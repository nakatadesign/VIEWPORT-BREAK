# 確定ロゴの適用と製品名の統一 — 2026-08-31

対象: 本リポジトリ / ブランチ `brand/viewport-break-logo-final` / commit `96fde1f`（push していない）

確定ロゴ = 黒背景・アイソメの透明ガラス板 2 枚が重なった V と B のマーク。1200x1200 RGB。
元画像 sha256 `146f5da4d33df470db8544d4c610ac965471ef21ce9f1f9191399fdc742373e7`。

---

## 1. 変更ファイル一覧

### 新規（82 ファイルのうち主なもの）

| パス | 内容 |
| --- | --- |
| `assets/brand/master/viewport-break-logo-master-1200.png` | **無加工のマスター**。元画像と sha256 一致 |
| `assets/brand/build_brand_assets.py` | master からだけ派生を作る。起動時に master の sha256 を照合 |
| `assets/brand/README.md` | 資産の構成・設計上の決めごと・既知の残課題 |
| `assets/brand/out/**`（49 件） | 派生物。`out/MANIFEST.json` に全件のサイズ・バイト数・sha256 |
| `docs/evidence/brand-logo-2026-08-31/**` | 検証記録（下記 4 章） |

### 変更

| パス | 内容 |
| --- | --- |
| `extension/icons/icon{16,32,48,128}.png` | 新アイコンへ差し替え |
| `extension/manifest.json` | `name` / `action.default_title` を VIEWPORT BREAK へ |
| `extension/background.js` | ツールチップ 2 箇所 |
| `extension/install.sh` | host manifest の `description`、案内文、ヘッダ |
| `extension/README.md` / `extension/core.js` / `extension/bin/vw` / `extension/host/viewport_deck_host.py` | 見出し・ヘッダ |
| `extension/tests/background.test.mjs` | ツールチップの期待値 |
| `packaging/build_dmg.sh` | iconset を生成せず `assets/brand/out/macos/AppIcon.iconset` を使う |
| `packaging/build_icns.py` | `icp4` / `icp5` を外す（4 章の不具合） |
| `docs/DMG_DISTRIBUTION_2026-08-30.md` / `docs/ZERO_TOUCH_INSTALL_DESIGN.md` | 解消済みの課題へ追記 |
| `.gitignore` | `assets/brand/__pycache__/` |

### 削除

| パス | 理由 |
| --- | --- |
| `extension/tools/make_icons.py` | 旧図案（青い角丸＋白いバー）の生成器。`__main__` が `extension/icons/` を上書きするため、新アイコンを壊す口が残る |

---

## 2. アイコン参照箇所の一覧と差し替え結果

grep（`icon` / `favicon` / `apple-touch` / `icns` / `AppIcon` / `CFBundleIcon` / `og:image` / `twitter:image` / `manifest`）で洗い出した**実在する参照箇所は 3 つだけ**。すべて差し替え済み。

| # | 参照箇所 | 参照していたもの | 対応 |
| --- | --- | --- | --- |
| 1 | `extension/manifest.json` の `icons` と `action.default_icon`（16/32/48/128） | `extension/icons/*.png` | ファイルを派生物へ差し替え。sha256 一致を確認 |
| 2 | `packaging/build_dmg.sh` → `build_icns.py` → `Info.plist` の `CFBundleIconFile = AppIcon` | `make_icons.py` がその場で生成 | コミット済み iconset を使う形へ変更。ビルド機に Pillow を要求しない |
| 3 | `packaging/helper/Sources/main.swift:424` の同梱ファイル一覧（`icons/icon16.png`, `icons/icon128.png`） | `extension/icons/*.png` | パス不変。中身が新しくなるので変更不要 |

### 参照先が存在しない成果物

このリポジトリは **Chrome 拡張 + macOS ヘルパーアプリ**の構成で、Web サイトも PWA も iOS アプリも無い。
`index.html` の `link` / `meta`、PWA manifest、`Info.plist` の iOS 用エントリは**そもそも存在しない**（`extension/popup.html` は拡張の popup で favicon を持たない、`docs/screenshots/index.html` は証跡）。

依頼どおり資産は全部作って `assets/brand/out/` に置いたが、**差し替えるべき参照箇所が無い**ので配線はしていない。

