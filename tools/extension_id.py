#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
Chrome 拡張 ID と manifest の "key" を相互に検証するツール。依存なし。

なぜ要るのか:
  ストアを経由しない拡張は、既定では **読み込んだディレクトリのパスから ID が決まる**。
  パスが変われば ID も変わり、native messaging manifest の allowed_origins が壊れる。
  manifest.json に "key"（RSA 公開鍵の DER を base64 したもの）を書くと、ID は
  その鍵から決まるようになり、パスに依存しなくなる。

  ID = sha256(DER 公開鍵) の先頭 16 バイトを、ニブルごとに 0-f → a-p へ写した 32 文字。

使い方:
  extension_id.py <manifest.json>       manifest の key から ID を出し、EXTENSION_ID と突き合わせる
  extension_id.py --key <base64>        key 文字列だけから ID を出す
  extension_id.py --der <file.der>      DER 公開鍵ファイルから ID を出す
  --json を付けると機械可読で出す
"""
import base64
import hashlib
import json
import os
import sys


def id_from_der(der: bytes) -> str:
    digest = hashlib.sha256(der).digest()[:16]
    return "".join(chr(ord("a") + (b >> 4)) + chr(ord("a") + (b & 0xF)) for b in digest)


def id_from_key(key_b64: str) -> str:
    return id_from_der(base64.b64decode(key_b64))


def main(argv):
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]
    if not argv:
        sys.stdout.write(__doc__)
        return 2

    if argv[0] == "--key":
        out = {"extension_id": id_from_key(argv[1])}
    elif argv[0] == "--der":
        with open(argv[1], "rb") as f:
            out = {"extension_id": id_from_der(f.read())}
    else:
        path = argv[0]
        with open(path, encoding="utf-8") as f:
            man = json.load(f)
        key = man.get("key")
        if not key:
            out = {"ok": False, "error": "manifest に key が無い。ID がパス依存になる"}
            print(json.dumps(out, ensure_ascii=False) if as_json else out["error"])
            return 1
        computed = id_from_key(key)
        expected_file = os.path.join(os.path.dirname(os.path.abspath(path)), "EXTENSION_ID")
        expected = None
        if os.path.exists(expected_file):
            with open(expected_file, encoding="utf-8") as f:
                expected = f.read().strip()
        out = {
            "ok": expected is None or expected == computed,
            "extension_id": computed,
            "expected": expected,
            "manifest": os.path.abspath(path),
        }

    if as_json:
        print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    else:
        print(out["extension_id"])
        if out.get("expected") and out["expected"] != out["extension_id"]:
            sys.stderr.write("不一致: EXTENSION_ID=%s\n" % out["expected"])
    return 0 if out.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
