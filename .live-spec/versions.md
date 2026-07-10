# Installed live-spec pack versions (freshness record)

| component | version / state |
|---|---|
| pack (`~/live-spec/VERSION`) | **1.0.8** |
| installed skills (`~/.claude/skills/*`) | in sync with source `~/live-spec/skills/` — verified by `diff -rq` 2026-07-10 (only stray: a generated `communicator/SKILL.html`, harmless) |

Last checked 2026-07-10 ~17:50 (was pack 0.5.3 / live-spec-base 0.1.6 on the 2026-07-05 attach record —
a 0.5.3 → 1.0.8 pack bump; installed copies were already synced by the live-spec window Jul 9–10).
Skills are read from `~/.claude/skills/` at invocation; the live-spec session owns their edits
(installed copies sync from `~/live-spec/skills/`). Re-verify at each safe breakpoint (base rule 8).
