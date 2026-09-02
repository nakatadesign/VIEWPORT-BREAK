#!/usr/bin/env python3
"""候補比較シートを PIL で組む。

行構成: 128px 一覧 / 32px 4倍拡大 / 16px 8倍拡大 / 16px 実寸。
拡大は最近傍固定。実際に縮小されたピクセルだけを見て判断するため、
リサンプルで見た目を良くしない。
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).parent
FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_R = "/System/Library/Fonts/Supplemental/Arial.ttf"
CELL = 136
GAP = 10


def load(name: str, bg: str, size: int) -> Image.Image:
    return Image.open(ROOT / "png" / f"{name}-{bg}-{size}.png").convert("RGB")


def cell(img: Image.Image, box: int) -> Image.Image:
    if img.width != box:
        img = img.resize((box, box), Image.NEAREST)
    return img


def build(names, out: pathlib.Path, bg="white", sheet_bg=(238, 238, 238),
          fg=(17, 17, 17), title="", subtitle=""):
    f_title = ImageFont.truetype(FONT, 30)
    f_head = ImageFont.truetype(FONT, 17)
    f_lab = ImageFont.truetype(FONT_R, 13)
    f_row = ImageFont.truetype(FONT, 15)

    rows = [("128px", 128, CELL), ("32px (×4)", 32, CELL),
            ("16px (×8)", 16, CELL), ("16px 実寸", 16, 16)]
    left = 120
    top = 96 if title else 40
    label_h = 22
    width = left + len(names) * (CELL + GAP) + GAP
    height = top + sum(max(r[2], 16) + GAP + 6 for r in rows) + label_h + 30

    sheet = Image.new("RGB", (width, height), sheet_bg)
    d = ImageDraw.Draw(sheet)
    if title:
        d.text((GAP + 10, 26), title, font=f_title, fill=fg)
        d.text((GAP + 10, 62), subtitle, font=f_lab, fill=(110, 110, 110))

    # 候補名ヘッダ
    for i, n in enumerate(names):
        x = left + i * (CELL + GAP)
        d.text((x, top - label_h), n, font=f_lab, fill=(90, 90, 90))

    y = top
    for row_label, size, box in rows:
        d.text((GAP + 10, y + max(box, 16) // 2 - 8), row_label, font=f_row, fill=fg)
        for i, n in enumerate(names):
            x = left + i * (CELL + GAP)
            img = cell(load(n, bg, size), box)
            sheet.paste(img, (x + (CELL - box) // 2, y))
        y += max(box, 16) + GAP + 6

    d.text((GAP + 10, height - 24), subtitle if not title else "", font=f_lab, fill=fg)
    sheet.save(out)
    print(out, sheet.size)
    return sheet


if __name__ == "__main__":
    build(sys.argv[2:], pathlib.Path(sys.argv[1]))
