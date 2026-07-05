# Pin verification checkpoint — s58 worker run (2026-07-05)

Verified all `symbol:LINE` pins in `docs/ARCHITECTURE.md` that point into files under `scripts/`.
17 pins audited. One BROKEN (renamed symbol). All others OK or DRIFTED.

## Results table

| node | pin as written | current line | verdict |
|---|---|---|---|
| N8 | `build_widget.py` `build_recommendations:1355` | 1355 | OK |
| N8 | `build_widget.py` `build_cards:1618` | 1618 | OK |
| N10 | `build_reference_notes.py` `build:198` | 198 | OK |
| N12 | `build_widget.py` `build_html:1983` | 1983 | OK |
| N12 | `build_widget.py` `build_story:1802` | 1802 | OK |
| N13 | `build_widget.py` `PLAYER_LOGIC:3928–3936` | 3974–3982 (markers now `PLAYER_LOGIC_START` / `PLAYER_LOGIC_END`) | DRIFTED |
| N14 | `build_widget.py` `VIEW_LOGIC:3386–3398` | 3432–3444 (markers now `VIEW_LOGIC_START` / `VIEW_LOGIC_END`) | DRIFTED |
| N15 | `build_widget.py` `build_cards:1618` | 1618 | OK |
| N15 | `build_widget.py` `build_recommendations:1355` | 1355 | OK |
| N15 | `build_widget.py` `_read_html:2314` | 2314 | OK |
| N16 | `build_widget.py` `<style>:2879` | 2923 | DRIFTED |
| N16 | `build_widget.py` `:root:2880` | 2924 | DRIFTED |
| N17 | `build_widget.py` `_ref_read_html:2817` | 2861 | DRIFTED |
| N17 | `build_widget.py` `_refread_bars_html:2363` | 2363 | OK |
| N17 | `build_widget.py` `render_reference_read:2665` | 2655 | DRIFTED |
| N17 | `build_widget.py` `render_reference_notes:2457` | 2457 | OK |
| N17 | `build_widget.py` `_web_panel_html:2583` | symbol does not exist — renamed to `_web_body_html` at line 2583 | BROKEN |

## _web_panel_html flag

ARCHITECTURE.md line 99 (N17 row) references `` `_web_panel_html:2583` ``.
The function no longer exists in `build_widget.py`. It was renamed `_web_body_html` (now at line 2583).
The doc pin is BROKEN and the symbol name is wrong.

## Raw grep commands and output

```
# N8 build_recommendations
grep -n "def build_recommendations" scripts/build_widget.py
→ 1355:def build_recommendations(core, detail, masking, S, als_overlay=None, stemmap=None, rhythm=None, character=None, repetition=None, selfsim=None):

# N8 / N15 build_cards
grep -n "def build_cards" scripts/build_widget.py
→ 1618:def build_cards(core, detail, S):

# N10 build in build_reference_notes.py
grep -n "def build" scripts/build_reference_notes.py
→ 198:def build(out_path: Path = DEFAULT_OUT) -> None:

# N12 build_html
grep -n "def build_html" scripts/build_widget.py
→ 1983:def build_html(core, detail, masking, als, out_path, title, S, als_offset_s=None, stemmap=None,

# N12 build_story
grep -n "def build_story" scripts/build_widget.py
→ 1802:def build_story(core, als_overlay, seg_bounds=None):

# N13 PLAYER_LOGIC markers
grep -n "PLAYER_LOGIC" scripts/build_widget.py
→ 3974: /* PLAYER_LOGIC_START — pure DOM-free player state machine (SPEC §B.14); node-executed by test_player_logic */
→ 3982: /* PLAYER_LOGIC_END */

# N14 VIEW_LOGIC markers
grep -n "VIEW_LOGIC" scripts/build_widget.py
→ 3432: /* VIEW_LOGIC_START — pure DOM-free view helpers (SPEC §B.15/INV-31); node-executed by test_view_logic */
→ 3444: /* VIEW_LOGIC_END */

# N15 _read_html
grep -n "def _read_html" scripts/build_widget.py
→ 2314:def _read_html(narrative_md):

# N16 <style>
grep -n "<style>" scripts/build_widget.py
→ 2923:<style>

# N16 :root
grep -n ":root" scripts/build_widget.py
→ 2924::root{--bg:#0c0e14;--panel:...

# N17 _ref_read_html
grep -n "def _ref_read_html" scripts/build_widget.py
→ 2861:def _ref_read_html(run_dir):

# N17 _refread_bars_html
grep -n "def _refread_bars_html" scripts/build_widget.py
→ 2363:def _refread_bars_html(track_z, centroid_z, conf_entries=None, confirm_z=0.4):

# N17 render_reference_read
grep -n "def render_reference_read" scripts/build_widget.py
→ 2655:def render_reference_read(track_raw_fp, directions, norm, confirmation=None, confirm_z=0.4,

# N17 render_reference_notes
grep -n "def render_reference_notes" scripts/build_widget.py
→ 2457:def render_reference_notes(artist_entry):

# N17 _web_panel_html / _web_body_html (rename check)
grep -n "_web_panel_html\|_web_body_html" scripts/build_widget.py
→ 2583:def _web_body_html(direction_name, conf_entries, centroid_z, confirm_z=0.4, web_data=None):
→ 2793:        body = _web_body_html(lean.direction, conf_e, directions[lean.direction], confirm_z,
(no hit for _web_panel_html)
```
