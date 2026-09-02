#!/usr/bin/env python3
"""案A「貫く線」のパラメータを振り、SVG と各サイズ PNG を書き出す。

マーク全体は canvas 1000 の中で上下 PAD を空けて収める。
- overshoot: 線が円から突き出る量（片側）
- ring: リング線幅
- bar: 貫く線の太さ
1000 canvas を 16px へ縮小するので 62.5 units = 1px。
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from build_design import build  # noqa: E402

ROOT = pathlib.Path(__file__).parent
GEOLOGO = "/Users/macmini/Apps/geologo/bin/geologo"
PAD = 40.0
SPAN = 1000.0 - PAD * 2  # マーク全体の高さ
SIZES = (16, 32, 48, 128)

# key: (overshoot, ring, bar)
VARIANTS = {
    "v1-tight-thin":   (80, 80, 72),
    "v2-tight-thick":  (80, 110, 104),
    "v3-mid-thin":     (130, 80, 72),
    "v4-mid-even":     (130, 100, 100),
    "v5-mid-bold":     (130, 100, 130),
    "v6-mid-thick":    (130, 120, 120),
    "v7-long-even":    (185, 100, 100),
    "v8-long-bold":    (185, 100, 130),
    "v9-long-thick":   (185, 125, 125),
}


def emit(name: str, overshoot: float, ring: float, bar: float) -> dict:
    r_outer = (SPAN - 2 * overshoot) / 2.0
    design = build(r_outer, ring, bar / 2.0, overshoot)
    dpath = ROOT / "designs" / f"{name}.json"
    dpath.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    spath = ROOT / "svg" / f"{name}.svg"
    out = subprocess.run(
        [GEOLOGO, "render", "--design", str(dpath), "--out", str(spath), "--json"],
        capture_output=True, text=True, check=True,
    )
    receipt = json.loads(out.stdout)

    for size in SIZES:
        for bg, tag in (("none", "alpha"), ("#FFFFFF", "white")):
            png = ROOT / "png" / f"{name}-{tag}-{size}.png"
            cmd = ["rsvg-convert", "-w", str(size), "-h", str(size), str(spath), "-o", str(png)]
            if bg != "none":
                cmd[1:1] = ["-b", bg]
            subprocess.run(cmd, check=True)
    return {
        "name": name, "overshoot": overshoot, "ring": ring, "bar": bar,
        "r_outer": r_outer,
        "ring_px_at_16": round(ring / 62.5, 2),
        "bar_px_at_16": round(bar / 62.5, 2),
        "overshoot_px_at_16": round(overshoot / 62.5, 2),
        "design_sha256": receipt["design_sha256"], "svg_sha256": receipt["output_sha256"],
        "counts": receipt["expected_counts"],
    }


if __name__ == "__main__":
    report = [emit(n, *p) for n, p in VARIANTS.items()]
    (ROOT / "sweep-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in report:
        print(f"{r['name']:16s} ring={r['ring_px_at_16']}px bar={r['bar_px_at_16']}px "
              f"overshoot={r['overshoot_px_at_16']}px @16")
