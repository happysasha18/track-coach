#!/usr/bin/env python3
"""Generate tempo_changes.als — a tiny synthetic Ableton project with tempo automation.

An .als is a gzip-compressed XML document. This builds the smallest tree parse_als.py needs to
extract arrangement tempo changes: a MainTrack whose Tempo parameter carries a FloatEvent
automation envelope. The events step 120 → 140 → 90 BPM, so parse_als should return three
tempo_changes with piecewise-integrated seconds. Regenerate with:
    python3 tests/fixtures/synthetic/make_tempo_als.py
"""
import gzip
from pathlib import Path

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12.0_12120" Creator="track-coach synthetic fixture">
  <LiveSet>
    <Tempo><Manual Value="120"/></Tempo>
    <MainTrack>
      <DeviceChain>
        <Mixer>
          <Tempo>
            <Manual Value="120"/>
            <AutomationTarget Id="30001"/>
          </Tempo>
        </Mixer>
        <AutomationEnvelopes>
          <Envelopes>
            <AutomationEnvelope>
              <EnvelopeTarget><PointeeId Value="30001"/></EnvelopeTarget>
              <Automation>
                <Events>
                  <FloatEvent Time="0" Value="120"/>
                  <FloatEvent Time="32" Value="140"/>
                  <FloatEvent Time="64" Value="90"/>
                </Events>
              </Automation>
            </AutomationEnvelope>
          </Envelopes>
        </AutomationEnvelopes>
      </DeviceChain>
    </MainTrack>
  </LiveSet>
</Ableton>
"""

if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "tempo_changes.als"
    with gzip.open(out, "wb") as f:
        f.write(XML.encode("utf-8"))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
