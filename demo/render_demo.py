"""Render a demo screen recording of the CLI from its real output.

Every line shown is copied from `demo/demo_output.txt` and `demo/scan_output.txt`,
which are the unedited stdout of the two commands. This is a capture of the tool
running, not a mock-up.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
FPS = 12
BG = (14, 17, 22)
BAR = (30, 34, 42)
FG = (222, 228, 236)
DIM = (130, 140, 155)
GREEN = (110, 210, 140)
ACCENT = (120, 190, 255)
WARN = (245, 190, 110)

FONT_PATH = "/usr/local/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono.ttf"
BOLD_PATH = "/usr/local/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSansMono-Bold.ttf"

root = Path(__file__).resolve().parent.parent
demo_lines = (root / "demo" / "demo_output.txt").read_text(encoding="utf-8").splitlines()
scan_lines = (root / "demo" / "scan_output.txt").read_text(encoding="utf-8").splitlines()
md_lines = (root / "data" / "sample_scan.md").read_text(encoding="utf-8").splitlines()

font = ImageFont.truetype(FONT_PATH, 17)
font_b = ImageFont.truetype(BOLD_PATH, 17)
font_title = ImageFont.truetype(BOLD_PATH, 46)
font_sub = ImageFont.truetype(FONT_PATH, 21)


def chrome(draw: ImageDraw.ImageDraw, title: str) -> None:
    draw.rectangle([0, 0, W, 34], fill=BAR)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = 20 + i * 22
        draw.ellipse([cx, 11, cx + 12, 23], fill=color)
    draw.text((110, 9), title, font=font, fill=DIM)


def draw_lines(draw, lines, y0=52, color=FG, x=24, line_h=22):
    y = y0
    for line, col in lines:
        draw.text((x, y), line, font=font, fill=col)
        y += line_h
    return y


def colorize(line: str):
    if line.startswith("[agent]"):
        return (line, DIM)
    if line.startswith("wrote "):
        return (line, GREEN)
    if line.startswith("# ") or line.startswith("**Regime"):
        return (line, ACCENT)
    if line.startswith("|"):
        return (line, FG)
    if line.startswith("Regime is"):
        return (line, WARN)
    if line.startswith("api:"):
        return (line, DIM)
    return (line, FG)


def wrap(lines, width=118):
    out = []
    for line in lines:
        if len(line) <= width:
            out.append(line)
        else:
            out.extend(textwrap.wrap(line, width))
    return out


screens: list[dict] = []

# 1. title
screens.append({"kind": "title", "dur": 4.0})

# 2. offline demo
cmd1 = "$ PYTHONPATH=src python3 -m cmc_radar.cli demo      # no API key, no network"
screens.append(
    {
        "kind": "term",
        "title": "cmc-market-radar - offline demo",
        "cmd": cmd1,
        "lines": wrap(demo_lines, 112)[:26],
        "dur": 1.2,
        "per_line": 0.30,
    }
)

# 3. live scan
cmd2 = "$ PYTHONPATH=src python3 -m cmc_radar.cli scan --top 100 --watch BTC,ETH,SOL,HYPE"
lines2 = wrap(scan_lines, 112)[:24]
screens.append({"kind": "term", "title": "cmc-market-radar - live scan on the CMC Pro API", "cmd": cmd2, "lines": lines2, "dur": 1.2, "per_line": 0.42})

# 4. markdown brief
lines4 = wrap(md_lines, 112)[:24]
screens.append({"kind": "term", "title": "data/sample_scan.md - the brief it writes", "cmd": "$ cat data/sample_scan.md | head -24", "lines": lines4, "dur": 1.0, "per_line": 0.24})

# 5. closing
screens.append({"kind": "end", "dur": 5.0})


def render_title(draw):
    draw.text((80, 230), "CMC Market Radar", font=font_title, fill=FG)
    draw.text((80, 300), "Cross-sectional crypto market intelligence", font=font_sub, fill=ACCENT)
    draw.text((80, 336), "on the CoinMarketCap Pro API", font=font_sub, fill=ACCENT)
    draw.text((80, 420), "zero dependencies  ·  12 unit tests  ·  read-only agent  ·  2 credits per scan", font=font, fill=DIM)
    draw.text((80, 470), "github.com/nvimuno-dot/cmc-market-radar", font=font, fill=GREEN)


def render_end(draw):
    draw.text((80, 210), "What it does", font=font_title, fill=FG)
    rows = [
        ("1  Universe", "top-N assets, liquidity floor, stablecoins excluded"),
        ("2  Score", "momentum + volume anomaly + cohort-relative liquidity"),
        ("3  Regime", "risk-on / neutral / risk-off x btc-led / alt-led"),
        ("4  Decide", "read-only agent emits JSON decisions with evidence"),
        ("5  Brief", "Markdown table + three sentences for the desk note"),
    ]
    y = 300
    for label, text in rows:
        draw.text((80, y), label, font=font_b, fill=ACCENT)
        draw.text((280, y), text, font=font, fill=FG)
        y += 40
    draw.text((80, 560), "CoinMarketCap endpoints: listings/latest · global-metrics/quotes/latest · quotes/latest · trending · derivatives",
              font=font, fill=DIM)


def frames_for(screen):
    dur = screen["dur"]
    if screen["kind"] in {"title", "end"}:
        return int(dur * FPS)
    reveal = dur + len(screen["lines"]) * screen["per_line"]
    return int(reveal * FPS)


writer = imageio.get_writer(str(root / "demo" / "cmc-market-radar-demo.mp4"), fps=FPS, quality=7, macro_block_size=None)
total = 0
for screen in screens:
    n = frames_for(screen)
    if screen["kind"] == "term":
        cmd_chars = len(screen["cmd"])
        type_time = 0.55
    for i in range(n):
        t = i / FPS
        img = Image.new("RGB", (W, H), BG)
        draw = ImageDraw.Draw(img)
        if screen["kind"] == "title":
            chrome(draw, "cmc-market-radar")
            render_title(draw)
        elif screen["kind"] == "end":
            chrome(draw, "cmc-market-radar")
            render_end(draw)
        else:
            chrome(draw, screen["title"])
            # prompt typing
            shown = min(cmd_chars, int(cmd_chars * min(1.0, t / type_time)))
            prompt_color = GREEN
            draw.text((24, 52), screen["cmd"][:shown], font=font, fill=prompt_color)
            visible = max(0, int((t - type_time - 0.25) / screen["per_line"]) + 1)
            lines = [colorize(l) for l in screen["lines"][:visible]]
            draw_lines(draw, lines, y0=92)
            # caret
            if int(t * 2) % 2 == 0:
                cy = 92 + len(lines) * 22
                draw.rectangle([24, cy + 2, 34, cy + 18], fill=FG)
        writer.append_data(np.array(img))
        total += 1
writer.close()
print(f"wrote demo/cmc-market-radar-demo.mp4 frames={total} seconds={total/FPS:.1f}")
