#!/usr/bin/env python3
"""VIEWPORT BREAK 案A「貫く線」の GeoLogo design.json を生成する。

幾何分解:
- body: 外円(2円弧) + バーの外縁(6直線) を1本の閉じたC0ループにした和集合輪郭
- features: 内円とバー左右エッジで閉じる chord 2個 = ビューポート内部の抜き

すべて正円と直線だけ。モノクロ。
"""
import json
import math
import pathlib
import sys

CANVAS = 1000.0
CX = CY = CANVAS / 2.0


def build(r_outer: float, ring: float, half_w: float, overshoot: float) -> dict:
    """r_outer=外円半径 / ring=リング線幅 / half_w=貫く線の半幅 / overshoot=円外への突出量"""
    r_in = r_outer - ring
    if not (0 < half_w < r_in):
        raise ValueError("half_w は内円半径より小さくすること")

    top = CY - r_outer - overshoot
    bottom = CY + r_outer + overshoot
    # バー側面が外円と交わる y
    yo = math.sqrt(r_outer * r_outer - half_w * half_w)
    yi = math.sqrt(r_in * r_in - half_w * half_w)
    xl, xr = CX - half_w, CX + half_w

    body = [
        # 左側面 上: バー上端左 -> 外円との交点
        {"type": "line", "key": "break-line-upper-left-edge",
         "start": [xl, top], "end": [xl, CY - yo]},
        # 外円 左半分（左回りで下へ）
        {"type": "circle", "key": "viewport-left-arc",
         "cx": CX, "cy": CY, "radius": r_outer,
         "start": [xl, CY - yo], "middle": [CX - r_outer, CY], "end": [xl, CY + yo]},
        # 左側面 下
        {"type": "line", "key": "break-line-lower-left-edge",
         "start": [xl, CY + yo], "end": [xl, bottom]},
        # バー下端
        {"type": "line", "key": "break-line-bottom-cap",
         "start": [xl, bottom], "end": [xr, bottom]},
        # 右側面 下
        {"type": "line", "key": "break-line-lower-right-edge",
         "start": [xr, bottom], "end": [xr, CY + yo]},
        # 外円 右半分（上へ）
        {"type": "circle", "key": "viewport-right-arc",
         "cx": CX, "cy": CY, "radius": r_outer,
         "start": [xr, CY + yo], "middle": [CX + r_outer, CY], "end": [xr, CY - yo]},
        # 右側面 上
        {"type": "line", "key": "break-line-upper-right-edge",
         "start": [xr, CY - yo], "end": [xr, top]},
        # バー上端
        {"type": "line", "key": "break-line-top-cap",
         "start": [xr, top], "end": [xl, top]},
    ]

    features = [
        # 内側の抜き 左（バー左エッジの直線 + 内円の左円弧）
        {"type": "chord", "key": "viewport-left-void", "fill": "paper",
         "line_start": [xl, CY + yi], "line_end": [xl, CY - yi],
         "arc": {"cx": CX, "cy": CY, "radius": r_in, "middle": [CX - r_in, CY]}},
        # 内側の抜き 右
        {"type": "chord", "key": "viewport-right-void", "fill": "paper",
         "line_start": [xr, CY - yi], "line_end": [xr, CY + yi],
         "arc": {"cx": CX, "cy": CY, "radius": r_in, "middle": [CX + r_in, CY]}},
    ]

    return {
        "schema_version": 1,
        "canvas": {"size": int(CANVAS)},
        "colors": {"paper": "#FFFFFF", "ink": "#111111"},
        "body": body,
        "features": features,
        "expected_counts": {"circles": 4, "lines": 8},
    }


if __name__ == "__main__":
    out = pathlib.Path(sys.argv[1])
    r_outer, ring, half_w, overshoot = (float(v) for v in sys.argv[2:6])
    out.write_text(json.dumps(build(r_outer, ring, half_w, overshoot),
                              ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out)
