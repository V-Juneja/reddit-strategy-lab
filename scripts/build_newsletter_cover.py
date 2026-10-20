"""Build a project-local, editable SVG article cover without external assets."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/reddit-strategy-finder-cover.svg"

SVG = r"""<svg xmlns="http://www.w3.org/2000/svg" width="2048" height="683" viewBox="0 0 2048 683">
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#06102a"/><stop offset="1" stop-color="#07366e"/>
  </linearGradient>
  <pattern id="grid" width="84" height="68" patternUnits="userSpaceOnUse">
    <path d="M84 0H0V68" fill="none" stroke="#147cff" stroke-opacity=".2" stroke-width="1.4"/>
  </pattern>
  <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
    <feGaussianBlur stdDeviation="14" result="blur"/>
    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
  </filter>
</defs>
<rect width="2048" height="683" fill="url(#bg)"/>
<rect width="2048" height="683" fill="url(#grid)"/>
<g fill="none" stroke="#1688ff" stroke-width="2" opacity=".22">
  <path d="M0 168C180 102 276 205 458 140S742 84 908 145S1198 220 1362 136S1646 62 1816 138S1972 191 2048 144"/>
  <path d="M0 198C180 132 276 235 458 170S742 114 908 175S1198 250 1362 166S1646 92 1816 168S1972 221 2048 174" opacity=".55"/>
</g>
<text x="92" y="91" fill="#a8d8ff" font-family="monospace" font-size="22" font-weight="700" letter-spacing="3">PROBABLY OVERFIT  /  RESEARCH IN PROGRESS</text>

<!-- Original Reddit-inspired speech-bubble robot mark; not the official Reddit logo. -->
<g transform="translate(370 344)">
  <path d="M-91 88L-164 145L-143 67Z" fill="#ff5b35"/>
  <circle r="146" fill="#ff5b35" stroke="#ffba98" stroke-width="5"/>
  <path d="M47 -112L81 -188L113 -179" fill="none" stroke="#ffba98" stroke-width="13" stroke-linecap="round"/>
  <circle cx="119" cy="-177" r="17" fill="#ffba98"/>
  <circle cx="-54" cy="-7" r="16" fill="#fff7ef"/>
  <circle cx="39" cy="-7" r="16" fill="#fff7ef"/>
  <path d="M-55 54Q-7 101 42 51" fill="none" stroke="#fff7ef" stroke-width="13" stroke-linecap="round"/>
</g>
<text x="370" y="557" fill="#ffd8ca" font-family="monospace" font-size="22" font-weight="700" text-anchor="middle" letter-spacing="2">REDDIT POST</text>

<path d="M548 344H758" fill="none" stroke="#54baff" stroke-width="10"/>
<path d="M752 324L787 344L752 364Z" fill="#54baff"/>

<rect x="829" y="226" width="536" height="240" rx="24" fill="#071426" stroke="#55baff" stroke-width="4"/>
<text x="875" y="284" fill="#8ad7ff" font-family="monospace" font-size="24" font-weight="700" letter-spacing="1">RULES  →  PYTHON</text>
<text x="875" y="344" fill="#f1f5ff" font-family="monospace" font-size="23">if close[t] &lt; close[t-1]:</text>
<text x="875" y="390" fill="#a7e8bf" font-family="monospace" font-size="23">    signal = True</text>
<text x="875" y="436" fill="#f1f5ff" font-family="monospace" font-size="23">fill = next_open</text>
<text x="875" y="515" fill="#8ba5c3" font-family="monospace" font-size="17" letter-spacing="1">NO SAME-CLOSE MAGIC</text>

<path d="M1406 344H1539" fill="none" stroke="#8cf0bd" stroke-width="10"/>
<path d="M1533 324L1568 344L1533 364Z" fill="#8cf0bd"/>
<g fill="none" stroke="#9cf5c8" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" filter="url(#glow)">
  <path d="M1604 296C1597 282 1570 281 1561 297C1549 318 1611 319 1600 343C1593 360 1567 359 1558 345M1580 273V368" transform="translate(70 0)"/>
  <path d="M1604 296C1597 282 1570 281 1561 297C1549 318 1611 319 1600 343C1593 360 1567 359 1558 345M1580 273V368" transform="translate(150 0)"/>
  <path d="M1604 296C1597 282 1570 281 1561 297C1549 318 1611 319 1600 343C1593 360 1567 359 1558 345M1580 273V368" transform="translate(230 0)"/>
</g>
<text x="1900" y="366" fill="#d1ffe4" font-family="Arial,sans-serif" font-size="100" font-weight="700" text-anchor="middle">?</text>
<text x="1760" y="442" fill="#d1ffe4" font-family="monospace" font-size="21" font-weight="700" text-anchor="middle" letter-spacing="2">BACKTEST FIRST</text>

<text x="1024" y="633" fill="#d3eaff" font-family="monospace" font-size="27" font-weight="700" text-anchor="middle" letter-spacing="3">POST  →  RULES  →  TEST  →  REPORT</text>
</svg>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(SVG)
    print(OUT)


if __name__ == "__main__":
    main()
