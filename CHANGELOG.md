# CHANGELOG

VIEWPORT BREAK（アプリ本体 / DMG 配布物）の変更履歴。
バージョンは `packaging/build_dmg.sh` の `APP_VERSION` が正本。

## 1.0.2 — 2026-08-31

- インストール手順から SHA-256 照合を廃止
- DMG の同梱文書を、単体で配っている『インストール手順.txt』と同一物にした。
  ターミナル前提の旧版『はじめにお読みください.txt』は削除（両者が食い違っていた）
- 手順書: 冒頭の所要時間・手順数の宣言と「なぜ警告が出るのか」節を削除、
  手順 13 に ウィンドウメニュー →「拡張機能」経由を追記、文言を微修正
- 手順書: 冒頭の箇条書きの先頭に「Google Chrome 用の機能拡張である」ことを明記、
  警告の説明を「Apple の審査を通していない」に改め、金額の記載をやめた

## 1.0.1 — 2026-08-30（未公開）

- Native Messaging の登録先を標準版 Google Chrome に限定し、旧版が Brave / Edge /
  Vivaldi / Arc / Canary / Chromium へ置いた manifest は更新時に削除する
- `--uninstall` で全既知 manifest と `~/Library/Application Support/VIEWPORT BREAK`
  を削除し、削除失敗を非 0 終了と JSON の `failures` で返す
- 展開済み拡張を検証済み一時ディレクトリとの rename swap で原子的に更新する
- popup の存在しない `README/install.sh` 案内を廃止し、失敗時は拡張アイコンへ
  赤い `!` バッジとエラー内容を表示する
- ビルド時に 0700/0600 の残存・ad-hoc 署名・DMG の内部 checksum を fail-closed で検証する
- 確定ロゴを適用し、製品名を VIEWPORT BREAK へ統一

## 1.0.0 — 2026-08-30

- DMG 配布の第一版（Swift ヘルパー + 拡張同梱 + ad-hoc 署名）
