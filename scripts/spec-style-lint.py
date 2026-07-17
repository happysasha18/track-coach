#!/usr/bin/env python3
"""spec-style-lint.py — the mechanical arm of the SPEC prose register (docs/spec-style.md).

Why this exists: re-styling the spec by hand drifted five times — a picked voice read fine on a
short sample, then degraded across long, constraint-heavy prose, and the tells only surfaced when a
human read it late. The tells are mechanical: a rule that OPENS with a negation instead of what
happens, machine jargon in user-facing prose, ALL-CAPS shouting where the plain statement carries
the force, and the banned contrast frame that names a thing by denying its neighbour. This scans the
register and flags each tell with its line, so the author (or a fresh session rewriting from scratch)
drives a section to clean against a machine, sparing a reader the patience. The register lives in docs/spec-style.md; this only holds
the floor it can check. Positive elegance (flow, sharpness) the linter cannot judge — that is what
the gold exemplars in docs/spec-style.md are for. Floor + exemplars = the whole quality system.

Checks (each maps to a rule in docs/spec-style.md):
  ERROR   negation-opener  a block leads with what it is NOT before what it IS (R4/plainness).
  ERROR   scissors         the contrast frame that names a thing by denying its neighbour, in a dash
                           or comma appositive or the parallel Russian negation-then-replacement forms
                           (a GLOBAL, PERMANENT ban).
  ERROR   provenance-narrative  a birth-story ("(Born of …)", "(Set by …)", "; born of …", a "Born of …"
                           sentence) in a normative body; provenance stays out of the body, in a docs home
                           keyed by the rule's code (docs/spec-style.md R15, docs/lenses.md). The ordinary
                           verb ("a row born of a split") is left alone.
  ERROR   machine-jargon   a dev/corporate word that has no place in this user-facing spec (R7).
  WARN    caps-shout       an ALL-CAPS ordinary word; force comes from the statement, not caps (R12).
  WARN    second-person    "you"/"your" — the register speaks of named actors, not the reader (R3).

In --gate mode (the DONE-GATE, docs/prose-quality-gate-design.md) the two soft signals are PROMOTED to
blocking errors, two more mechanical rules join them (reassurance, future-narration), the normative-only
rules skip marked informative regions (a user-story line, a blockquote, a NOTE), and a machine-readable
waiver file (scripts/spec-waivers.json) moves a still-unfixed finding into a dated, counted debt bucket
instead of a silent pass. Default mode is unchanged (caps-shout and second-person stay advisory), so the
section-by-section workflow and its tests keep their contract.

Two tiers (INV-166, docs/spec-style.md "Two tiers"): the checks split by whom they bind. The UNIVERSAL
tier (negation-opener, scissors, machine-jargon) is the plainness every live-spec document holds whatever
its register, so it binds every host's gate. The PACK-REGISTER tier (caps-shout, second-person,
reassurance, future-narration) is the pack's own reference-documentation taste, a host adopts on its own
word. `--tier universal` runs the universal tier as the gate and leaves the register tier advisory
(warnings, visible, non-blocking); `--tier full` runs the union as the gate — the pack's own docs, and
identical to `--gate`, which stays as its alias. The default (no flag) is unchanged: universal errors,
caps-shout/second-person warnings, reassurance/future-narration not checked.

Usage: spec-style-lint.py [--gate | --tier universal|full] FILE   (or: cat text | spec-style-lint.py ... -)
Exit 0 = no ERROR (WARN may still print) · exit 1 = at least one ERROR.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_common  # noqa: E402  (sibling module in scripts/)

# --- negation-opener -------------------------------------------------------------------------
# A block (a paragraph line, a bullet, or a bold-titled rule) should open with what happens, not
# with what the thing is NOT. The ugly pattern is DEFINE-BY-EXCLUSION: the opening states what the
# subject is not, via a copula or a becoming verb ("X is not Y", "X does not become Y", "Not a Z"),
# instead of what it is. An ACTION prohibition ("does not ask", "never re-carves", "no design
# decision inside") is correct register (R4 blesses "does not"/"never" for prohibitions) and is NOT
# flagged. We examine only the block's opening clause, after stripping markdown markers and a
# leading **bold title** (the title names the rule; the body that follows carries the statement).
LEAD_MARKERS = re.compile(r"^\s*(?:(?:[-*+>]\s+)|(?:#{1,6}\s+))+")   # real bullet/quote/heading (marker + space), never a **bold** run
BOLD_TITLE = re.compile(r"^\s*\*\*[^*]+\*\*\.?\s*")          # a leading **bold title** (+ its period)
NEG_OPENER_WORDS = 12                                        # opening clause window
COPULA = {"is", "are", "was", "were", "be", "been", "being"}
COPULA_NT = {"isn't", "aren't", "wasn't", "weren't"}         # contracted copula-negation
BECOMING = {"become", "becomes", "make", "makes", "mean", "means", "form", "forms",
            "constitute", "constitutes", "turn", "turns", "represent", "represents"}
# a subordinator fronts a CONDITION; a negation inside a condition ("priority when it is not
# normal") is legal, not define-by-exclusion. Only a negation NOT under a preceding subordinator
# counts as an opener tell.
SUBORD = {"when", "if", "where", "until", "once", "while", "unless", "whenever", "wherever",
          "as", "after", "before", "because", "since", "though", "although", "whether"}


def _strip_lead(line):
    """Remove markdown markers and a leading bold title; return the body that states the rule."""
    body = LEAD_MARKERS.sub("", line)
    body = BOLD_TITLE.sub("", body)
    return body.strip()


def _is_negation_opener(body):
    """A block opener defines by exclusion: it states what the subject is NOT (via a copula or a
    becoming verb) before what it is. Prohibitions on an action and negations inside a fronted
    condition are NOT tells."""
    words = [w.lower() for w in re.findall(r"[A-Za-z']+", body)][:NEG_OPENER_WORDS]
    if not words:
        return False
    if words[0] in ("not", "neither"):
        return True
    if words[0] == "no" and len(words) > 1 and words[1] == "longer":
        return True
    seen_subord = False
    for i, w in enumerate(words):
        if w in SUBORD:
            seen_subord = True
        if seen_subord:
            continue
        if w in COPULA_NT:
            return True
        if w in COPULA and i + 1 < len(words) and words[i + 1] == "not":
            return True
        if w in ("do", "does", "did") and i + 2 < len(words) \
                and words[i + 1] == "not" and words[i + 2] in BECOMING:
            return True
    return False


# --- scissors --------------------------------------------------------------------------------
# The contrast frame: defining a thing by denying its neighbour. A GLOBAL, PERMANENT ban.
# Four shapes are caught:
#   em-dash + not/never       the neighbour denied after a dash
#   comma appositive          the neighbour denied after a comma (the additive "… only" is exempt)
#   Russian «… , а не …»       the neighbour denied after a comma with «а не»
#   Russian «не … , а …» / «не столько … , сколько …»   the denial fronted
SCISSORS = re.compile(
    r"[—–]\s*(?:not|never)\b"                        # dash + not/never
    r"|(?<!\w)-{1,2}\s+(?:not|never)\b"              # double-hyphen + not/never
    r"|,\s+not\s+(?!only\b|just\b|merely\b|simply\b)"  # comma appositive, additive forms exempt
    r"|,\s*а\s+не\b"                                 # «… , а не …»
    r"|(?<!\w)не\s+столько\b"                        # «не столько … , сколько …»
    r"|(?<!\w)не\s+[^,]{1,60}?,\s*а\s"               # «не … , а …» (contrast)
    r"(?!не\b|если\b|когда\b|бы\b|то\b|также\b|тоже\b|потом\b|уже\b)",  # skip conditional/additive «а если/бы/…»
    re.IGNORECASE)

# --- machine jargon (curated, extensible — add a word only when it is unambiguously wrong here) --
JARGON = {"serialized", "questionnaire", "instantiate", "instantiated", "functionality",
          "leverage", "leveraging", "utilize", "utilizes", "utilization", "performant"}
JARGON_RE = re.compile(r"(?<!\w)(%s)(?!\w)" % "|".join(sorted(JARGON)), re.IGNORECASE)

# --- caps-shout ------------------------------------------------------------------------------
# an ALL-CAPS alphabetic word of length >= 2 that is not a known acronym or defined term.
CAPS_ALLOW = {"JSON", "CI", "HTML", "CSS", "RFC", "API", "URL", "UI", "MVP", "TTL", "MECE",
              "LLD", "HLD", "PRD", "README", "LICENSE", "OK", "MD", "CLI", "ID", "IDE", "NLP", "SPEC",
              "LIVE", "STATE", "NEXT", "NOW", "MUST", "SHALL", "NOTE", "QA", "TODO", "HEAD",
              "KPI", "UX", "FIXME", "VCS", "DOM", "PID", "OS", "CDN", "CDP",
              # doc / file names used as bare tokens
              "ARCHITECTURE", "ROADMAP", "JOURNAL", "VERSION", "LIVE-STATE", "MIGRATION", "CHANGELOG",
              # the audit record's milestone-read disposition values (INV-156), a closed vocabulary
              # pinned in the matrix (M-303) and the real docs/audit/ records — literal terms, not shout
              "MET", "OWED", "FLAG",
              # defined problem-ledger status values (E-24) and the prototype label
              "WATCHED", "OWNED", "AGREED", "NON-PROBLEM", "SOLVED", "ARCHIVED", "PROTOTYPE", "DECIDE",
              # defined prover/verify mode names — literal terms, not shout
              "CROSS-LINK", "FEATURE-FIT", "RE-ENTRY",
              # defined bold law-part labels of the narration law (INV-35)
              "IDENTITY", "DIGEST", "HEARTBEAT",
              # the design-review loop's three named rest-states (INV-154), a closed vocabulary
              "CONVERGES", "WAITS", "STANDS", "DOWN",
              # the push-gate reach map's three named check-set categories (INV-45), a closed vocabulary
              "EXPLICIT", "CONSERVATIVE", "SELF-TESTED",
              # semantic-version tier names (the version-history rows in ARCHITECTURE.md), conventional caps
              "MAJOR", "MINOR", "PATCH", "GB",
              # prior-art framework proper names cited in the reading-order note (INV-75)
              "BMAD"}
FILENAME_RE = re.compile(r"\b[\w./-]+\.(?:md|py|sh|json|txt|html|js|css|yml|yaml|toml)\b")
# capture an ALL-CAPS token, including a hyphenated compound (CROSS-LINK) as one token, so a
# defined mode name is judged whole against the allowlist rather than split into "LINK".
CAPS_RE = re.compile(r"(?<![\w`\[])([A-Z]{2,}(?:-[A-Z]{2,})*)(?![\w`\]-])")

# --- second person ---------------------------------------------------------------------------
# The register speaks of named actors, not the reader (R3). A quoted product-copy literal is the
# exception: a double-quoted span is the PRODUCT's own voice (a line the product shows the human,
# e.g. the read contract "needs your word: what, by when"), not the spec's register, so a second
# person inside quotes is data the spec cites, not a leak. Only the second-person rule takes this
# exemption; caps/scissors/jargon stay global.
SECOND_PERSON = re.compile(r"(?<!\w)(you|your|you're|yours|yourself)(?!\w)", re.IGNORECASE)
QUOTED_SPAN = re.compile(r"\"[^\"]*\"")


def _second_person_outside_quotes(scrub):
    """True when a second-person word appears outside every double-quoted span (a real register
    leak); a match that lies wholly inside quotes is a cited product literal and does not count."""
    spans = [m.span() for m in QUOTED_SPAN.finditer(scrub)]
    for m in SECOND_PERSON.finditer(scrub):
        s, e = m.span()
        if not any(qs <= s and e <= qe for qs, qe in spans):
            return True
    return False

# --- reassurance / invitation (gate mode only, R4/R7) ----------------------------------------
# Reassuring or inviting the reader has no place in a normative sentence. Curated phrases, kept
# conservative so a legitimate word ("just one row" as a quantity) is not caught; "simply" and the
# listed phrases are the unambiguous tells (the recurring intro-block leak said "you can ignore").
REASSURANCE = ("don't worry", "no need to", "feel free", "of course", "rest assured",
               "you can ignore", "you don't have to", "as we saw", "as noted above",
               "needless to say", "simply put")
REASSURANCE_RE = re.compile(r"(?<!\w)simply(?!\w)", re.IGNORECASE)  # bare 'simply' is a tell on its own

# --- future narration (gate mode only, R4) ---------------------------------------------------
# A reference spec states what is true in the present. "the card will show", "the row that shall
# carry" is future narration; rephrase to present. Scoped to will/shall + a spec verb to avoid
# catching every "will".
FUTURE_NARRATION = re.compile(
    r"(?<!\w)(?:will|shall)\s+(?:be|show|shows|display|appear|open|contain|"
    r"return|carry|report|hold|become|run|fire|land|ship)\b", re.IGNORECASE)

# --- provenance-narrative (global, R15) ------------------------------------------------------
# A normative body states the mechanism in plain present tense; the provenance — the date and the
# case that motivated the rule — lives in a docs home keyed by the rule's code (docs/lenses.md), never
# as an inline birth-story. The tell has three shapes, told apart from the ordinary verb by SHAPE, not
# by the word alone: a parenthetical aside "(Born of …)", a Formal-index trailing cell "…; born of …",
# and a sentence that OPENS with "Born of …" or says "… was born of …". The two ordinary-verb uses —
# "every row born of a split cites …", "a clause born of an approved look points at its norm" — are
# lowercase, mid-clause, and carry no story; none of the arms below match them. The one-token dated
# pointers the rule permits (INV-43's `norm: <path>`, INV-119's `commit <hash>`) carry no "born of".
PROV_PAREN = re.compile(r"\([^)]*\bborn of\b", re.IGNORECASE)   # parenthetical aside "(Born of …)"
PROV_CELL = re.compile(r";\s+born of\b", re.IGNORECASE)         # Formal-index trailing cell "…; born of …"
# a dated birth-story parenthetical opening with a provenance verb/phrase and carrying an ISO date:
# "(Set by …)", "(Set on …)", "(Born in the field: …)", "(Sharpened … :)", "(Raised by …)",
# "(recorded live … :)", "(recorded 2026-… :)", "(The trigger broadened … :)", "(the worked miss: …)".
# It is told from an ordinary dated note (which opens with a bare date, "Audit", "rows", "The owner's
# word", or a dateless "(recorded profile line …)") by its provenance OPENER, and the required ISO date
# keeps a dateless parenthetical from tripping. The `recorded` arm uses a lookahead so the date it needs
# is not consumed by the opener.
PROV_STORY_OPEN = re.compile(
    r"\(\s*(?:Set (?:by|on)|Born (?:of|in)|Sharpened|Raised by|Softened"
    r"|[Rr]ecorded (?=live |\d{4})|The trigger broadened|the worked miss)"
    r"[^)]*\d{4}-\d{2}-\d{2}")
# a clause OPENING with capital-B "Born of" (sentence/bullet start) or the "was born of" form; the
# capital B (no re.IGNORECASE) is what tells the story-opener from the lowercase ordinary verb.
PROV_SENTENCE = re.compile(r"(?<![A-Za-z])Born of\b")
PROV_WASBORN = re.compile(r"\bwas born of\b", re.IGNORECASE)


def _is_provenance_narrative(scrub):
    """A birth-story in a normative body: a parenthetical/cell aside or a story-opening sentence.
    Told from the ordinary verb by shape (parenthesis, leading `;`, or a capital-B/was-born opener)."""
    return bool(PROV_PAREN.search(scrub) or PROV_CELL.search(scrub)
                or PROV_SENTENCE.search(scrub) or PROV_WASBORN.search(scrub)
                or PROV_STORY_OPEN.search(scrub))


# --- TIERS (INV-166) --------------------------------------------------------------------------
# The checks split into two named tiers by whom they bind — a host adopts the floor without the
# pack's own taste. Named here as the code copy of the split; docs/spec-style.md "Two tiers"
# carries the prose.
#   UNIVERSAL       negation-opener, scissors, machine-jargon — the plainness every live-spec
#                   document holds whatever its register; binds every host's gate.
#   PACK-REGISTER   caps-shout, second-person, reassurance, future-narration — the pack's own
#                   reference-documentation taste, a host adopts on its own word.
# (provenance-narrative stays outside the split — a birth-story in a normative body has no
# register reading at all, so it runs as an error in every tier, unconditionally, as before.)
UNIVERSAL_RULES = frozenset({"negation-opener", "scissors", "machine-jargon"})
PACK_REGISTER_RULES = frozenset({"caps-shout", "second-person", "reassurance", "future-narration"})
TIERS = ("default", "universal", "full")


def lint(text, gate=False, tier=None):
    """Return (errors, warnings); each a list of (line_no, code, snippet).

    tier resolves the mode; when omitted it derives from gate (back-compat): tier="full" if
    gate else "default". Explicit values:
      "default"    negation-opener/scissors/machine-jargon are errors; caps-shout/second-person
                   are warnings; reassurance/future-narration are not checked. (today's default,
                   unchanged.)
      "universal"  the UNIVERSAL tier is the gate (errors); the PACK-REGISTER tier — all four
                   rules, including reassurance/future-narration — runs as advisory warnings;
                   informative-region skipping behaves as in "full".
      "full"       the union as errors (identical to --gate): caps-shout, second-person,
                   reassurance, and future-narration are all promoted to errors alongside the
                   UNIVERSAL tier.
    In both "universal" and "full" the normative-only rules (negation-opener, second-person,
    reassurance, future-narration) skip marked informative regions (user-story line, blockquote,
    NOTE) — global rules (scissors, machine-jargon, caps-shout, provenance-narrative) always run."""
    if tier is None:
        tier = "full" if gate else "default"
    if tier not in TIERS:
        raise ValueError("unknown tier: %r (expected one of %s)" % (tier, ", ".join(TIERS)))
    gate_like = tier in ("universal", "full")     # exempt-region skipping + reassurance/future-narration run
    register_errors = tier == "full"              # pack-register rules land as errors only at "full"

    errors, warnings = [], []
    lines = text.splitlines()
    exempt = gate_common.exempt_flags(lines) if gate_like else [False] * len(lines)
    prev_blank = True
    for idx, raw in enumerate(lines):
        i = idx + 1
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped:
            prev_blank = True
            continue
        # strip a leading bullet/quote marker (so "- Never …" is not read as a dash-cut), then
        # inline code spans and bracketed anchors, so `docs/decisions/` and [INV-4] never trip
        # caps / jargon / scissors. A **bold title** is kept — jargon/caps inside it still count.
        scrub = gate_common.scrub(stripped)
        exempt_here = exempt[idx]
        # bucket a pack-register rule by tier: at "full" the promoted rules are errors, else warnings.
        norm_bucket = errors if register_errors else warnings

        is_block_lead = prev_blank or bool(LEAD_MARKERS.match(line))
        if is_block_lead and _is_negation_opener(_strip_lead(line)) and not exempt_here:
            errors.append((i, "negation-opener", stripped[:110]))
        if SCISSORS.search(scrub):                                   # global
            errors.append((i, "scissors", stripped[:110]))
        if _is_provenance_narrative(scrub):                          # global
            errors.append((i, "provenance-narrative", stripped[:110]))
        for m in JARGON_RE.finditer(scrub):                          # global
            errors.append((i, "machine-jargon:%s" % m.group(1).lower(), stripped[:110]))
        for m in CAPS_RE.finditer(scrub):                            # global
            if m.group(1) not in CAPS_ALLOW:
                (errors if register_errors else warnings).append(
                    (i, "caps-shout:%s" % m.group(1), stripped[:110]))
        if _second_person_outside_quotes(scrub) and not exempt_here:  # normative-only
            norm_bucket.append((i, "second-person", stripped[:110]))
        if gate_like and not exempt_here:
            low = scrub.lower()
            hit = next((p for p in REASSURANCE if p in low), None) or \
                (REASSURANCE_RE.search(scrub) and "simply")
            if hit:
                norm_bucket.append((i, "reassurance:%s" % hit, stripped[:110]))
            if FUTURE_NARRATION.search(scrub):
                norm_bucket.append((i, "future-narration", stripped[:110]))
        prev_blank = False
    return errors, warnings


def apply_waivers(findings, filename, waivers, today=None):
    """Split findings into (active_errors, waived). A finding is (line, code, snippet); its rule is
    the code's head before ':'. Records which waiver ids matched, for stale-waiver reporting."""
    active, waived, matched = [], [], set()
    for line, code, snip in findings:
        rule = code.split(":", 1)[0]
        w = gate_common.match_waiver(rule, filename, snip, waivers, today)
        if w:
            waived.append((line, code, snip, w["id"]))
            matched.add(w["id"])
        else:
            active.append((line, code, snip))
    return active, waived, matched


