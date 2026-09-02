#!/bin/bash
# VIEWPORT BREAK — native messaging host を登録する。
#
# 拡張本体は Chrome の「パッケージ化されていない拡張機能を読み込む」で
# この extension/ ディレクトリを指定する。このスクリプトは host 側だけを扱う。
#
# 冪等。何度実行してもよい。アンインストールは --uninstall。
set -euo pipefail

HOST_NAME="com.nanago.viewport_deck"
EXT_ID="ejlimgikbnaihoigbcmelaadniiminfj"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST_BIN="$HERE/host/viewport_deck_host.py"

# host が AppleScript で操作するのは標準版 Google Chrome だけ。
# 1.0.0 以前が置いた他ブラウザ向け manifest は移行掃除またはアンインストールにだけ使う。
TARGET_DIRS=(
  "$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
)
LEGACY_TARGET_DIRS=(
  "$HOME/Library/Application Support/Google/Chrome Canary/NativeMessagingHosts"
  "$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
  "$HOME/Library/Application Support/BraveSoftware/Brave-Browser/NativeMessagingHosts"
  "$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
  "$HOME/Library/Application Support/Vivaldi/NativeMessagingHosts"
  "$HOME/Library/Application Support/Arc/User Data/NativeMessagingHosts"
)

if [[ "${1:-}" == "--uninstall" ]]; then
  for d in "${TARGET_DIRS[@]}" "${LEGACY_TARGET_DIRS[@]}"; do
    f="$d/$HOST_NAME.json"
    [[ -f "$f" ]] && rm -f "$f" && echo "削除: $f"
  done
  echo "完了。拡張本体は chrome://extensions から手動で削除する。"
  exit 0
fi

[[ -f "$HOST_BIN" ]] || { echo "host が見つからない: $HOST_BIN" >&2; exit 1; }
chmod +x "$HOST_BIN"

installed=0
for d in "${TARGET_DIRS[@]}"; do
  parent="$(dirname "$d")"
  [[ -d "$parent" ]] || continue          # そのブラウザは未インストール
  mkdir -p "$d"
  tmp_manifest="$(mktemp "$d/.$HOST_NAME.XXXXXX")"
  trap 'rm -f "$tmp_manifest"' EXIT
  cat > "$tmp_manifest" <<JSON
{
  "name": "$HOST_NAME",
  "description": "VIEWPORT BREAK — AppleScript で Chrome ウィンドウ幅を 500px 下限より下へ設定する",
  "path": "$HOST_BIN",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXT_ID/"
  ]
}
JSON
  chmod 644 "$tmp_manifest"
  mv -f "$tmp_manifest" "$d/$HOST_NAME.json"
  trap - EXIT
  echo "設置: $d/$HOST_NAME.json"
  installed=$((installed+1))
done

# 旧版の過剰登録を残さない。
for d in "${LEGACY_TARGET_DIRS[@]}"; do
  f="$d/$HOST_NAME.json"
  [[ -f "$f" ]] && rm -f "$f" && echo "旧登録を削除: $f"
done

[[ $installed -gt 0 ]] || { echo "設置先が 1 つも無い（Chrome 未インストール？）" >&2; exit 1; }

echo
echo "host 疎通確認:"
"$HOST_BIN" --list || echo "  （Chrome が起動していないか、Automation 権限が未許可）"

cat <<TXT

次にやること:
  1. chrome://extensions を開き、右上の「デベロッパー モード」を ON
  2. 「パッケージ化されていない拡張機能を読み込む」で次を選ぶ:
       $HERE
  3. 拡張 ID が $EXT_ID になっていることを確認する
     （manifest.json の "key" で固定しているので、この ID 以外にはならない）
  4. ツールバーの VIEWPORT BREAK をクリックし、375 など 500px 未満のプリセットを押す。
     ウィンドウがその幅になれば完了（届かなければ popup にその場で理由が出る）

初回に「"Google Chrome" が "Google Chrome" を制御することを求めています」と出たら許可する。
拒否した場合は システム設定 → プライバシーとセキュリティ → オートメーション で後から許可できる。
TXT
