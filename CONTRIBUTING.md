# CONTRIBUTING

VIEWPORT BREAK は[プロプライエタリ](LICENSE)な private リポジトリです。
外部からの pull request は受け付けていません。この文書は**権限を持つ開発者向けの作業規約**です。

---

## 開発環境

追加のパッケージインストールは不要。macOS 標準のものだけで動く。

| 用途 | 必要なもの |
|---|---|
| 拡張・host の実行 | macOS 12 以降 / Google Chrome 116 以降 / `/usr/bin/python3` / `/usr/bin/osascript` |
| DMG のビルド | Xcode Command Line Tools（`swiftc` / `codesign` / `hdiutil`） |
| ブランド資産の生成 | `assets/brand/build_brand_assets.py` が使う画像ライブラリ |

```bash
# native messaging host を登録する（冪等）
cd extension && ./install.sh

# 拡張は chrome://extensions からデベロッパー モードで extension/ を読み込む
# ID が ejlimgikbnaihoigbcmelaadniiminfj になっていることを毎回確認する
```

---

## 変更前に読むもの

設計判断はすべて `docs/` に理由つきで残してある。**同じ検証をやり直す前に、
既に実測された結論がないか確認すること。**

| 触る対象 | 先に読む |
|---|---|
| ウィンドウ幅の下限まわり | `docs/WINDOW_FLOOR_2026-08-30.md` / `docs/EXTENSION_ONLY_LIMITS_2026-08-30.md` |
| プリセットの刻み | `docs/PRESET_WIDTHS_2026-08-30.md` |
| 拡張の実装 | `docs/EXTENSION_2026-08-30.md` |
| DMG 配布・署名・Gatekeeper | `docs/DMG_DISTRIBUTION_2026-08-30.md` / `docs/ZERO_TOUCH_INSTALL_DESIGN.md` |
| ロゴ・アイコン | `assets/brand/README.md` / `docs/BRAND_LOGO_APPLY_2026-08-31.md` |

---

## 守ること

### 1. 名称を揺らさない

製品名は **VIEWPORT BREAK**（大文字・スペース区切り）。
`com.nanago.viewport_deck` は host の登録名、`com.nanago.viewport-break` はアプリの bundle ID。
**既存の識別子は改名しない**（変えると登録済みの native messaging host と拡張の対応が壊れる）。

### 2. 拡張 ID を変えない

`extension/manifest.json` の `key` は拡張 ID を
`ejlimgikbnaihoigbcmelaadniiminfj` に固定するためのもの。
これを消すとディレクトリ位置によって ID が変わり、host の `allowed_origins` が壊れる。
**`key` を書き換えない。**

### 3. 検証していないことを「できる」と書かない

README・`docs/`・同梱文書では、実測した内容と未検証の内容を必ず書き分ける。
制限事項は隠さずに書く（README の「既知の制限」がその方針）。
新しく実測したら、生の出力を `docs/evidence/<トピック>-<日付>/` へ残す。

### 4. secrets を入れない

API キー・トークン・証明書・鍵は**コミットしない**。
生成スクリプトが外部サービスを使う場合は、キーを keychain か
リポジトリ外のファイルから読む（keychain の `security find-generic-password`、
または環境変数で渡したファイルパスから読む形にする）。

個人情報（電話番号、メールアドレス、iMessage 由来の添付画像など）も同様に入れない。

### 5. 履歴を書き換えない

`--force` / `--force-with-lease` の push、`rebase` による公開済み履歴の改変、
`filter-branch` は行わない。取り消しは revert コミットで行う。

---

## バージョンと配布物

| 対象 | 正本 |
|---|---|
| macOS アプリ / DMG | `packaging/build_dmg.sh` の `APP_VERSION` |
| Chrome 拡張 | `extension/manifest.json` の `version` |

**配布物を差し替えるときは必ずバージョンを上げる。**
同じバージョン番号で中身の違う DMG を出さない（1.0.1 → 1.0.2 はこの規約で切った）。

```bash
# DMG をビルドする
./packaging/build_dmg.sh

# 配布候補の契約を検証する（.app / DMG / 同梱文書 / パーミッション / 署名）
/usr/bin/python3 packaging/tests/test_release_contract.py
```

`build/` は `.gitignore` 済み。**ビルド成果物（.app / .dmg）をコミットしない。**

変更を入れたら `CHANGELOG.md` に 1 行足す。

---

## コミットメッセージ

`<type>(<scope>): <日本語の要約>` の形。既存の履歴に合わせる。

```
feat(extension): 任意幅の下限を 50 → 1 にし、復帰コマンド --restore を追加 (v1.4.0)
fix(packaging): 「応答しないため開けません」の原因 3 点を修正し、手順を実測で引き直す
docs(packaging): 配布物から SHA-256 照合を廃止する
chore(assets): ロゴ試行錯誤の記録だけ残し、再生成できる出力を落とす
```

type は `feat` / `fix` / `docs` / `chore` / `release`。
**何をしたかではなく、何が変わったかを書く。**

---

## 公開範囲

このリポジトリは private です。**public 化・リリース作成・外部への告知は、
オーナーの明示的な指示がある場合にのみ行う。**
