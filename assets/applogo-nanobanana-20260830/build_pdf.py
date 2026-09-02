"""採用案の比較 PDF（A4 横 1ページ）を作る。

上段: 案ごとに 大サイズ / 32px・16px 実寸 / コンセプト1行。
下段: 16px 検証と実測値、落選案とその理由。
日本語は標準 CID フォントでベクタのまま出す（ヒラギノは CFF で reportlab が埋め込めない）。
"""
import json, os
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

D = "/Users/macmini/Projects/viewport-deck/assets/applogo-nanobanana-20260830"
PROC, SHEET = os.path.join(D, "proc"), os.path.join(D, "sheet")
OUT = os.path.join(SHEET, "viewport-break-applogo-2026-08-30.pdf")

pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
JP = "HeiseiKakuGo-W5"

CANDIDATES = [
    ("a-split",     "A / SPLIT",    "面が縦に割れ、左右が別々の幅で止まる。切り替えの瞬間そのもの。"),
    ("b2-stack",    "B / STACK",    "幅の違う3本のバーが階段状に並ぶ。プリセット幅の一覧を表す。"),
    ("d2-fracture", "D / FRACTURE", "一枚の面が裂け、割れ目から光が抜ける。BREAK の直接的な抽象化。"),
    ("e-bracket",   "E / BRACKET",  "向き合う2つの塊が幅を挟み、その間に光が残る。幅を掴んで決める。"),
    ("f2-gate",     "F / GATE",     "枠の内側が奥へ抜ける。フレームの向こうに別の視界がある。"),
]

DROPPED = [
    ("B（第1案）", "16px でカードの重なりが潰れ、幅の違いが消えた"),
    ("C（第1案）", "開口の外に不要な斜めの破片が入り、何が開いているのか読めない"),
    ("C（第2案）", "円＋横線の形に戻り、却下済みの GeoLogo 案と同じ方向になった"),
    ("D（第1案）", "スラブと地の明度差が足りず、16px で全体が沈んだ"),
    ("F（第1案）", "アイコンの中にアイコンの二重構造。開口も中心からずれた"),
]

BG_PAGE = (0.976, 0.976, 0.980)
INK, SUB, LINE = (0.10, 0.11, 0.13), (0.42, 0.45, 0.50), (0.86, 0.87, 0.89)
NO_LINE_START = "。、）」』】〉》・ー？！"


def wrap_ja(c, text, size, width, font=JP):
    """幅で折り返しつつ、行頭禁則の約物を前の行にぶら下げる。"""
    lines, line = [], ""
    for ch in text:
        if c.stringWidth(line + ch, font, size) > width and line:
            if ch in NO_LINE_START:
                lines.append(line + ch); line = ""; continue
            lines.append(line); line = ch
        else:
            line += ch
    if line:
        lines.append(line)
    return lines


W, H = landscape(A4)
c = canvas.Canvas(OUT, pagesize=(W, H))

# 透明のままだとビューアによって黒地に見えるので、地は必ず塗る
c.setFillColorRGB(*BG_PAGE)
c.rect(0, 0, W, H, stroke=0, fill=1)

M = 36
c.setFillColorRGB(*INK)
c.setFont(JP, 18)
c.drawString(M, H - M - 12, "VIEWPORT BREAK — アプリアイコン案（抽象方向）")
c.setFillColorRGB(*SUB)
c.setFont(JP, 8.5)
c.drawString(M, H - M - 27,
             "nano-banana 生成 / 全案を 16px に実縮小して検証し、成立した5案のみ掲載 / 2026-08-30")
c.setStrokeColorRGB(*LINE)
c.setLineWidth(0.7)
c.line(M, H - M - 36, W - M, H - M - 36)

GAP = 14
COLW = (W - M * 2 - GAP * 4) / 5
top = H - M - 52

