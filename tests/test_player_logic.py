#!/usr/bin/env python3
"""Player STATE-MACHINE tests (SPEC §B.14, matrix INV-35..39).

The synced player (play/pause × per-stem mute × solo × seek) is the widget's most interactive
surface and was, until 2026-06-23, tested ONLY by string-matching the JS source — so the
COMBINATIONS were never exercised (the seek-stops-playback bug, 0.8.28, was exactly that class).

Here we test the REAL shipped logic, not a Python mirror: the pure DOM-free helpers
(`pgains`/`toggleStem`/`seekResult`) are emitted between `__PLAYER_LOGIC_START__`/`__PLAYER_LOGIC_END__`
markers in the rendered widget. We pull that block out of the rendered HTML, run it in node, and
assert the cross-control invariants over real toggle sequences. (Assert against the artifact, not a
fragment — playbook.) Skips cleanly if node is unavailable.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import build_widget  # noqa: E402

NODE = shutil.which("node")
_BLOCK = re.compile(r"/\* PLAYER_LOGIC_START.*?PLAYER_LOGIC_END \*/", re.S)


def _render_full_html():
    """Render a full-mode widget (stems present ⇒ the per-stem player + its logic block ship)."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_player_"))
    sdir = tmp / "stems_web"
    sdir.mkdir()
    for s in ("drums", "bass", "vocals"):
        (sdir / f"{s}.m4a").write_bytes(b"\x00")
    core = {
        "duration_s": 96.0, "time_bins": [round(i * 2, 3) for i in range(48)], "tempo": 123,
        "energy": [round(0.2 + 0.6 * i / 48, 3) for i in range(48)],
        "brightness": [0.5] * 48, "density": [0.4] * 48,
        "wobble_rate": [1.0] * 48, "stereo_width": [0.4] * 48,
        "energy_trend": 0.4, "brightness_trend": 0.0, "density_trend": 0.0,
        "stereo_width_trend": 0.0,
    }
    out = tmp / "widget.html"
    build_widget.build_html(core, {}, None, None, str(out), "Player Test",
                            build_widget.STRINGS, audio_stems_rel="stems_web", mode="full")
    return out.read_text(encoding="utf-8")


@unittest.skipUnless(NODE, "node not installed — player state-machine tests need a JS engine")
class PlayerStateMachine(unittest.TestCase):
    """INV-35..39: execute the REAL extracted player helpers in node, over combinations."""

    @classmethod
    def setUpClass(cls):
        html = _render_full_html()
        m = _BLOCK.search(html)
        assert m, "player logic block markers not found in the rendered widget"
        cls.tmp = Path(tempfile.mkdtemp(prefix="tc_playerjs_"))
        cls.mod = cls.tmp / "player_logic.js"
        cls.mod.write_text(m.group(0), encoding="utf-8")

    def _node(self, body):
        """Run `body` JS with the extracted helpers required as P; fail the test on a non-zero exit."""
        js = (f"const P=require({json.dumps(str(self.mod))});\n"
              f"const A=(c,m)=>{{if(!c){{console.error('FAIL: '+m);process.exit(1);}}}};\n"
              + body)
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"node assertion failed:\n{r.stderr}{r.stdout}")

    def test_one_mode_at_a_time(self):  # INV-35
        # Exhaustively walk every toggle sequence of length <= 4 on 3 stems; after EACH step the
        # player must never have a mute AND a solo live at once.
        self._node(r"""
        const KINDS=['mute','solo'];
        function walk(stems,depth){
          const anyMute=stems.some(s=>s.mute),anySolo=stems.some(s=>s.solo);
          A(!(anyMute&&anySolo),'mute and solo live at once: '+JSON.stringify(stems));
          if(depth===0)return;
          for(let i=0;i<stems.length;i++)for(const k of KINDS)walk(P.toggleStem(stems,i,k),depth-1);
        }
        walk([{mute:false,solo:false},{mute:false,solo:false},{mute:false,solo:false}],4);
        """)

    def test_solo_resolves_gains(self):  # INV-36
        # With a solo live, audible == exactly the soloed set, regardless of mute flags.
        self._node(r"""
        let s=[{mute:true,solo:false},{mute:false,solo:true},{mute:true,solo:false}];
        let m=P.pgains(s);                       // muted[]: audible = !muted
        A(m[0]===true&&m[1]===false&&m[2]===true,'solo did not isolate stem 1: '+JSON.stringify(m));
        // two solos: both audible, the rest muted
        s=[{mute:false,solo:true},{mute:false,solo:false},{mute:false,solo:true}];
        m=P.pgains(s);
        A(m[0]===false&&m[1]===true&&m[2]===false,'two-solo set wrong: '+JSON.stringify(m));
        """)

    def test_mute_resolves_gains(self):  # INV-37
        self._node(r"""
        const s=[{mute:true,solo:false},{mute:false,solo:false},{mute:true,solo:false}];
        const m=P.pgains(s);
        A(m[0]===true&&m[1]===false&&m[2]===true,'mute did not resolve: '+JSON.stringify(m));
        const none=P.pgains([{mute:false,solo:false}]);
        A(none[0]===false,'an untouched stem must be audible');
        """)

    def test_seek_preserves_transport_and_mix(self):  # INV-38
        # solo a stem -> "seek while playing" -> the SAME one stem is still the only audible one AND
        # transport resumes. seekResult carries no stem state, so a seek cannot disturb the mix.
        self._node(r"""
        const s=[{mute:false,solo:false},{mute:false,solo:true},{mute:false,solo:false}];
        const before=P.pgains(s);
        const r=P.seekResult(50,96,true);          // was playing
        const after=P.pgains(s);
        A(JSON.stringify(before)===JSON.stringify(after),'seek disturbed the mix');
        A(r.resume===true,'seek-while-playing must resume');
        A(P.seekResult(50,96,false).resume===false,'seek-while-paused must stay paused');
        """)

    def test_seek_clamps(self):  # INV-39
        self._node(r"""
        A(P.seekResult(-5,96,true).t===0,'negative seek must clamp to 0');
        A(P.seekResult(150,96,true).t===96,'over-duration seek must clamp to dur');
        A(P.seekResult(50,96,true).t===50,'in-range seek must pass through');
        """)

    def test_simple_resets_mix(self):  # INV-40 — entering Simple resets to full mix (solo/mute is Detailed-only)
        self._node(r"""
        const s=[{mute:false,solo:true},{mute:true,solo:false},{mute:false,solo:false}];  // a solo AND a mute live
        const r=P.resetMix(s);
        A(r.every(x=>!x.mute&&!x.solo),'resetMix must clear every mute+solo: '+JSON.stringify(r));
        A(P.pgains(r).every(x=>x===false),'after resetMix every stem must be audible: '+JSON.stringify(P.pgains(r)));
        """)