WAIVER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spec-waivers.json")

# The rules this gate emits — used to scope the stale-waiver check to the style gate's own
# waivers, since the waiver file is shared with the redundancy gate (spec-redundancy).
STYLE_RULES = {"negation-opener", "scissors", "provenance-narrative", "machine-jargon",
               "caps-shout", "second-person", "reassurance", "future-narration"}


USAGE = "usage: spec-style-lint.py [--gate | --tier universal|full] FILE|-\n"


def _parse_argv(argv):
    """Return (tier, positional) or raise ValueError with a usage message. --gate is the alias for
    --tier full (back-compat, tests/test_convergence_locks.py calls --gate and must keep working
    unchanged); an explicit --tier wins ties with a redundant --gate on the same command line."""
    tier = None
    positional = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--gate":
            tier = tier or "full"
            i += 1
        elif a == "--tier":
            if i + 1 >= len(argv):
                raise ValueError(USAGE)
            tier = argv[i + 1]
            i += 2
        elif a.startswith("--tier="):
            tier = a.split("=", 1)[1]
            i += 1
        elif a.startswith("--"):
            raise ValueError(USAGE)
        else:
            positional.append(a)
            i += 1
    if tier is not None and tier not in ("universal", "full"):
        raise ValueError(
            "spec-style-lint.py: unknown --tier %r (expected 'universal' or 'full')\n" % tier)
    if len(positional) != 1:
        raise ValueError(USAGE)
    return (tier or "default"), positional[0]