| 成果物 | 置き場所 | 参照元 |
| --- | --- | --- |
| iOS / iPadOS 15 サイズ | `out/ios/` | 無し（iOS プロジェクト未作成） |
| favicon 6 サイズ + `favicon.ico` | `out/web/` | 無し（サイト未作成） |
| apple-touch-icon 180 | `out/web/` | 同上 |
| PWA `192` / `512` / `maskable 192` / `maskable 512` | `out/web/` | 同上（manifest.webmanifest 自体が無い） |
| OGP 1200x630 / Twitter card 1200x600 | `out/share/` | 同上 |

サイトを作るときの配線例は `assets/brand/README.md` の表を参照。

---

## 3. 統一した名称の箇所

### 表示文字列 → `VIEWPORT BREAK`

| ファイル | 箇所 |
| --- | --- |
| `extension/manifest.json` | `name`、`action.default_title` |
| `extension/background.js` | `DEFAULT_TITLE`、失敗時の `setTitle` |
| `extension/install.sh` | host manifest の `description`、セットアップ案内、ヘッダコメント |
| `extension/README.md` | 見出し・本文・操作案内 |
| `extension/core.js` / `extension/bin/vw` / `extension/host/viewport_deck_host.py` | ファイル冒頭のヘッダ |
| `extension/tests/background.test.mjs` | 期待値 |

`packaging/` 側（`build_dmg.sh` の `APP_NAME`、`Info.plist`、DMG の案内文、Swift の `PRODUCT_NAME`）は**既に VIEWPORT BREAK** だった。

### 識別子として意図的に変えなかったもの

| 識別子 | 理由 |
| --- | --- |
| `HOST_NAME = "com.nanago.viewport_deck"` | native messaging の登録キー。`core.js` / `install.sh` / `main.swift` / release contract test の 4 箇所で一致必須。改名すると既に登録済みの環境と繋がらなくなる（`main.swift:30` に「改名しない」と明記あり） |
| `extension/host/viewport_deck_host.py` | ファイル名。host manifest の `path` が指す |
| `com.nanago.viewport-break` / `viewport-break` | bundle id と実行ファイル名。既に break 系 |

拡張 ID は `manifest.json` の `key` から導出されるので、`name` の変更では**変わらない**。
`ejlimgikbnaihoigbcmelaadniiminfj` のままであることを `tools/extension_id.py` で確認済み。

---

## 4. 途中で見つけた不具合 — macOS の `.icns` の 16pt / 32pt が色ノイズ

新アイコンを入れて `.app` を作り、`NSWorkspace.shared.icon(forFile:)`（Finder と同じ経路）で
実描画したところ、**16pt と 32pt が色ノイズ**になった。

原因は `packaging/build_icns.py` が 1x 枠を `icp4` / `icp5` で書いていたこと。
この 2 つは PNG を入れても macOS 側が 24bit 生データとして読む。
コンテナ自体は妥当（全チャンクが正しい PNG ペイロード）だが、読み手が別物として解釈する。

**既存の 1.0.0 / 1.0.1 の DMG も同じ状態**。旧アイコン（青い角丸＋白いバー）でも同様に化けていたはず。

対応: `icp4` / `icp5` を外し、`ic11`（16x16@2x = 32px）/ `ic12`（32x32@2x = 64px）以上の
PNG 表現だけを入れる。1x は macOS が縮小して作る。Retina では 16pt = 32 デバイス px なので
`ic11` がそのまま出る。

`.icns` は 10 → 8 representations になった。

### 試して採らなかった案

正規の 1x 枠である `is32` / `il32`（RLE 圧縮 24bit RGB）+ `s8mk` / `l8mk`（非圧縮マスク）も実装した。
自前 RLE は往復デコードで**ビット一致**したが、macOS の描画結果とは相関しなかった
（相関 −0.14 / −0.18、期待値ともノイズとも一致しない）。macOS 側の解釈が掴めなかったので撤去した。

**残課題**: 非 Retina（1x）でだけ 16pt がやや暗い。Retina では影響なし。

---

## 5. 派生の作り方で効いている 3 点

### 透過版はストレートアルファへの割り戻し

master は純黒地にガラスの反射だけが乗った絵で、黒地 = 何も無い。
つまり RGB が実質アルファ乗算済みなので、輝度をアルファに使い、RGB を輝度で割り戻して
ストレートアルファへ直している。

結果、**ガラス板の内側は透明**になり、見えるのは縁のハイライトだけ。
これはガラスとして正しいが、**白い面に置くとほぼ消える**。
明るい地で使う場合は黒地版を使う。アイコン類が全部黒地なのも同じ理由
（Chrome のツールバーはライト `#DEE1E6` / ダーク `#35363A` の両方があるため）。

### セーフエリア

