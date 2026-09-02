#!/bin/bash
# VIEWPORT BREAK — 配布用 DMG を作る。
#
#   ./packaging/build_dmg.sh              → build/VIEWPORT BREAK <version>.dmg
#   ./packaging/build_dmg.sh --app-only   → .app だけ作る（反復用）
#   BUILD_DIR=... で出力先を変えられる
#
# Developer ID では署名しない。公証もこの版では使わない（年 99 ドルの契約が要るため）。
# 代わりに **ad-hoc 署名**（codesign -s -）だけ行う。Apple Silicon は未署名の
# Mach-O を実行できないため、ad-hoc 署名は Gatekeeper とは別に必須。
# ad-hoc 署名では Gatekeeper は通らない。購入者側の初回起動手順は
# docs/DMG_DISTRIBUTION_2026-08-30.md §5 を参照。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$REPO/build}"

APP_NAME="VIEWPORT BREAK"
BUNDLE_ID="com.nanago.viewport-break"
APP_VERSION="1.0.2"          # 配布物を差し替えず、内容が変わるたび必ず上げる
EXE_NAME="viewport-break"
MIN_MACOS="12.0"

APP="$BUILD_DIR/$APP_NAME.app"
STAGE="$BUILD_DIR/dmg-stage"
DMG="$BUILD_DIR/$APP_NAME $APP_VERSION.dmg"
CHECKSUM="$DMG.sha256"
PREFLIGHT="$BUILD_DIR/$APP_NAME $APP_VERSION - BEFORE OPENING.txt"
HYBRID="$BUILD_DIR/.$APP_NAME-$APP_VERSION-hybrid.dmg"
VOLNAME="$APP_NAME"

say() { printf '\033[1m▸ %s\033[0m\n' "$*"; }

rm -rf "$APP" "$STAGE" "$DMG"
rm -f "$CHECKSUM" "$PREFLIGHT" "$HYBRID"
mkdir -p "$BUILD_DIR"

# ---------------------------------------------------------------- 0. 前提チェック
say "拡張 ID の固定を検証する"
# ここで落とすのは意図的。ID がずれた拡張を同梱すると、native messaging manifest の
# allowed_origins と食い違い、インストールしても host が呼べない DMG が出来上がる。
"$REPO/tools/extension_id.py" "$REPO/extension/manifest.json" >/dev/null
EXT_ID="$("$REPO/tools/extension_id.py" "$REPO/extension/manifest.json")"
SWIFT_ID="$(sed -n 's/^let EXT_ID *= *"\(.*\)".*/\1/p' "$HERE/helper/Sources/main.swift")"
if [[ "$EXT_ID" != "$SWIFT_ID" ]]; then
  echo "拡張 ID が helper と食い違う: manifest=$EXT_ID helper=$SWIFT_ID" >&2
  exit 1
fi
echo "  拡張 ID = $EXT_ID （manifest の key と helper が一致）"

# ---------------------------------------------------------------- 1. ヘルパーをビルド
say "ヘルパーを universal binary としてコンパイルする"
OBJ="$BUILD_DIR/obj"; mkdir -p "$OBJ"
for arch in arm64 x86_64; do
  swiftc -O -target "$arch-apple-macosx$MIN_MACOS" \
    -o "$OBJ/$EXE_NAME-$arch" "$HERE/helper/Sources/main.swift"
done
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
lipo -create -output "$APP/Contents/MacOS/$EXE_NAME" \
  "$OBJ/$EXE_NAME-arm64" "$OBJ/$EXE_NAME-x86_64"
chmod +x "$APP/Contents/MacOS/$EXE_NAME"
lipo -archs "$APP/Contents/MacOS/$EXE_NAME" | sed 's/^/  arch: /'

