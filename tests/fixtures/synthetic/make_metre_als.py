#!/usr/bin/env python3
"""Generate metre_changes.als — a tiny synthetic Ableton project for the metre-change test.

An .als is a gzip-compressed XML document. This builds the smallest tree parse_als.py needs to
extract arrangement time-signature changes: a MainTrack whose TimeSignature parameter carries an
automation envelope of EnumEvents. The enum encoding is value = log2(den)*99 + (num-1), so
404 = 9/16, 309 = 13/8, 201 = 4/4 (the same ground truth the unit tests in test_parse_als.py pin).

The events reproduce the sequence 9/16 -> 13/8 -> 4/4, which the integration test asserts. This
fixture replaces the need for any private, real .als on disk: the metre-change test now runs on
every machine. Regenerate with:  python3 tests/fixtures/synthetic/make_metre_als.py
"""
import gzip
from pathlib import Path

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Ableton MajorVersion="5" MinorVersion="12.0_12120" Creator="track-coach synthetic fixture">
  <LiveSet>
    <Tempo><Manual Value="120"/></Tempo>
    <TimeSignature>
      <TimeSignatures>
        <RemoteableTimeSignature>
          <Numerator Value="9"/>
          <Denominator Value="16"/>
        </RemoteableTimeSignature>
      </TimeSignatures>
    </TimeSignature>
    <MainTrack>
      <DeviceChain>
        <Mixer>
          <TimeSignature>
            <Manual Value="404"/>
            <AutomationTarget Id="20001"/>
          </TimeSignature>
        </Mixer>
        <AutomationEnvelopes>
          <Envelopes>
            <AutomationEnvelope>
              <EnvelopeTarget><PointeeId Value="20001"/></EnvelopeTarget>
              <Automation>
                <Events>
                  <EnumEvent Time="0" Value="404"/>
                  <EnumEvent Time="36" Value="309"/>
                  <EnumEvent Time="80" Value="201"/>
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
    out = Path(__file__).resolve().parent / "metre_changes.als"
    with gzip.open(out, "wb") as f:
        f.write(XML.encode("utf-8"))
    print(f"wrote {out} ({out.stat().st_size} bytes)")