# ── INV-31: resolveView — global remembered view helper (SPEC §B.15)
_VIEW_BLOCK = re.compile(r"/\* VIEW_LOGIC_START.*?VIEW_LOGIC_END \*/", re.S)


def _render_view_html():
    """Render any full-mode widget — the VIEW_LOGIC block is always present in the template."""
    tmp = Path(tempfile.mkdtemp(prefix="tc_view_"))
    core = {
        "duration_s": 48.0, "time_bins": [round(i * 1.0, 3) for i in range(48)], "tempo": 120,
        "energy": [0.5] * 48, "brightness": [0.5] * 48, "density": [0.4] * 48,
        "wobble_rate": [1.0] * 48, "stereo_width": [0.4] * 48,
        "energy_trend": 0.0, "brightness_trend": 0.0, "density_trend": 0.0,
        "stereo_width_trend": 0.0,
    }
    out = tmp / "widget.html"
    build_widget.build_html(core, {}, None, None, str(out), "View Test", build_widget.STRINGS)
    return out.read_text(encoding="utf-8")


@unittest.skipUnless(NODE, "node not installed — view state-machine tests need a JS engine")
class ResolveViewLogic(unittest.TestCase):
    """INV-31: execute the REAL extracted resolveView helper in node.

    The pure helper resolveView(hash, stored) is emitted between VIEW_LOGIC_START/VIEW_LOGIC_END
    markers in the rendered widget. We pull that block out of the HTML, run it in node, and assert
    the precedence rules: URL hash > stored preference > calm default (simple).
    """

    @classmethod
    def setUpClass(cls):
        html = _render_view_html()
        m = _VIEW_BLOCK.search(html)
        assert m, "VIEW_LOGIC_START/VIEW_LOGIC_END markers not found in the rendered widget"
        cls.tmp = Path(tempfile.mkdtemp(prefix="tc_viewjs_"))
        cls.mod = cls.tmp / "view_logic.js"
        cls.mod.write_text(m.group(0), encoding="utf-8")

    def _node(self, body):
        """Run `body` JS with the extracted helpers required as V; fail on non-zero exit."""
        js = (f"const V=require({json.dumps(str(self.mod))});\n"
              f"const A=(c,m)=>{{if(!c){{console.error('FAIL: '+m);process.exit(1);}}}};\n"
              + body)
        r = subprocess.run([NODE, "-e", js], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, f"node assertion failed:\n{r.stderr}{r.stdout}")

    def test_hash_detailed_returns_detailed(self):  # INV-31 — URL hash overrides stored
        self._node('A(V.resolveView("#detailed",null)==="detailed",\'#detailed should→detailed\');')

    def test_hash_full_returns_detailed(self):       # INV-31 — #full is an alias for Detailed
        self._node('A(V.resolveView("#full",null)==="detailed",\'#full should→detailed\');')

    def test_hash_simple_returns_simple(self):       # INV-31 — #simple overrides stored
        self._node('A(V.resolveView("#simple","detailed")==="simple",\'#simple should→simple\');')

    def test_stored_detailed_no_hash_returns_detailed(self):  # INV-31 — remembered preference
        self._node('A(V.resolveView("","detailed")==="detailed",\'stored detailed+no hash should→detailed\');')

    def test_stored_simple_no_hash_returns_simple(self):      # INV-31 — remembered preference
        self._node('A(V.resolveView("","simple")==="simple",\'stored simple+no hash should→simple\');')

    def test_no_hash_no_stored_returns_simple(self):          # INV-31 — calm-first-use default
        self._node('A(V.resolveView("",null)==="simple",\'no hash+no stored should→simple (calm default)\');')


if __name__ == "__main__":
    unittest.main()
