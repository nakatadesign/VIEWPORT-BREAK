"""raw PNG を「同じ角丸正方形マスクをかけた 1024px アイコン」に揃え、検証用縮小を書き出す。

nanobanana は同じ指示でも「白余白の上の角丸プレート」「フルブリード」「アイコンの中に
アイコン」の3通りを返す。案ごとの見た目差が地の扱いの差に埋もれないよう、
実アイコン面だけを切り出したうえで全案に共通の squircle マスクをかけて比較条件を揃える。
どれを切るかは全 raw を目視した上での明示ポリシー（FULL_BLEED）で決める。
"""
import os
from PIL import Image, ImageDraw

D = "/Users/macmini/Projects/viewport-deck/assets/applogo-nanobanana-20260830"
RAW, PROC = os.path.join(D, "raw"), os.path.join(D, "proc")

# 四隅の色がそのままアイコン地になっている（=切り出さない）案
FULL_BLEED = {"c2-aperture", "d2-fracture"}

# 元画像の角丸が共通マスクより小さく、切り出すと外側の白が縁として残る案。
# 辺長に対する割合だけ内側に詰めて白縁を食わせる。
INSET = {"a-split": 0.035}

SLUGS = ["a-split", "b-stack", "b2-stack", "c-aperture", "c2-aperture",
         "d-fracture", "d2-fracture", "e-bracket", "f-gate", "f2-gate"]

TOL = 26          # 背景色との許容差（R+G+B の合計差）
CORNER_R = 0.2237 # macOS の角丸比（辺長に対する半径）


def content_bbox(im):
    """四隅の色から TOL 以上離れたピクセルの bounding box。無ければ None。"""
    w, h = im.size
    cs = [im.getpixel(p) for p in [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]]
    bg = tuple(sum(c[i] for c in cs) // 4 for i in range(3))
    sw = 256
    small = im.resize((sw, max(1, int(sw * h / w))), Image.LANCZOS)
    px = small.load()
    xs, ys = [], []
    for y in range(small.size[1]):
        for x in range(small.size[0]):
            r, g, b = px[x, y][:3]
            if abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2]) > TOL:
                xs.append(x); ys.append(y)
    if not xs:
        return None
    fx, fy = w / small.size[0], h / small.size[1]
    return (int(min(xs) * fx), int(min(ys) * fy), int(max(xs) * fx) + 1, int(max(ys) * fy) + 1)


def square_crop(im, box):
    """bbox の中心を保ち、画像からはみ出さない最大の正方形。余白は足さない。"""
    l, t, r, b = box
    cx, cy = (l + r) / 2, (t + b) / 2
    side = min(max(r - l, b - t), im.size[0], im.size[1])
    l2 = max(0, min(int(round(cx - side / 2)), im.size[0] - side))
    t2 = max(0, min(int(round(cy - side / 2)), im.size[1] - side))
    return (l2, t2, l2 + side, t2 + side)


def squircle_mask(size):
    """4倍解像度で描いて縮小し、角のジャギーを消したマスクを返す。"""
    ss = 4
    m = Image.new("L", (size * ss, size * ss), 0)
    ImageDraw.Draw(m).rounded_rectangle(
        [0, 0, size * ss - 1, size * ss - 1], radius=int(size * ss * CORNER_R), fill=255)
    return m.resize((size, size), Image.LANCZOS)


MASK = squircle_mask(1024)

for slug in SLUGS:
    src = os.path.join(RAW, f"{slug}.png")
    if not os.path.exists(src):
        continue
    im = Image.open(src).convert("RGB")
    if slug in FULL_BLEED:
        note = "フルブリード（切り出しなし）"
    else:
        box = content_bbox(im)
        if box is None:
            note = "アイコン面を検出できず原寸のまま"
        else:
            l, t, r, b = square_crop(im, box)
            k = int((r - l) * INSET.get(slug, 0))
            im = im.crop((l + k, t + k, r - k, b - k))
            note = f"アイコン面を切り出し -> {im.size[0]}x{im.size[1]}"

    base = im.resize((1024, 1024), Image.LANCZOS)
    base.putalpha(MASK)
    base.save(os.path.join(PROC, f"{slug}-1024.png"))
    for n in (32, 16):
        base.resize((n, n), Image.LANCZOS).save(os.path.join(PROC, f"{slug}-{n}.png"))
    base.resize((16, 16), Image.LANCZOS).resize((256, 256), Image.NEAREST).save(
        os.path.join(PROC, f"{slug}-16x16-zoom.png"))
    print(f"{slug}: {note}")
