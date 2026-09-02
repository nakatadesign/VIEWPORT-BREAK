#!/usr/bin/python3
"""iconsetのPNGを、追加依存なしでmacOS ICNSコンテナへまとめる。"""

from __future__ import annotations

import os
import struct
import sys


# icp4 / icp5（16x16・32x32 の 1x 枠）は **意図的に入れない**。
# この 2 つは PNG を入れても macOS 側が 24bit 生データとして読むため、
# Finder で 16pt / 32pt が色ノイズになる（2026-08-31 に NSWorkspace 実描画で確認。
# 1.0.0 / 1.0.1 の DMG はこの状態で出ている）。
# 代わりに ic11 / ic12（@2x の PNG）だけを置き、1x は macOS に縮小させる。
#
# 正規の 1x 枠である is32/il32（RLE 24bit RGB）+ s8mk/l8mk（生マスク）も試したが、
# 自前 RLE は往復デコードでビット一致するのに macOS の描画結果とは相関しなかった
# （実測: 相関 -0.14 / -0.18）。macOS 側の解釈が掴めていないので入れていない。
# 非 Retina で 16pt がやや暗くなるのが既知の残課題。
ENTRIES = [
    (b"ic11", "icon_16x16@2x.png", 32),
    (b"ic12", "icon_32x32@2x.png", 64),
    (b"ic07", "icon_128x128.png", 128),
    (b"ic13", "icon_128x128@2x.png", 256),
    (b"ic08", "icon_256x256.png", 256),
    (b"ic14", "icon_256x256@2x.png", 512),
    (b"ic09", "icon_512x512.png", 512),
    (b"ic10", "icon_512x512@2x.png", 1024),
]



def png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("PNGヘッダーが不正")
    return struct.unpack(">II", data[16:24])


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("使い方: build_icns.py <AppIcon.iconset> <AppIcon.icns>", file=sys.stderr)
        return 2

    iconset, output = argv
    chunks: list[bytes] = []
    for kind, name, expected in ENTRIES:
        path = os.path.join(iconset, name)
        try:
            with open(path, "rb") as f:
                data = f.read()
            actual = png_size(data)
        except (OSError, ValueError) as e:
            print(f"アイコンを読めない: {path}: {e}", file=sys.stderr)
            return 1
        if actual != (expected, expected):
            print(
                f"アイコン寸法が不正: {path}: expected={expected}x{expected} actual={actual[0]}x{actual[1]}",
                file=sys.stderr,
            )
            return 1
        chunks.append(kind + struct.pack(">I", len(data) + 8) + data)

    body = b"".join(chunks)
    with open(output, "wb") as f:
        f.write(b"icns" + struct.pack(">I", len(body) + 8) + body)
    print(f"  icns: {len(ENTRIES)} representations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
