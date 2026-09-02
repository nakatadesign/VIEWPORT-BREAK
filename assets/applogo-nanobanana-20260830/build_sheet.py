"""採用5案の比較シート PNG を作る。案ごとに 1024px 相当・32px・16px とコンセプト1行。

PDF もこの PNG を1ページに敷いて作るため、レイアウトの正本はここ1箇所にする。
"""
import json, os
from PIL import Image, ImageDraw, ImageFont

D = "/Users/macmini/Projects/viewport-deck/assets/applogo-nanobanana-20260830"
PROC, SHEET = os.path.join(D, "proc"), os.path.join(D, "sheet")

W3 = "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc"
W6 = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"
f = lambda p, s: ImageFont.truetype(p, s)

CANDIDATES = [
    ("a-split",     "A / SPLIT",    "面が縦に割れ、左右が別々の幅で止まる。切り替えの瞬間そのもの。"),
    ("b2-stack",    "B / STACK",    "幅の違う3本のバーが階段状に並ぶ。プリセット幅の一覧を表す。"),
    ("d2-fracture", "D / FRACTURE", "一枚の面が裂け、割れ目から光が抜ける。BREAK の直接的な抽象化。"),
    ("e-bracket",   "E / BRACKET",  "向き合う2つの塊が幅を挟み、その間に光が残る。幅を掴んで決める。"),
    ("f2-gate",     "F / GATE",     "枠の内側が奥へ抜ける。フレームの向こうに別の視界がある。"),
]

BG, INK, SUB, LINE = (247, 247, 249), (26, 28, 33), (108, 114, 127), (222, 224, 230)

M = 64                 # 外周マージン
ICON = 300             # 大サイズ表示
GAP = 34               # カラム間
COLW = ICON
HEAD = 150
CAP_H = 190            # コンセプト文＋小サイズの領域

Wpx = M * 2 + COLW * 5 + GAP * 4
Hpx = HEAD + ICON + CAP_H + M

img = Image.new("RGB", (Wpx, Hpx), BG)
d = ImageDraw.Draw(img)

d.text((M, 52), "VIEWPORT BREAK — アプリアイコン案（抽象方向）", font=f(W6, 40), fill=INK)
d.text((M, 104), "nano-banana 生成 / 16px で成立する案のみ掲載 / 2026-08-30",
       font=f(W3, 22), fill=SUB)
d.line([(M, HEAD - 18), (Wpx - M, HEAD - 18)], fill=LINE, width=2)


NO_LINE_START = "。、）」』】〉》・ー？！"


def wrap_ja(text, fnt, width, draw):
    """幅で折り返しつつ、行頭に来てはいけない約物を前の行へ送る。"""
    lines, line = [], ""
    for ch in text:
        if draw.textlength(line + ch, font=fnt) > width and line:
            if ch in NO_LINE_START:
                line += ch          # 約物は追い出さず前行にぶら下げる
                lines.append(line)
                line = ""
                continue
            lines.append(line)
            line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


def paste(im, box):
    img.paste(im, box, im if im.mode == "RGBA" else None)


for i, (slug, title, concept) in enumerate(CANDIDATES):
    x = M + i * (COLW + GAP)
    y = HEAD
    paste(Image.open(f"{PROC}/{slug}-1024.png").resize((ICON, ICON), Image.LANCZOS), (x, y))

    ty = y + ICON + 22
    d.text((x, ty), title, font=f(W6, 25), fill=INK)

    # 実寸の 32px / 16px を並べ、その右に 16px の拡大（ドット確認用）
    sy = ty + 38
    paste(Image.open(f"{PROC}/{slug}-32.png"), (x, sy))
    paste(Image.open(f"{PROC}/{slug}-16.png"), (x + 44, sy + 8))
    paste(Image.open(f"{PROC}/{slug}-16x16-zoom.png").resize((48, 48), Image.NEAREST),
          (x + 74, sy))
    d.text((x + 132, sy + 4), "32px", font=f(W3, 16), fill=SUB)
    d.text((x + 132, sy + 26), "16px", font=f(W3, 16), fill=SUB)

    # コンセプト1行（カラム幅で折り返す。行頭禁則の文字は前行に押し込む）
    cy = sy + 74
    fnt = f(W3, 19)
    for ln in wrap_ja(concept, fnt, COLW, d):
        d.text((x, cy), ln, font=fnt, fill=INK)
        cy += 27

img.save(f"{SHEET}/viewport-break-applogo-comparison.png")
print("PNG:", img.size)