for i, (slug, title, concept) in enumerate(CANDIDATES):
    x = M + i * (COLW + GAP)
    y = top - COLW
    c.drawImage(ImageReader(f"{PROC}/{slug}-1024.png"), x, y, COLW, COLW, mask="auto")

    ty = y - 17
    c.setFillColorRGB(*INK)
    c.setFont(JP, 10.5)
    c.drawString(x, ty, title)

    # 32px / 16px は実寸、右端は 16px を拡大したもの
    sy = ty - 32
    c.drawImage(ImageReader(f"{PROC}/{slug}-32.png"), x, sy, 24, 24, mask="auto")
    c.drawImage(ImageReader(f"{PROC}/{slug}-16.png"), x + 30, sy + 4, 12, 12, mask="auto")
    c.drawImage(ImageReader(f"{PROC}/{slug}-16x16-zoom.png"), x + 50, sy, 24, 24, mask="auto")
    c.setFillColorRGB(*SUB)
    c.setFont(JP, 6)
    c.drawString(x, sy - 9, "32px実寸 / 16px実寸 / 16pxの拡大")

    cy = sy - 24
    c.setFillColorRGB(*INK)
    c.setFont(JP, 8)
    for ln in wrap_ja(c, concept, 8, COLW):
        c.drawString(x, cy, ln)
        cy -= 11

# ---- 中段: 推し1案 ----
ry0 = 262
c.setFillColorRGB(0.925, 0.937, 0.957)
c.roundRect(M, ry0 - 62, W - M * 2, 74, 6, stroke=0, fill=1)
c.drawImage(ImageReader(f"{PROC}/e-bracket-1024.png"), M + 14, ry0 - 52, 54, 54, mask="auto")
c.setFillColorRGB(*INK)
c.setFont(JP, 11)
c.drawString(M + 82, ry0 - 8, "推し: E / BRACKET")
c.setFont(JP, 8)
rec = ("16px でも括弧と中央の光が崩れず、5案で最も小さいサイズに強い。"
       "「幅を両側から挟んで決める」という操作そのものを形にしていて、"
       "分割画面アイコンや一覧アイコンに埋もれない固有の形をしている。"
       "大胆さを取るなら次点は D / FRACTURE。")
yy = ry0 - 24
for ln in wrap_ja(c, rec, 8, W - M * 2 - 96):
    c.drawString(M + 82, yy, ln)
    yy -= 11.5

# ---- 下段: 実測値と落選理由 ----
by = 150
c.setStrokeColorRGB(*LINE)
c.line(M, by + 16, W - M, by + 16)

half = (W - M * 2 - 28) / 2

c.setFillColorRGB(*INK)
c.setFont(JP, 9.5)
c.drawString(M, by, "実測（1024px 正規化後・地色と最明部）")
c.setFont(JP, 6.5)
c.setFillColorRGB(*SUB)
c.drawString(M, by - 11,
             "コントラスト比は最明部と地色。造形規格のシルエット下限 3:1 を全案が満たす。")

meas = json.load(open(os.path.join(D, "measure.json")))
rows = [("案", "地色 OKLCH (L/C)", "最明部との比", "判定")]
for slug, title, _ in CANDIDATES:
    m = meas[slug]
    L, C = m["bg_oklch"][0], m["bg_oklch"][1]
    ratio = m["contrast_brightest_vs_bg"]
    rows.append((title.split(" / ")[1], f"{L:.3f} / {C:.3f}", f"{ratio:.2f}:1",
                 "可" if ratio >= 3 else "不可"))

ry = by - 26
for r, row in enumerate(rows):
    c.setFont(JP, 7.5 if r else 7)
    c.setFillColorRGB(*(SUB if r == 0 else INK))
    for cx, txt in zip([M, M + 78, M + 190, M + 260], row):
        c.drawString(cx, ry, txt)
    ry -= 12

x2 = M + half + 28
c.setFillColorRGB(*INK)
c.setFont(JP, 9.5)
c.drawString(x2, by, "落選した案と理由")
ry = by - 15
for name, reason in DROPPED:
    c.setFillColorRGB(*INK)
    c.setFont(JP, 7.5)
    c.drawString(x2, ry, name)
    c.setFillColorRGB(*SUB)
    c.setFont(JP, 7)
    for ln in wrap_ja(c, reason, 7, half - 62):
        c.drawString(x2 + 58, ry, ln)
        ry -= 9.5
    ry -= 3.5

c.setFillColorRGB(*SUB)
c.setFont(JP, 6.5)
c.drawString(M, M - 12,
             "生成は nano-banana（gemini CLI 拡張）。文字は入れていない。"
             "既存アイコンの差し替えやコード変更は行っていない。")
c.showPage()
c.save()
print("PDF:", OUT, os.path.getsize(OUT), "bytes")