# ---------------------------------------------------------------- 2. Info.plist
say "Info.plist を書く"
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
  <key>CFBundleExecutable</key><string>$EXE_NAME</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$APP_VERSION</string>
  <key>CFBundleVersion</key><string>$APP_VERSION</string>
  <key>LSMinimumSystemVersion</key><string>$MIN_MACOS</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSHumanReadableCopyright</key><string>VIEWPORT BREAK</string>
  <!-- オートメーション権限のダイアログに出る説明文。
       これが無いと macOS はダイアログを出さずに要求を落とす。 -->
  <key>NSAppleEventsUsageDescription</key>
  <string>Chrome のウィンドウ幅を、Chrome 自身の下限（500px）より狭い 375px などへ設定するために使います。</string>
</dict>
</plist>
PLIST
printf 'APPL????' > "$APP/Contents/PkgInfo"

# ---------------------------------------------------------------- 3. アイコン
say "アイコンを組み込む"
# 確定ロゴ（assets/brand/master/）から派生させた iconset をそのまま使う。
# 派生は assets/brand/build_brand_assets.py が生成し、リポジトリへコミット済み。
# ここで生成し直さないのは、**ビルド機に Pillow を要求しない**ため。
# ロゴを差し替えるときは build_brand_assets.py を回してから、この DMG を作る。
ICONSET="$REPO/assets/brand/out/macos/AppIcon.iconset"
[[ -d "$ICONSET" ]] || { echo "iconset が無い: $ICONSET （build_brand_assets.py を先に回す）" >&2; exit 1; }
n_icons=$(find "$ICONSET" -name '*.png' | wc -l | tr -d ' ')
[[ "$n_icons" == "10" ]] || { echo "iconset の枚数が 10 でない: $n_icons" >&2; exit 1; }
echo "  iconset: $n_icons 枚（${ICONSET}）"
/usr/bin/python3 "$HERE/build_icns.py" "$ICONSET" "$APP/Contents/Resources/AppIcon.icns"

# ---------------------------------------------------------------- 4. 拡張を同梱
say "拡張を Resources へ同梱する"
EXT_DST="$APP/Contents/Resources/extension"
mkdir -p "$EXT_DST"
# host/ と bin/ と install.sh は開発用の Python 経路。配布物には入れない
# （配布版のヘルパーは .app 本体そのもの）。
for f in manifest.json popup.html popup.css popup.js core.js background.js EXTENSION_ID; do
  cp "$REPO/extension/$f" "$EXT_DST/"
done
cp -R "$REPO/extension/icons" "$EXT_DST/"
find "$EXT_DST" -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
echo "  $(find "$EXT_DST" -type f | wc -l | tr -d ' ') ファイル"

# ---------------------------------------------------------------- 5. パーミッション正規化
# ビルド機の umask をそのまま配布物へ持ち込まないための明示。
# 実測（2026-08-30）: umask 077 の環境で作った 1.0.0 の DMG は中身が全部
#   drwx------ / -rwx------ （0700 / 0600）で固まっていた。配布物としては不正で、
#   .app を読むのが所有者だけになる。Google Chrome.app は 0775、通常は 0755。
# 署名の前に直す（パーミッションは署名対象外だが、順序を固定して迷いを無くす）。
say "パーミッションを 755/644 に正規化する"
find "$APP" -type d -exec chmod 755 {} +
find "$APP" -type f -exec chmod 644 {} +
chmod 755 "$APP/Contents/MacOS/$EXE_NAME"
ls -ld "$APP" "$APP/Contents/MacOS/$EXE_NAME" | sed 's/^/  /'

# ---------------------------------------------------------------- 6. ad-hoc 署名
say "ad-hoc 署名する（Developer ID ではない）"
codesign --force --deep --sign - --timestamp=none "$APP"
# codesign が umask 077 で新規作成した CodeResources も配布可能なモードへ戻す。
find "$APP/Contents/_CodeSignature" -type f -exec chmod 644 {} +
codesign --verify --deep --strict "$APP"
codesign -dv "$APP" 2>&1 | sed -n 's/^/  /p' | head -8

if [[ "${1:-}" == "--app-only" ]]; then
  say "完了（--app-only）: $APP"
  exit 0
fi

