"""各案の背景色・マーク主色を測り、コントラスト比と OKLCH を出す。

skill「ロゴ・マスコットアイコンの造形規格」の検収（シルエット対背景 3:1、OKLCH 帯）を
目視追認で済ませないための計測。値は 1024px 正規化後の画像から取る。
"""
import json, math, os
from collections import Counter
from PIL import Image

D = "/Users/macmini/Projects/viewport-deck/assets/applogo-nanobanana-20260830"
PROC = os.path.join(D, "proc")
KEEP = ["a-split", "b2-stack", "d2-fracture", "e-bracket", "f2-gate"]


def srgb_to_linear(c):
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rel_luminance(rgb):
    r, g, b = (srgb_to_linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(c1, c2):
    l1, l2 = rel_luminance(c1), rel_luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def to_oklch(rgb):
    r, g, b = (srgb_to_linear(v) for v in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    bb = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    C = math.hypot(a, bb)
    H = math.degrees(math.atan2(bb, a)) % 360
    return round(L, 3), round(C, 3), round(H, 1)


def quantize(im, step=24):
    """色を粗く量子化して代表色の出現頻度を数える。"""
    small = im.resize((160, 160), Image.LANCZOS)
    c = Counter()
    for px in small.getdata():
        c[tuple((v // step) * step + step // 2 for v in px[:3])] += 1
    return c


out = {}
for slug in KEEP:
    im = Image.open(os.path.join(PROC, f"{slug}-1024.png")).convert("RGBA")
    im = Image.alpha_composite(Image.new("RGBA", im.size, (255, 255, 255, 255)), im).convert("RGB")
    w, h = im.size
    # アイコン地の色 = 角丸マスクの内側で、かつマークが載らない上下端の中央寄り数点の中央値。
    # 四隅はマスクで白く抜けるので使わない。
    pts = [(w // 2, int(h * 0.045)), (int(w * 0.30), int(h * 0.045)),
           (int(w * 0.70), int(h * 0.045)), (w // 2, int(h * 0.955)),
           (int(w * 0.30), int(h * 0.955)), (int(w * 0.70), int(h * 0.955))]
    samples = sorted((im.getpixel(p) for p in pts), key=rel_luminance)
    bg = samples[len(samples) // 2]

    # マーク主色 = 背景から十分離れた色のうち最頻
    counts = quantize(im)
    mark = max((c for c in counts
                if sum(abs(c[i] - bg[i]) for i in range(3)) > 60),
               key=lambda c: counts[c], default=None)
    # 最明部 = 上位頻度色のうち最も明るいもの（光る部分の可読性確認用）
    top = [c for c, n in counts.most_common(12)]
    brightest = max(top, key=rel_luminance)

    out[slug] = {
        "bg_rgb": bg, "bg_oklch": to_oklch(bg),
        "mark_rgb": mark, "mark_oklch": to_oklch(mark) if mark else None,
        "brightest_rgb": brightest, "brightest_oklch": to_oklch(brightest),
        "contrast_mark_vs_bg": round(contrast(mark, bg), 2) if mark else None,
        "contrast_brightest_vs_bg": round(contrast(brightest, bg), 2),
    }

print(json.dumps(out, ensure_ascii=False, indent=2))
with open(os.path.join(D, "measure.json"), "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
