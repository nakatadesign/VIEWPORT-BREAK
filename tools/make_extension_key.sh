#!/bin/bash
# 拡張 ID を固定するための鍵を作る。
#
# ストア非経由で配布する拡張は、既定では読み込んだディレクトリのパスから ID が決まる。
# native messaging manifest の allowed_origins は ID を名指しするので、
# ID が動くと host 呼び出しが必ず失敗する。manifest.json に "key" を焼き込んで固定する。
#
#   ./tools/make_extension_key.sh                 → 秘密鍵と key と ID を表示（ファイルは作らない）
#   ./tools/make_extension_key.sh out/vb.pem      → 秘密鍵をそのパスへ保存する
#
# 表示された `"key": "..."` を extension/manifest.json の先頭付近へ貼り、
# 同じ ID を extension/EXTENSION_ID と install 側へ反映する。
# 秘密鍵は **リポジトリに入れない**。CRX を自前署名して配る日が来たときだけ必要になる。
# unpacked 配布しかしないなら、manifest の key（公開鍵）だけで ID は固定できる。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PEM="${1:-}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

/usr/bin/openssl genrsa -out "$TMP/key.pem" 2048 2>/dev/null
/usr/bin/openssl rsa -in "$TMP/key.pem" -pubout -outform DER -out "$TMP/pub.der" 2>/dev/null

KEY="$(/usr/bin/base64 < "$TMP/pub.der" | tr -d '\n')"
ID="$("$HERE/extension_id.py" --der "$TMP/pub.der")"

if [[ -n "$PEM" ]]; then
  mkdir -p "$(dirname "$PEM")"
  cp "$TMP/key.pem" "$PEM"
  chmod 600 "$PEM"
  echo "秘密鍵: $PEM  （リポジトリに入れない）"
fi

echo
echo "manifest.json に貼る行:"
echo "  \"key\": \"$KEY\","
echo
echo "拡張 ID: $ID"
echo
echo "反映先: extension/manifest.json の key / extension/EXTENSION_ID /"
echo "        packaging/helper/Sources/main.swift の EXT_ID / extension/install.sh の EXT_ID"