# ---------------------------------------------------------------- 7. DMG
say "DMG を組む"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
# DMG を開いた人が最初に見る文書は、単体で配っている手順書と同一物にする。
# 1.0.2 までは旧版の『はじめにお読みください.txt』（ターミナルで quarantine を
# 外す前提の手順）が焼かれていて、単体配布版と食い違っていた。同じ 1 本にする。
cp "$HERE/dmg/インストール手順.txt" "$STAGE/"

# DMG に焼かれるのは STAGE の中身なので、正規化は **ここが本番**。
# macOS の cp -R は -p を付けない限りモードを引き継がず、umask が再適用される。
# 実測（2026-08-30）: $APP を 755 にしてから cp -R しても、STAGE 側は 0700 に戻り、
# その 0700 がそのまま DMG へ焼かれていた。ここで直さないと意味がない。
say "ステージのパーミッションを正規化する"
find "$STAGE" -type d -exec chmod 755 {} +
find "$STAGE" -type f -exec chmod 644 {} +
chmod 755 "$STAGE/$APP_NAME.app/Contents/MacOS/$EXE_NAME"
chmod -h 755 "$STAGE/Applications"
# 署名は chmod では壊れないが、焼く前に必ず検証する
codesign --verify --deep --strict "$STAGE/$APP_NAME.app"
RESIDUAL_MODES="$(find "$STAGE" \( -perm 700 -o -perm 600 \) -print)"
if [[ -n "$RESIDUAL_MODES" ]]; then
  printf '%s\n' "$RESIDUAL_MODES" | sed 's/^/  不正な 0700\/0600: /' >&2
  exit 1
fi

if ! hdiutil create -volname "$VOLNAME" -srcfolder "$STAGE" -ov -format UDZO \
  -fs HFS+ -quiet "$DMG"; then
  # 一部のCI／サンドボックスは disk image device の構成を禁止するため、create が
  # 「装置が構成されていません」で失敗する。その場合も、デバイスを attach しない
  # makehybrid で HFS+ イメージを作り、同じ UDZO 形式へ変換できる。
  say "通常経路を使えないため、attach 不要の HFS+ 経路で DMG を組む"
  rm -f "$DMG" "$HYBRID"
  hdiutil makehybrid -quiet -hfs -hfs-volume-name "$VOLNAME" \
    -o "$HYBRID" "$STAGE"
  hdiutil convert "$HYBRID" -quiet -format UDZO -imagekey zlib-level=9 \
    -o "$DMG"
  rm -f "$HYBRID"
fi
hdiutil verify "$DMG" >/dev/null
rm -rf "$STAGE"

# 開く前の案内。DMG内ではなく、ダウンロードページ／購入メール側へ掲載する。
# 購入者向けの SHA-256 照合は 2026-08-31 のオーナー決裁で廃止した。購入ページと
# DMG の配布元が同一サーバーで、改竄されれば掲載ハッシュも同時に書き換わるため、
# 照合しても購入者が守れるものが無い。署名・公証も導入しない方針で確定している。
sed -e "s/@APP_VERSION@/$APP_VERSION/g" \
    -e "s/@DMG_FILENAME@/$(basename "$DMG")/g" \
    "$HERE/dmg/BEFORE_OPENING.txt.in" > "$PREFLIGHT"

# ビルド記録として手元に残すだけの内部用ダイジェスト。
# 購入ページ・購入メール・手順書のいずれにも掲載しないこと。
SHA256="$(shasum -a 256 "$DMG" | awk '{print $1}')"
printf '%s  %s\n' "$SHA256" "$(basename "$DMG")" > "$CHECKSUM"

say "完了"
printf '  %s  %s\n' "$(ls -lh "$DMG" | awk '{print $5}')" "$DMG"
printf '  sha256 %s（内部記録。配布物へ掲載しない）\n' "$SHA256"
printf '  事前手順 %s\n' "$PREFLIGHT"
printf '  内部記録 %s\n' "$CHECKSUM"
