# track-coach — live-spec HOST profile (attach record, 2026-07-05)

Host-level overrides only (the settings ladder, pack SPEC E-13: session beats host beats personal
beats package default). Settings about Alexander himself (language, proactivity) live in his personal
profile `~/.claude/live-spec/profile.md` — not here.

## Attach

- Adopted mid-flight 2026-07-05 (the s57 adoption pass). The host was already authored largely IN the
  method (SPEC/TEST_MATRIX/ARCHITECTURE/JOURNAL/NEXT_STEPS + prover records since ~s11), so ADOPT
  phases 0–5 were a verification walk, not a rewrite. Provenance: **native-live-spec** for the doc set;
  no re-engineered-claim backlog.
- Canonical doc homes: `docs/SPEC.md` · `docs/TEST_MATRIX.md` · `docs/ARCHITECTURE.md` ·
  `JOURNAL.md` + `NEXT_STEPS.md` (repo root, gitignored — durable on disk, not in git) ·
  roadmap = the FORWARD QUEUE inside `NEXT_STEPS.md` (no separate ROADMAP.md).
- **Surface registry lives as CODE, not a .md**: `tests/test_completeness_gate.py` `USER_SURFACES`
  (INV-46) — every rendered surface must be registered + populated or the suite is red. This is the
  E-10 registry, enforced rather than written; a separate SURFACE_REGISTRY.md would be a second home.

## Host overrides (each one written down, never silent)

1. **Push gate is HUMAN-first:** track-coach NEVER pushes without Alexander's explicit OK (his
   standing rule). On every push the README rides with fresh screenshots. The machine-checkable part
   is `guardrails/pre-push` (installed hook; pack 5-gate shape).
2. **Prover cadence override (pack gate a):** the pack wants a same-day prover record per push; this
   host runs per-feature CROSS-LINK proves + milestone deep audits (Fable) instead. So the hook's
   gate (a) is a WARNING, not a block. Rationale: push frequency here is milestone-shaped; every
   feature already carries its prove.
3. **Concurrent-edit fence not armed:** single-writer rule stands (s47 coordination — skill/pack and
   track-coach edits happen only from THE track-coach session; the tlvphoto/live-spec sessions never
   write here). Arm `fence-refresh` only if a second writer ever appears.
4. **Test command:** `python3 -m pytest` (pytest pip-installed under `~/Library/Python/3.9`); full
   suite ~210 s. Browser-level tests need headless Chrome (present on this Mac).
5. **Matrix coverage checklist is a prose walk** (`docs/TEST_MATRIX.md` §8), not checkboxes; the
   hook's gate (d) checks boxes only if boxes ever appear. The real ownership/coverage enforcement is
   `tests/test_traceability.py` (in the suite = hook gate b/c).

## Installed pack versions at attach (2026-07-05)

See `versions.md` (same folder).
