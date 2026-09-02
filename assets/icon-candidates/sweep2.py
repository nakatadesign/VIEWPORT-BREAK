#!/usr/bin/env python3
"""2巡目: 16px のピクセルグリッドへ整数で乗るよう線幅・突き出し・余白をスナップする。

16px 換算では 62.5 units = 1px。直線は円弧と違いエッジがグリッドに乗るか否かで
くっきりさが大きく変わるため、bar 幅・overshoot・pad を 1px の整数倍に置く。
"""
import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from build_design import build  # noqa: E402

ROOT = pathlib.Path(__file__).parent
GEOLOGO = "/Users/macmini/Apps/geologo/bin/geologo"
U = 62.5  # 16px 時の 1px 相当
SIZES = (16, 32, 48, 128)

# key: (pad_px, overshoot_px, ring_px, bar_px)  ※すべて16px換算
VARIANTS = {
    "a-p0-o2-r15-b2":   (0.0, 2.0, 1.5, 2.0),
    "b-p0-o2-r17-b2":   (0.0, 2.0, 1.7, 2.0),
    "c-p0-o2-r2-b2":    (0.0, 2.0, 2.0, 2.0),
    "d-p0-o3-r17-b2":   (0.0, 3.0, 1.7, 2.0),
    "e-p0-o25-r17-b2":  (0.0, 2.5, 1.7, 2.0),
    "f-p0-o2-r17-b25":  (0.0, 2.0, 1.7, 2.5),
    "g-p1-o2-r17-b2":   (1.0, 2.0, 1.7, 2.0),
    "h-p1-o25-r15-b2":  (1.0, 2.5, 1.5, 2.0),
    "i-p0-o2-r2-b25":   (0.0, 2.0, 2.0, 2.5),
}


def emit(name, pad_px, overshoot_px, ring_px, bar_px):
    pad, overshoot, ring, bar = (v * U for v in (pad_px, overshoot_px, ring_px, bar_px))
    span = 1000.0 - pad * 2
    r_outer = (span - 2 * overshoot) / 2.0
    design = build(r_outer, ring, bar / 2.0, overshoot)
    dpath = ROOT / "designs" / f"{name}.json"
    dpath.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    spath = ROOT / "svg" / f"{name}.svg"
    receipt = json.loads(subprocess.run(
        [GEOLOGO, "render", "--design", str(dpath), "--out", str(spath), "--json"],
        capture_output=True, text=True, check=True).stdout)
    for size in SIZES:
        for bg, tag in ((None, "alpha"), ("#FFFFFF", "white")):
            cmd = ["rsvg-convert"]
            if bg:
                cmd += ["-b", bg]
            cmd += ["-w", str(size), "-h", str(size), str(spath),
                    "-o", str(ROOT / "png" / f"{name}-{tag}-{size}.png")]
            subprocess.run(cmd, check=True)
    return {"name": name, "pad_px": pad_px, "overshoot_px": overshoot_px,
            "ring_px": ring_px, "bar_px": bar_px, "r_outer": r_outer,
            "circle_diameter_px_at_16": round(r_outer * 2 / U, 2),
            "design_sha256": receipt["design_sha256"], "svg_sha256": receipt["output_sha256"]}


if __name__ == "__main__":
    report = [emit(n, *p) for n, p in VARIANTS.items()]
    (ROOT / "sweep2-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in report:
        print(f"{r['name']:18s} 円径={r['circle_diameter_px_at_16']}px @16")
