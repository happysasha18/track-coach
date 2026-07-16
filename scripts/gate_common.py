"""gate_common.py — shared helpers for the prose-quality DONE-GATE (docs/prose-quality-gate-design.md).

Imported by the hyphenated gate scripts (spec-style-lint.py in --gate mode, spec-redundancy-precheck.py,
spec-judge.py, spec-done-gate.py). Holds the pieces they must agree on: text scrubbing, sentence/bullet
segmentation, the machine-readable waiver file, and informative-region (exemption) detection. One home per
rule, so the linter and the redundancy check strip and segment text the same way.
"""
import datetime
import json
import os
import re

# --- text scrubbing (shared with the linter) ------------------------------------------------
LEAD_MARKERS = re.compile(r"^\s*(?:(?:[-*+>]\s+)|(?:#{1,6}\s+))+")
BOLD_TITLE = re.compile(r"^\s*\*\*[^*]+\*\*\.?\s*")
FILENAME_RE = re.compile(r"\b[\w./-]+\.(?:md|py|sh|json|txt|html|js|css|yml|yaml|toml)\b")


def scrub(text):
    """Strip lead markers, inline code, bracketed anchors, and filenames — the neutral form the
    register checks run against, so `[INV-4]` and `docs/x.md` never trip a rule."""
    s = LEAD_MARKERS.sub("", text)
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = FILENAME_RE.sub(" ", s)
    return s


# --- informative-region (exemption) detection ------------------------------------------------
# Normative-only rules (second-person, negation-opener, reassurance, future-narration) skip these
# regions; global rules (scissors, machine-jargon, caps-shout) always run. A user quote or a
# user-story line is a marked informative companion (docs/spec-style.md R7b/R7c), not normative law.
USER_STORY = re.compile(r"^\s*(?:[-*+>]\s+)*\*\*\s*user\s*story\s*:?\s*\*\*", re.I)
NOTE_INFORMATIVE = re.compile(r"^\s*(?:[-*+]\s+)*(?:\*\*)?\s*note\s*\(informative\)", re.I)
BLOCKQUOTE = re.compile(r"^\s*>")


def exempt_flags(lines):
    """Given a list of raw lines, return a list[bool] — True where normative-only rules are exempt
    (inside a user-story block, an informative NOTE block, or a blockquote line). A user-story /
    NOTE block runs from its lead line to the next blank line; a blockquote is per-line."""
    flags = []
    in_block = False
    for raw in lines:
        stripped = raw.strip()
        if not stripped:
            in_block = False
            flags.append(False)
            continue
        if USER_STORY.match(raw) or NOTE_INFORMATIVE.match(raw):
            in_block = True
        flags.append(in_block or bool(BLOCKQUOTE.match(raw)))
    return flags


# --- sentence / bullet segmentation (for the redundancy pre-check) ---------------------------
_ABBREV = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "al.")


def segment_units(text):
    """Split the document into content units — sentences and bullet clauses — each with its 1-based
    start line. Returns a list of dicts {line, raw, norm_tokens}. Splits on sentence punctuation and
    on ';', guarding common abbreviations, and treats each bullet as its own unit."""
    units = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("|"):
            continue
        body = scrub(stripped)
        # protect abbreviations from the sentence splitter
        guarded = body
        for a in _ABBREV:
            guarded = guarded.replace(a, a.replace(".", "\0"))
        parts = re.split(r"(?<=[.?!;])\s+", guarded)
        for part in parts:
            part = part.replace("\0", ".").strip()
            if part:
                units.append({"line": lineno, "raw": part})
    return units


# --- waivers -----------------------------------------------------------------------------------
WAIVER_FIELDS = ("id", "rule", "file", "snippet", "reason", "owner", "date", "expiry")
MAX_WAIVER_DAYS = 30


def _today():
    return datetime.date.today()


def load_waivers(path):
    """Load the waiver list. Missing file → empty list."""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("waiver file must be a JSON array: %s" % path)
    return data


def waiver_status(waiver, today=None):
    """'active' | 'expired' — a waiver whose expiry has passed no longer suppresses (it reverts to a
    hard error, so a forgotten debt breaks the gate rather than fading to silence)."""
    today = today or _today()
    exp = datetime.date.fromisoformat(waiver["expiry"])
    return "active" if today <= exp else "expired"


def match_waiver(rule, filename, offending_text, waivers, today=None):
    """Return the active waiver covering this finding, or None. A waiver matches when its rule and
    file match and its snippet occurs verbatim in the offending text. Snippet-based (not line-based)
    so the waiver self-invalidates once the offending text is fixed."""
    base = os.path.basename(filename)
    for w in waivers:
        if w.get("rule") != rule:
            continue
        if w.get("file") not in (filename, base):
            continue
        if w.get("snippet") and w["snippet"] in offending_text:
            if waiver_status(w, today) == "active":
                return w
    return None


def stale_waivers(waivers, matched_ids):
    """Waivers whose snippet matched no finding this run — the defect they covered is gone, so the
    waiver should be removed. Returns the list of stale waiver dicts."""
    return [w for w in waivers if w.get("id") not in matched_ids]
