#!/usr/bin/env python3
"""check-shipped-language.py — the machine that holds the English + no-personal-names
line on SHIPPED artifacts (ROADMAP row 275, SPEC INV-120). Composes with row 274, which
states the impersonal voice; this script is the machine that holds it.

Two MECHANICAL offences, each reported as file:line so the fix is mechanical:
  (1) cyrillic    a Cyrillic character outside a deliberately-emitted user-language string
  (2) owner-name  an owner/personal name (Alexander, Sasha + variants) in a shipped
                  spec / README / skill / code comment or prose

The wish names a THIRD offence — a coined non-English metaphor where a plain English term
belongs. That is NOT mechanically reliable (a metaphor is a judgement, not a pattern), so
this script deliberately does NOT attempt it: it is left to the human and to the existing
register lints (scripts/spec-style-lint.py — machine-jargon, scissors). Silence here is not
a clean bill on (3).

SHIPPED SET (the files a reader outside this machine meets). Spared, by design, are the
local-only diaries and the fixture homes: JOURNAL.md, ROADMAP.md, NEXT_STEPS.md, MIGRATION.md,
and everything under docs/, attic/, inbox/, .live-spec/, tests/, evals/, prototype/ (a
fenced sketch is not shipped product, SPEC INV-17 — and a prod allowlist may not point into
it, so the exclude, not a glob, is its home). The gate's own
machinery is spared too — this detector's own source and its allowlist name the very tokens
they exist to catch, so scanning them would report the detector's patterns as offences.

ALLOWLIST (scripts/shipped-language-allowlist.json — same dated-debt shape as spec-waivers.json,
the equivalence-gate rule: a NEW offence reds, a listed one is counted debt, never a silent pass):
  user_language_globs : files whose Cyrillic is deliberate program data. Cyrillic in them
                        is never an offence.
  authorship_globs    : files where an owner name is a legitimate authorship byline (LICENSE,
                        the plugin manifest's author field, a copyright line). Never an offence.
  cyrillic_waivers    : [{file, snippet, note, added}] pre-existing Cyrillic debt, counted.
  name_waivers        : [{file, snippet, note, added}] pre-existing owner-name debt, counted.
Region rule: Cyrillic inside a fenced ```user ... ``` block, or on a line carrying an inline
marker (`user-language` in a trailing #/<!-- --> comment), is a deliberate sample and spared.

Usage:
  check-shipped-language.py [--root DIR] [--allowlist FILE] [FILE ...]
Exit 0 = no active offence (waived debt may print) . Exit 1 = at least one active offence.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

CYRILLIC = re.compile(r"[Ѐ-ӿԀ-ԯ]")
OWNER = re.compile(
    r"\b(?:Alexander|Sasha|Sashka|Alexandr)\b"
    r"|Александр|Алекс(?:андр)?|Саш(?:а|е|у|и|ей|ку|ка)",
    re.IGNORECASE)
USER_REGION_MARK = re.compile(r"(?:#|<!--)\s*user-language")
FENCE_USER_OPEN = re.compile(r"^\s*```+\s*user\b")
FENCE_ANY = re.compile(r"^\s*```")

EXCLUDE_DIRS = ("docs/", "attic/", "inbox/", ".live-spec/", "tests/", "evals/", "prototype/")
EXCLUDE_FILES = ("JOURNAL.md", "ROADMAP.md", "NEXT_STEPS.md", "MIGRATION.md",
                 "check-shipped-language.py", "shipped-language-allowlist.json")
TEXT_EXT = (".md", ".py", ".sh", ".json", ".txt", ".yml", ".yaml", ".html", ".js", ".css")


def load_allowlist(path):
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def is_excluded(rel):
    if any(rel == e or rel.endswith("/" + e) for e in EXCLUDE_FILES):
        return True
    return any(rel == d[:-1] or rel.startswith(d) for d in EXCLUDE_DIRS)


def shipped_set(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files"],
                             capture_output=True, text=True, check=True).stdout
        rels = out.splitlines()
    except Exception:
        rels = []
        for dp, _, fns in os.walk(root):
            for fn in fns:
                rels.append(os.path.relpath(os.path.join(dp, fn), root))
    return [r for r in rels if r.endswith(TEXT_EXT) and not is_excluded(r)]


def globbed(rel, globs):
    return any(fnmatch.fnmatch(rel, g) for g in (globs or []))


def waived(rel, snippet, waivers):
    for w in waivers or []:
        if fnmatch.fnmatch(rel, w.get("file", "")) and w.get("snippet", "") in snippet:
            return True
    return False


def scan_file(path, rel, allow):
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except (UnicodeDecodeError, OSError):
        return
    cyr_file_ok = globbed(rel, allow.get("user_language_globs"))
    name_file_ok = globbed(rel, allow.get("authorship_globs"))
    in_user_fence = False
    for i, raw in enumerate(lines, 1):
        if FENCE_USER_OPEN.match(raw):
            in_user_fence = True
            continue
        if in_user_fence and FENCE_ANY.match(raw):
            in_user_fence = False
            continue
        snip = raw.strip()[:110]
        if not cyr_file_ok and not in_user_fence and not USER_REGION_MARK.search(raw):
            if CYRILLIC.search(raw) and not waived(rel, snip, allow.get("cyrillic_waivers")):
                yield (i, "cyrillic", snip)
        if not name_file_ok:
            if OWNER.search(raw) and not waived(rel, snip, allow.get("name_waivers")):
                yield (i, "owner-name", snip)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--allowlist", default=None)
    ap.add_argument("files", nargs="*")
    a = ap.parse_args(argv[1:])
    default_allow = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "shipped-language-allowlist.json")
    allow = load_allowlist(a.allowlist or default_allow)

    if a.files:
        pairs = [(f, os.path.relpath(f, a.root)) for f in a.files]
    else:
        pairs = [(os.path.join(a.root, r), r) for r in shipped_set(a.root)]

    offences = []
    for path, rel in pairs:
        for ln, code, snip in scan_file(path, rel, allow):
            offences.append((rel, ln, code, snip))

    if not offences:
        print("OK (shipped-language): no Cyrillic or owner-name offences in the shipped set.")
        print('{"severity":"ok","code":"shipped-language","offences":0}')
        return 0

    print("FAIL (shipped-language): a shipped artifact carries Cyrillic outside a deliberate")
    print("user-language string, or an owner/personal name (SPEC INV-120, ROADMAP row 275).")
    for rel, ln, code, snip in offences:
        print("  %s:%d  [%s]  %s" % (rel, ln, code, snip))
    print("  Fix: state the requirement impersonally (row 274) and move candid/Russian process")
    print("  notes to the local-only diaries; mark a deliberate sample with a ```user fence or an")
    print("  inline 'user-language' comment; add known pre-existing debt to the allowlist.")
    print('{"severity":"error","code":"shipped-language","offences":%d}' % len(offences))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