def main(argv):
    try:
        tier, src = _parse_argv(argv)
    except ValueError as exc:
        sys.stderr.write(str(exc))
        return 2
    gate_like = tier in ("universal", "full")
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    errors, warnings = lint(text, tier=tier)

    waived, stale = [], []
    if gate_like:
        all_waivers = gate_common.load_waivers(WAIVER_PATH)
        errors, waived, matched = apply_waivers(errors, src, all_waivers)
        # The waiver file is shared with other gates (spec-redundancy). Scope the stale check to
        # THIS gate's own rules, so a live redundancy waiver is never reported stale by the style
        # gate (it matches no style finding by design).
        mine = [w for w in all_waivers if w.get("rule") in STYLE_RULES]
        stale = gate_common.stale_waivers(mine, matched)

    if not errors and not warnings and not waived:
        label = {"default": "", "universal": "/universal", "full": "/gate"}[tier]
        print("OK (spec-style%s): no register tells found." % label)
    if errors:
        print("SPEC-STYLE LINT — ERROR (docs/spec-style.md): a rule opens with what it is NOT,")
        print("shouts, uses machine jargon, cuts with «X — not Y», carries a birth-story in the body,")
        print("reassures, or narrates the future.")
        for line_no, code, snip in errors:
            print("  line %d  [%s]  %s" % (line_no, code, snip))
    if warnings:
        print("SPEC-STYLE LINT — warn (soft signals; a fully-converted section clears these too):")
        for line_no, code, snip in warnings:
            print("  line %d  [%s]  %s" % (line_no, code, snip))
    if waived:
        print("SPEC-STYLE LINT — WAIVED (dated debt, scripts/spec-waivers.json; still counted):")
        for line_no, code, snip, wid in waived:
            print("  line %d  [%s]  (%s)  %s" % (line_no, code, wid, snip))
    if stale:
        print("SPEC-STYLE LINT — stale waivers (defect gone; remove these from spec-waivers.json):")
        for w in stale:
            print("  [%s]  %s" % (w.get("id"), w.get("snippet")))
    print('{"severity":"%s","code":"spec-style","errors":%d,"warnings":%d,"waived":%d,"stale":%d}'
          % ("error" if errors else "advisory", len(errors), len(warnings), len(waived), len(stale)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