マークは master の中で中心からずれている（bbox `x[143..987] y[198..1034]` = 左に 34px・下に 16px）。
派生時は bbox 基準で置き直しているので四辺の余白が揃う。

マスクで 1px も欠けないことを、マスク前後の光量差で確認した:

| マスク | マーク占有率 | 失う光量 | マスク外の点灯 px |
| --- | --- | --- | --- |
| 角丸 r=22.37% | 0.70 | 0.00000% | 0 |
| 角丸 r=22.37%（16px 用） | 0.82 | 0.00000% | 0 |
| macOS squircle（1024 中 824） | 本体比 0.72 | 0.00000% | 0 |
| PWA maskable の安全円（中央 80% 径） | 0.55 | 0.00000% | 0 |

### 小サイズの輝度

ガラスの縁は細い高輝度の線なので、sRGB 値のまま平均縮小すると実際の光量より暗くなる。
16px では peak 輝度が 88.8 まで落ちて潰れていた。

**リニア光で縮小**したうえで、最大輝度が 250 に届くまで一様ゲインをかけた
（16px で 1.84〜2.12 倍、48px で 1.18 倍、128px 以上は 1.0）。
結果、全サイズで peak 輝度 249〜255 に揃った。

---

## 6. 検証結果

`docs/evidence/brand-logo-2026-08-31/final-verify.log` に生出力。

| 項目 | 結果 |
| --- | --- |
| `node extension/tests/background.test.mjs` | PASS (exit 0) |
| `packaging/tests` release contract 4 件 | OK (exit 0) |
| `tools/extension_id.py` | `ejlimgikbnaihoigbcmelaadniiminfj`、`ok: true` |
| `packaging/build_dmg.sh` | 通る。DMG の checksum も生成 |
| 派生の冪等性 | 2 回回して全件同一 sha256 |
| macOS アプリアイコン実描画（16〜512pt） | 全サイズ 平均彩度 < 0.12・peak 輝度 ≥ 160 |
| `.app` 同梱の拡張 | `name` = VIEWPORT BREAK、アイコン 4 件の sha256 一致 |

### 未検証

**Chrome へ拡張を読み込んでの目視確認は未実施。**
ツールバーのアイコンと `chrome://extensions` の表示名が実際に新しくなっていることは確認できていない。
このセッションでは Chrome の起動が承認されなかったため。

代わりに `docs/evidence/brand-logo-2026-08-31/extension-icon-on-toolbar-colors.png` へ、
アイコンファイルを Chrome のツールバー地色に実寸で置いたレンダを残した。
これは Chrome のスクリーンショットではない。

確認手順（任意のプロファイルで）:

```
open -na "Google Chrome" --args \
  --user-data-dir=/tmp/vb-check \
  --load-extension="$PWD/extension" \
  "chrome://extensions/?id=ejlimgikbnaihoigbcmelaadniiminfj"
```

---

## 7. 残課題 / follow-up

1. **16px 専用グリフが無い。** V と B の字形が読めるのは 32px 以上。16px は「見分けがつく」水準。
   本筋は 16px 用に簡略化したグリフを別に起こすこと。
2. **非 Retina の 16pt がやや暗い**（4 章）。`is32` / `il32` の macOS 側の解釈が分かれば直せる。
3. **Web 資産に参照元が無い**（2 章）。サイト・PWA・iOS アプリを作る時点で配線が要る。
4. **透過版は明るい地で消える**（5 章）。白背景で使う要件が出たら、地色付きの版か
   暗色トレースを足した版を別途起こす必要がある。

---

## 8. このコミットに同居している他作業

dispatch 開始時点で作業ツリーには既に 26 件の未コミット変更があった（1.4.1 系の作業）。
うち、今回触ったファイルと重なる分（`extension/manifest.json` の version 1.4.0→1.4.1、
`build_dmg.sh` / `install.sh` / `background.js` / `README.md` / `DMG_DISTRIBUTION_2026-08-30.md`、
未追跡だった `packaging/build_icns.py` と `extension/tests/`）は、
git がファイル単位でしかステージできないため**同じコミットに入っている**。

今回の作業と無関係な分は触らずに残した:
`extension/popup.js` / `packaging/helper/Sources/main.swift` /
`packaging/dmg/はじめにお読みください.txt` / `packaging/dmg/BEFORE_OPENING.txt.in` /
`packaging/tests/` / `assets/icon-candidates/` / `assets/applogo-nanobanana-20260830/` /
`logo-*/` 11 ディレクトリ。

dispatch 開始時より新たに増えた dirty は 0 件。
