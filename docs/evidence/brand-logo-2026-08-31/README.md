# 確定ロゴ適用の検証記録 — 2026-08-31

## macOS アプリアイコン（実描画）

`appicon-{16,32,64,128,256,512}.png` は `NSWorkspace.shared.icon(forFile:)` で
`build/VIEWPORT BREAK.app` から取り出して各サイズへ描画したもの。
Finder がアイコンを引くのと同じ経路なので、モックではなく実際の表示。

- `macos-appicon-nsworkspace.png` — 修正後。全サイズで彩度 < 0.12（無彩色）・peak 輝度 ≥ 160。
- `macos-appicon-BEFORE-icp4-icp5-noise.png` — 修正前。**16pt / 32pt が色ノイズ**。
  `packaging/build_icns.py` が `icp4` / `icp5` に PNG を入れていたのが原因で、
  macOS はこの 2 つを 24bit 生データとして読む。1.0.0 / 1.0.1 の DMG も同じ状態で出ている。

## Chrome 拡張アイコン

- `extension-icon-on-toolbar-colors.png` — `extension/icons/*.png` を Chrome の
  ツールバー地色（ライト `#DEE1E6` / ダーク `#35363A`）へ実寸で置いたもの。
  **これは Chrome のスクリーンショットではなく、アイコンファイルのレンダ。**
  chrome://extensions とツールバーでの実表示は未確認（下記）。

## 未検証

Chrome へ拡張を読み込んでの目視確認（ツールバーのアイコン、chrome://extensions の
表示名が "VIEWPORT BREAK" になっていること）は **未実施**。
このセッションでは Chrome の起動が承認されなかったため。

機械的には次まで確認済み:

- `extension/icons/*.png` の sha256 が `assets/brand/out/extension/*.png` と一致
- `.app` に同梱された `Contents/Resources/extension/` も同じ sha256・`name` が "VIEWPORT BREAK"
- `manifest.json` の `name` / `action.default_title` が "VIEWPORT BREAK"
- 拡張 ID が `ejlimgikbnaihoigbcmelaadniiminfj` のまま（`key` 由来なので改名の影響を受けない）

## その他

- `brand-assets-manifest.json` — 派生物 49 件のサイズ・バイト数・sha256。
