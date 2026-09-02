#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VIEWPORT BREAK — 確定ロゴ（master PNG）から配布用アイコン一式を派生させる。

master は無加工で assets/brand/master/ に置き、このスクリプトは **常にそこからだけ**
派生を作る。派生物を再入力にしない（世代劣化を避ける）。

  出力先: assets/brand/out/…（すべてこのスクリプトで再生成できる）
  実行:   python3 assets/brand/build_brand_assets.py

依存: Pillow。これは **デザイン時** の依存で、配布物にも packaging/build_dmg.sh の
実行時にも残らない（build_dmg.sh は生成済み PNG をコピーするだけ）。
"""
import hashlib
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
MASTER = os.path.join(HERE, "master", "viewport-break-logo-master-1200.png")
OUT = os.path.join(HERE, "out")

# master の同一性。差し替えたら意図的に更新する。
MASTER_SHA256 = "146f5da4d33df470db8544d4c610ac965471ef21ce9f1f9191399fdc742373e7"

BLACK = (0, 0, 0)
# アルファ抽出のしきい値。master は純黒地なので、これ未満の輝度は地とみなす。
ALPHA_FLOOR = 6
# 角丸版の角丸半径（辺長比）。macOS 以外の「丸角の四角」系で共通に使う。
CORNER_R = 0.2237
# macOS Big Sur 以降のアイコングリッド: 1024 キャンバスに 824 の本体を centered。
MACOS_BODY = 824.0 / 1024.0

WORDMARK = "VIEWPORT BREAK"
FONT_CANDIDATES = [
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]

# 高解像で組んでから縮小するための内部作業解像度。
WORK = 2048

# 小サイズで縮小したとき、細いハイライトが平均されて沈む。sRGB 値をそのまま
# 平均すると物理的に暗くなりすぎるので、**リニア光で縮小**したうえで、
# 最大輝度が TARGET_PEAK に届くまでゲインをかけて持ち上げる。
# 128px 以上では素のままで届くので、実質 48px 以下にだけ効く。
TARGET_PEAK = 250.0
MAX_GAIN = 4.0


def log(msg):
    print(msg, flush=True)


# --------------------------------------------------------------- master → mark
def load_mark():
    """master から「地の黒を抜いた」ストレートアルファのマークを切り出す。

    master は純黒地にガラスの反射だけが乗った絵なので、黒地 = 何も無い。
    つまり master の RGB は既に「アルファ乗算済み」の状態で、輝度がそのまま
    被覆率になる。輝度をアルファに、RGB を輝度で割り戻してストレートアルファへ直す。
    """
    im = Image.open(MASTER).convert("RGB")
    w, h = im.size
    px = im.load()

    rgba = Image.new("RGBA", (w, h))
    dst = rgba.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            # Rec.709 輝度。ガラスの反射は無彩色なので実質 max とほぼ同じだが、
            # 縁の色付きハイライトを潰さないため輝度で取る。
            lum = (2126 * r + 7152 * g + 722 * b) // 10000
            if lum < ALPHA_FLOOR:
                dst[x, y] = (0, 0, 0, 0)
                continue
            a = 255 if lum > 255 else lum
            # 割り戻し（unpremultiply）。白飛びは 255 で頭打ち。
            s = 255.0 / a
            dst[x, y] = (min(255, int(r * s)), min(255, int(g * s)),
                         min(255, int(b * s)), a)
            if x < minx: minx = x
            if x > maxx: maxx = x
            if y < miny: miny = y
            if y > maxy: maxy = y

    mark = rgba.crop((minx, miny, maxx + 1, maxy + 1))
    log("  mark bbox = x[%d..%d] y[%d..%d]  %dx%d" %
        (minx, maxx, miny, maxy, mark.width, mark.height))
    return mark


def fit_mark(mark, canvas, scale):
    """マークの長辺が canvas*scale になるよう縮小し、canvas 中央へ置いた RGBA を返す。

    master のマークは元画像の中で中心からずれているので、bbox 基準で置き直す。
    これで角丸マスクに対する余白（セーフエリア）が left/right/top/bottom で揃う。
    """
    target = canvas * scale
    k = target / max(mark.width, mark.height)
    nw, nh = max(1, round(mark.width * k)), max(1, round(mark.height * k))
    small = mark.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    out.paste(small, ((canvas - nw) // 2, (canvas - nh) // 2), small)
    return out



# --------------------------------------------------- 縮小（リニア光）とゲイン
def _srgb_to_linear_table():
    t = np.empty(256, dtype=np.float32)
    for v in range(256):
        c = v / 255.0
        t[v] = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return t


_S2L = _srgb_to_linear_table()


def _l2s(a):
    a = np.clip(a, 0.0, 1.0)
    out = np.where(a <= 0.0031308, a * 12.92, 1.055 * (a ** (1 / 2.4)) - 0.055)
    return np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)


def resize_rgb_linear(rgb, size):
    """sRGB の RGB 画像をリニア光で縮小する。

    細い高輝度のハイライトを sRGB 値のまま平均すると、実際の光量より暗くなる。
    ガラスの縁だけで形を見せるこのマークでは、それがそのまま小サイズの潰れになる。
    """
    lin = _S2L[np.asarray(rgb.convert("RGB"))]
    chans = []
    for c in range(3):
        band = Image.fromarray(np.ascontiguousarray(lin[..., c]))  # float32 → mode "F"
        chans.append(np.asarray(band.resize((size, size), Image.LANCZOS),
                                dtype=np.float32))
    return Image.fromarray(_l2s(np.stack(chans, axis=-1)), mode="RGB")


def apply_gain(rgb):
    """最大輝度が TARGET_PEAK に届くまで一様にゲインをかける（上限 MAX_GAIN）。"""
    a = np.asarray(rgb, dtype=np.float32)
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    peak = float(lum.max())
    if peak <= 1.0:
        return rgb, 1.0
    gain = min(MAX_GAIN, max(1.0, TARGET_PEAK / peak))
    if gain <= 1.0001:
        return rgb, 1.0
    return Image.fromarray(np.clip(a * gain, 0, 255).astype(np.uint8), mode="RGB"), gain


GAIN_LOG = {}


def finish(body_rgb, shape_alpha, size, tag):
    """WORK 解像度の「黒地 + マーク」を目標サイズへ落とし、輪郭マスクを付ける。"""
    small = resize_rgb_linear(body_rgb, size)
    small, gain = apply_gain(small)
    if gain > 1.0001:
        GAIN_LOG["%s@%d" % (tag, size)] = round(gain, 2)
    out = small.convert("RGBA")
    if shape_alpha is not None:
        out.putalpha(shape_alpha.resize((size, size), Image.LANCZOS))
    return out


# ------------------------------------------------------------------- 形状マスク
def rounded_mask(size, radius_ratio, supersample=4):
    n = size * supersample
    r = int(round(n * radius_ratio))
    m = Image.new("L", (n, n), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, n - 1, n - 1), radius=r, fill=255)
    return m.resize((size, size), Image.LANCZOS)


def squircle_mask(size, exponent=5.0, supersample=4):
    """macOS の本体形状に近い superellipse。|x|^n + |y|^n <= 1。"""
    n = size * supersample
    t = (np.arange(n, dtype=np.float64) + 0.5) / (n / 2.0) - 1.0
    p = np.abs(t) ** exponent
    inside = (p[:, None] + p[None, :]) <= 1.0
    m = Image.fromarray((inside * 255).astype(np.uint8), mode="L")
    return m.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------------- 合成 3 種
def render_rounded(mark, size, scale):
    """黒の角丸正方形にマークを置く。地が明暗どちらでも輪郭が立つ版。

    Chrome ツールバー・favicon・PWA の通常アイコンはこれ。
    ガラスの反射は明色なので、白い地に透過で置くと消える。黒地を持たせる。
    """
    body = Image.new("RGBA", (WORK, WORK), BLACK + (255,))
    body.alpha_composite(fit_mark(mark, WORK, scale))
    return finish(body, rounded_mask(WORK, CORNER_R), size, "rounded")


def render_fullbleed(mark, size, scale):
    """角丸なしの黒ベタ正方形。マスクを OS 側がかける iOS / maskable 用。"""
    body = Image.new("RGBA", (WORK, WORK), BLACK + (255,))
    body.alpha_composite(fit_mark(mark, WORK, scale))
    return finish(body, None, size, "fullbleed")


def render_macos(mark, size, scale):
    """macOS のアイコングリッド: 1024 中 824 の squircle 本体 + 周囲の余白。"""
    body_px = int(round(WORK * MACOS_BODY))
    body = Image.new("RGBA", (body_px, body_px), BLACK + (255,))
    body.alpha_composite(fit_mark(mark, body_px, scale))
    canvas = Image.new("RGBA", (WORK, WORK), BLACK + (255,))
    off = (WORK - body_px) // 2
    canvas.paste(body, (off, off))
    shape = Image.new("L", (WORK, WORK), 0)
    shape.paste(squircle_mask(body_px), (off, off))
    return finish(canvas, shape, size, "macos")


def render_transparent(mark, size, scale):
    """地なしのマーク単体。暗い面に重ねる用途専用。

    黒地に置いたときと同じ見えになるよう、乗算済み（= master と同じ状態）で
    リニア縮小してから、アルファで割り戻す。
    """
    placed = fit_mark(mark, WORK, scale)
    pre = Image.new("RGBA", (WORK, WORK), (0, 0, 0, 255))
    pre.alpha_composite(placed)
    rgb = resize_rgb_linear(pre.convert("RGB"), size)
    alpha = placed.getchannel("A").resize((size, size), Image.LANCZOS)
    a = np.asarray(alpha, dtype=np.float32)
    c = np.asarray(rgb, dtype=np.float32)
    scale_up = np.where(a > 0, 255.0 / np.maximum(a, 1.0), 0.0)[..., None]
    out = np.clip(c * scale_up, 0, 255).astype(np.uint8)
    im = Image.fromarray(out, mode="RGB").convert("RGBA")
    im.putalpha(alpha)
    return im


# ------------------------------------------------------------------------ OGP
def load_font(px):
    for path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        for idx in (0, 1, 2, 3):
            try:
                f = ImageFont.truetype(path, px, index=idx)
                if "bold" in (f.getname()[1] or "").lower():
                    return f
            except Exception:
                break
        try:
            return ImageFont.truetype(path, px)
        except Exception:
            continue
    return ImageFont.load_default()


def render_share(mark, w, h):
    """OGP / Twitter card。黒地にマーク + ワードマーク。"""
    ss = 2
    W, H = w * ss, h * ss
    im = Image.new("RGB", (W, H), BLACK)
    mark_px = int(H * 0.56)
    m = fit_mark(mark, mark_px, 1.0)
    # 左にマーク、右にワードマーク。全体を光学的に中央へ。
    font = load_font(int(H * 0.115))
    d = ImageDraw.Draw(im)
    tb = d.textbbox((0, 0), WORDMARK, font=font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    gap = int(H * 0.07)
    total = mark_px + gap + tw
    x0 = (W - total) // 2
    im.paste(m, (x0, (H - mark_px) // 2), m)
    d.text((x0 + mark_px + gap - tb[0], (H - th) // 2 - tb[1]),
           WORDMARK, font=font, fill=(238, 244, 246))
    return im.resize((w, h), Image.LANCZOS)




# ----------------------------------------------------------------------- 出力
MANIFEST = []


def save(im, relpath):
    path = os.path.join(OUT, relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path, optimize=True)
    with open(path, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    MANIFEST.append({"path": "assets/brand/out/" + relpath.replace(os.sep, "/"),
                     "size": list(im.size), "mode": im.mode,
                     "bytes": os.path.getsize(path), "sha256": digest})
    log("    %-52s %5dx%-5d %7d B" % (relpath, im.size[0], im.size[1],
                                      os.path.getsize(path)))
    return path


def main():
    with open(MASTER, "rb") as f:
        got = hashlib.sha256(f.read()).hexdigest()
    if got != MASTER_SHA256:
        log("master の sha256 が一致しない。期待 %s / 実際 %s" % (MASTER_SHA256, got))
        return 1

    log("master: %s" % MASTER)
    mark = load_mark()

    # -- 1. Chrome 拡張 -----------------------------------------------------
    # 16px まで潰れないよう、小さいサイズほどマークを大きく取る。
    log("  [1] Chrome 拡張アイコン")
    for s, sc in ((16, 0.82), (32, 0.76), (48, 0.72), (128, 0.70)):
        save(render_rounded(mark, s, sc), "extension/icon%d.png" % s)

    # -- 2. macOS .icns 用 iconset -----------------------------------------
    log("  [2] macOS iconset（10 表現）")
    for s, name in ((16, "icon_16x16"), (32, "icon_16x16@2x"), (32, "icon_32x32"),
                    (64, "icon_32x32@2x"), (128, "icon_128x128"), (256, "icon_128x128@2x"),
                    (256, "icon_256x256"), (512, "icon_256x256@2x"), (512, "icon_512x512"),
                    (1024, "icon_512x512@2x")):
        save(render_macos(mark, s, 0.72), "macos/AppIcon.iconset/%s.png" % name)

    # -- 3. iOS / iPadOS ----------------------------------------------------
    # iOS はアルファ不可・角丸不可（OS がマスクする）。黒ベタ全面で出す。
    log("  [3] iOS / iPadOS")
    for s, name in ((1024, "AppIcon-1024"), (180, "AppIcon-60@3x"), (167, "AppIcon-83.5@2x"),
                    (152, "AppIcon-76@2x"), (120, "AppIcon-60@2x"), (120, "AppIcon-40@3x"),
                    (87, "AppIcon-29@3x"), (80, "AppIcon-40@2x"), (76, "AppIcon-76"),
                    (60, "AppIcon-20@3x"), (58, "AppIcon-29@2x"), (40, "AppIcon-20@2x"),
                    (40, "AppIcon-40"), (29, "AppIcon-29"), (20, "AppIcon-20")):
        save(render_fullbleed(mark, s, 0.70).convert("RGB"), "ios/%s.png" % name)

    # -- 4. web: favicon / apple-touch / PWA --------------------------------
    log("  [4] favicon / apple-touch-icon / PWA")
    for s, sc in ((16, 0.82), (32, 0.76), (48, 0.72), (96, 0.72), (192, 0.70), (512, 0.70)):
        save(render_rounded(mark, s, sc), "web/favicon-%dx%d.png" % (s, s))
    # .ico は 16/32/48 を 1 ファイルへ。
    ico_path = os.path.join(OUT, "web", "favicon.ico")
    os.makedirs(os.path.dirname(ico_path), exist_ok=True)
    render_rounded(mark, 256, 0.72).save(
        ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    with open(ico_path, "rb") as f:
        MANIFEST.append({"path": "assets/brand/out/web/favicon.ico",
                         "size": [48, 48], "mode": "ICO(16/32/48)",
                         "bytes": os.path.getsize(ico_path),
                         "sha256": hashlib.sha256(f.read()).hexdigest()})
    log("    %-52s %5s        %7d B" % ("web/favicon.ico", "16/32/48",
                                        os.path.getsize(ico_path)))
    # apple-touch-icon は iOS が角丸をかけるので全面黒ベタ。
    save(render_fullbleed(mark, 180, 0.70).convert("RGB"), "web/apple-touch-icon.png")
    save(render_rounded(mark, 192, 0.70), "web/pwa-192.png")
    save(render_rounded(mark, 512, 0.70), "web/pwa-512.png")
    # maskable は中央 80% 径の円だけが保証される。内接正方形は辺 0.8/√2 ≒ 0.566。
    save(render_fullbleed(mark, 192, 0.55), "web/pwa-maskable-192.png")
    save(render_fullbleed(mark, 512, 0.55), "web/pwa-maskable-512.png")

    # -- 5. OGP / Twitter card ---------------------------------------------
    log("  [5] OGP / Twitter card")
    save(render_share(mark, 1200, 630), "share/og-image-1200x630.png")
    save(render_share(mark, 1200, 600), "share/twitter-card-1200x600.png")

    # -- 6. 素の 2 版（黒地 / 透過） ---------------------------------------
    log("  [6] 黒地版 / 透過版")
    for s in (1024, 512, 256):
        save(render_fullbleed(mark, s, 0.78).convert("RGB"),
             "logo/viewport-break-onblack-%d.png" % s)
        save(render_transparent(mark, s, 0.94),
             "logo/viewport-break-transparent-%d.png" % s)

    with open(os.path.join(OUT, "MANIFEST.json"), "w") as f:
        json.dump({"master": {"path": "assets/brand/master/viewport-break-logo-master-1200.png",
                              "sha256": MASTER_SHA256},
                   "files": MANIFEST}, f, ensure_ascii=False, indent=2)
    if GAIN_LOG:
        log("  小サイズの輝度ゲイン: %s" % json.dumps(GAIN_LOG, sort_keys=True))
    log("  合計 %d ファイル → %s" % (len(MANIFEST), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
