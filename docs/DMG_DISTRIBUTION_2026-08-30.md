# VIEWPORT BREAK — DMG 配布（ストア非経由）第一版

> **最新のローカル候補は 1.0.2（§15、未公開）。** §14 は 1.0.1、§0〜§13 は配布済み 1.0.0 の
> 実測・障害記録として残しており、現在の登録先や購入者手順の正本ではない。

作成 2026-08-30 / 実測環境 macOS 26.3.1 (25D771280a, arm64) + Google Chrome 151.0.7922.174 + swiftc 6.2.4

「ダウンロードした DMG → インストール → 375px になる」を実際に通した記録と、その過程で
設計を変えた点、購入者に伝えなければならないこと、まだ実測できていないことをまとめる。

**判定: 配布物としては成立する。ただし無署名・無公証のため、購入者に初回だけ 3 種類の
「許可」操作を必ず踏ませる必要があり、その案内が製品の一部になる。**

---

## 0. 一目で分かる結果

| 項目 | 結果 | 証跡 |
| --- | --- | --- |
| DMG が作れる | `VIEWPORT BREAK 1.0.0.dmg` / 190,977 bytes / sha256 `5fad10ac171fd9a49ff12631b31ef3cd4540406bc9f52a14288cd86b22261c7c`（§4 で測ったビルドの値。DMG は再現ビルドではないので毎回変わる） | `packaging/build_dmg.sh` |
| ダウンロードで quarantine が付く | `com.apple.quarantine = 0281;6a93bf49;Chrome;1C4520A3-...` | `out/download_gatekeeper.json` |
| Gatekeeper が初回起動を止める | 「"VIEWPORT BREAK.app" は開いていません」 | `shots/10-gatekeeper-first-launch.png` |
| ネイティブメッセージング登録が自動で入る | 既存の 6 ブラウザのプロファイルへ manifest 設置 | `--doctor` 出力（§4.3） |
| 拡張 ID が固定される | `ejlimgikbnaihoigbcmelaadniiminfj`（読み込み後の実 ID と一致） | `out/install_e2e.json` |
| **ウィンドウが 375px になる** | **`reached_375: true`（AppleScript 読み戻し・`chrome.windows` API 両方で 375）** | `shots/31-after-375.png` |
| SaaS 連動 | **存在しない**（未着手であって、壊れているのではない） | §7 |
| 署名・公証 | **していない**（指示どおり。$99/年の契約は取得していない） | — |

---

## 1. 依存関係の棚卸し — DMG 一発に何が要るか

配布前の構成（`extension/install.sh` が作る開発者向けの状態）は、次の 4 つが揃って初めて動く。

1. **ヘルパー本体** — `extension/host/viewport_deck_host.py`（Python）
2. **ネイティブメッセージング manifest** — `<Chrome の user-data-dir>/NativeMessagingHosts/com.nanago.viewport_deck.json`
   （既定プロファイルなら `~/Library/Application Support/Google/Chrome/NativeMessagingHosts/`）。
   `path` にヘルパーの絶対パス、`allowed_origins` に `chrome-extension://<拡張 ID>/` を書く。
3. **拡張本体** — `chrome://extensions` の「パッケージ化されていない拡張機能を読み込む」で読み込むフォルダ
4. **オートメーション（AppleEvents）の許可** — ヘルパーが Chrome を AppleScript で操作するための TCC 許可

このうち **1 は購入者の Mac ではそのままでは動かない**。理由を実測した。

### 1.1 `/usr/bin/python3` は macOS に含まれていない（配布を止めた事実）

```
$ otool -L /usr/bin/python3
/usr/bin/python3:
    /usr/lib/libxcselect.dylib ...
$ /usr/bin/python3 -c 'import sys; print(sys.executable)'
/Library/Developer/CommandLineTools/usr/bin/python3
```

`/usr/bin/python3` は `libxcselect` 経由のシムで、実体は Command Line Tools 配下にある。
Xcode も CLT も入れていない Mac（＝購入者の大多数）でこれを叩くと、Python は起動せず
CLT のインストールを促すダイアログが出る。**Python 製ヘルパーを DMG に入れる案はここで捨てた。**

### 1.2 置き換え — 依存ゼロの Swift ユニバーサルバイナリ

`packaging/helper/Sources/main.swift`（約 660 行）に、Python 版と**同じ JSON プロトコル**で
書き直した。拡張側 (`extension/core.js`) は 1 行も変えていない。

- ビルド: `swiftc -target arm64-apple-macosx12.0` と `x86_64-apple-macosx12.0` を別々に作り `lipo` で結合
  → `Mach-O universal (x86_64 arm64)`、Apple Silicon / Intel 両対応、外部依存なし
- AppleScript は `osascript` を呼ばず `NSAppleScript` でインプロセス実行する。
  これは TCC の帰属先を変えるための選択で、効果は §5.3 に実測がある。
- `ping` の応答に `impl:"swift"` を足して、どちらのヘルパーが応答したか判別できるようにした。

Python 版は開発用として残してある（`extension/install.sh` / `extension/bin/vw` はそのまま）。

### 1.3 DMG が済ませるもの / 購入者に残るもの

| | 誰がやるか |
| --- | --- |
| ヘルパーの配置 | DMG →「Applications へドラッグ」 |
| NM manifest の設置 | **アプリ初回起動時に自動**（存在するブラウザのプロファイルにだけ書く） |
| 拡張フォルダの展開 | **アプリ初回起動時に自動**（`~/Library/Application Support/VIEWPORT BREAK/extension`） |
| Gatekeeper の解除 | **購入者**（システム設定 →「このまま開く」） |
| 拡張の読み込み | **購入者**（デベロッパーモード ON →「パッケージ化されていない拡張機能を読み込む」） |
| オートメーション許可 | **購入者**（初回の 375 押下時に「許可」） |

購入者に残る 3 つは、いずれも**プログラムからは代行できない**（Gatekeeper と TCC は
仕様として合成クリックを拒否する／デベロッパーモードはユーザー操作を要求する）。
だから同梱の `はじめにお読みください.txt` とアプリ起動時のダイアログが必須になる。

---

## 2. 拡張 ID の固定 — 手順の確定

ストアを経由しない拡張は、フォルダのパスから ID が決まってしまう。一方 NM manifest の
`allowed_origins` には ID を書く必要がある。したがって **manifest に `key` を書いて ID を固定する**
のが唯一の方法。以下を確定した。

### 2.1 仕組み

- `key` = RSA 公開鍵の **DER を base64** にしたもの
- 拡張 ID = `sha256(DER)` の**先頭 16 バイト**を hex にし、各ニブル `0-f` を `a-p` に写したもの

`tools/extension_id.py` がこの計算を実装している。manifest の `key` から ID を出し、
`extension/EXTENSION_ID` の値と突き合わせる。

```
$ tools/extension_id.py extension/manifest.json --json
{"expected":"ejlimgikbnaihoigbcmelaadniiminfj",
 "extension_id":"ejlimgikbnaihoigbcmelaadniiminfj",
 "manifest":"...","ok":true}
```

### 2.2 鍵を作り直すときの手順（`tools/make_extension_key.sh`）

```
openssl genrsa 2048                 # 秘密鍵（リポジトリに入れない・オフラインで保管）
openssl rsa -pubout -outform DER    # 公開鍵 DER
base64                              # → manifest の "key"
```

スクリプトは `"key": "..."` の行と、そこから決まる ID を表示する。ID を変えると
**次の 4 か所を必ず同時に更新**する（ズレると native messaging が拒否される）:

1. `extension/manifest.json` の `key`
2. `extension/EXTENSION_ID`
3. `packaging/helper/Sources/main.swift` の `EXT_ID`
4. `packaging/dmg/はじめにお読みください.txt` の案内文中の ID

`packaging/build_dmg.sh` は 1 と 3 の一致をビルド前に検証し、食い違うとビルドを中止する。

**現行の鍵は変更していない。** ID は `ejlimgikbnaihoigbcmelaadniiminfj` のまま。

---

## 3. DMG の設計とビルド

### 3.1 中身

```
/Volumes/VIEWPORT BREAK/
├── VIEWPORT BREAK.app
│   └── Contents/
│       ├── Info.plist            com.nanago.viewport-break / LSMinimumSystemVersion 12.0
│       │                          NSAppleEventsUsageDescription（§5.3）
│       ├── MacOS/viewport-break  universal (x86_64 arm64), ad-hoc 署名
│       ├── Resources/AppIcon.icns
│       └── Resources/extension/  ← 実行時に ~/Library へ展開される拡張一式
├── Applications                  → /Applications へのシンボリックリンク
└── はじめにお読みください.txt
```

アプリバンドル内のファイルは 16 個。拡張は「実行時に必要なファイルだけ」を入れており、
`tools/` や `host/` は入っていない。

### 3.2 ビルド

```
$ packaging/build_dmg.sh              # → build/VIEWPORT BREAK 1.0.0.dmg
$ packaging/build_dmg.sh --app-only   # → build/VIEWPORT BREAK.app だけ
```

やっていること:

1. manifest の ID と `main.swift` の `EXT_ID` の一致を検証
2. 2 アーキテクチャを `swiftc` でコンパイル → `lipo -create`
3. `Info.plist` / `PkgInfo` を生成、`assets/brand/out/macos/AppIcon.iconset`（確定ロゴからの派生、コミット済み）を `packaging/build_icns.py` で `.icns` にまとめる
4. 拡張の実行時ファイルをコピー
5. `codesign --force --deep --sign -`（**ad-hoc**。Developer ID 署名ではない）
6. ステージングに `/Applications` シンボリックリンクと `はじめにお読みください.txt` を置く
7. `hdiutil create -volname "VIEWPORT BREAK" -format UDZO -fs HFS+`
8. サイズと sha256 を表示

`hdiutil` の出力にはタイムスタンプが入るため、**同じソースからビルドしても DMG の sha256 は毎回変わる**
（再ビルドで `5fad10ac...` → `2ce9c2b1...` → `7d11fad9...` を確認）。
配布時は「配ったファイルの sha256」を都度控える運用になる。

ad-hoc 署名は Gatekeeper を通すためではなく（通らない）、`Sealed Resources` を付けて
バンドルの同一性を TCC に認識させるため。実測での署名情報:

```
Identifier=com.nanago.viewport-break
Format=app bundle with Mach-O universal (x86_64 arm64)
CodeDirectory ... flags=0x2(adhoc)
Signature=adhoc
TeamIdentifier=not set
```

---

## 4. 実測 — ダウンロードから 375px まで通した

使い捨てプロファイルの Chrome で自分の DMG を HTTP 経由でダウンロードし、本物の
quarantine 属性が付いた状態から始めている。手順スクリプトは
`docs/evidence/dmg-installer-2026-08-30/` に 4 本置いた。

### 4.1 ダウンロード（`run_download_gatekeeper.py` → `out/download_gatekeeper.json`）

- ダウンロード後の DMG: sha256 がビルド時と一致、`com.apple.quarantine = 0281;6a93bf49;Chrome;1C4520A3-32EE-4DE2-928A-1C8EA19CDFF3`
- マウント（`hdiutil attach`）rc=0、中身は `Applications` / `VIEWPORT BREAK.app` / `はじめにお読みください.txt` の 3 つ
- DMG 内の .app に対する `spctl -a -t exec` → **rc=3 `rejected`**（＝Gatekeeper は許可しない）
- スクリーンショット `shots/01-chrome-download.png`

### 4.2 Gatekeeper（`run_gatekeeper_install.py` → `out/gatekeeper_install.json`）§5 に詳述

### 4.3 インストール直後の状態（`run_install_e2e.py` → `out/install_e2e.json`）

アプリを起動すると `shots/20-setup-dialog.png` のダイアログが出て、その時点で
以下がすでに済んでいる。

既定プロファイルに書かれた manifest（実際のファイル内容）:

```json
{
  "allowed_origins": ["chrome-extension://ejlimgikbnaihoigbcmelaadniiminfj/"],
  "description": "VIEWPORT BREAK — Chrome ウィンドウ幅を 500px の下限より下へ設定する",
  "name": "com.nanago.viewport_deck",
  "path": "/Applications/VIEWPORT BREAK.app/Contents/MacOS/viewport-break",
  "type": "stdio"
}
```

`--doctor` の出力（抜粋）:

```
host_version              2.0.0
extension_installed       true
extension_id              ejlimgikbnaihoigbcmelaadniiminfj
translocated              false
automation_permission     true
native_messaging_manifests  Google Chrome / Chromium / Brave / Microsoft Edge /
                            Vivaldi / Arc の 6 か所（いずれも path_exists: true）
```

manifest は**すでに存在するプロファイルディレクトリにだけ**書く。入っていないブラウザの
ディレクトリを勝手に作ることはしない。

展開された拡張フォルダ: `~/Library/Application Support/VIEWPORT BREAK/extension`
（`manifest.json` / `background.js` / `core.js` / `popup.*` / `icons/` / `EXTENSION_ID`）

### 4.4 Chrome へ読み込んで 375px（同スクリプト）

使い捨てプロファイル（`--user-data-dir`）に対して、**製品と同じコードパス**
（`viewport-break --install --chrome-dir <path>`）で manifest を設置してから測った。

| 手順 | 結果 |
| --- | --- |
| 拡張の読み込み | 返った ID が `ejlimgikbnaihoigbcmelaadniiminfj` = 固定 ID と一致 |
| service worker | `chrome-extension://ejlimgik.../background.js` を検出 |
| 拡張 → ヘルパー ping | `{"engine":"applescript:set-bounds","impl":"swift","path":"/Applications/VIEWPORT BREAK.app/Contents/MacOS/viewport-break","host_version":"2.0.0","ok":true}` |
| popup を開く | ボタン 320/360/**375**/390/414/430/640/768/1024/1280/1440/1920、現在値 1000 |
| **375 を押す** | popup の表示が `{"msg":"375px","curW":"375"}` |
| AppleScript 読み戻し | `width: 1000 → 375`（同一ウィンドウ id 1400165156）**reached_375: true** |
| `chrome.windows` API 読み戻し | `{"id":1400165156,"left":900,"top":120,"width":375,"height":760}` |

スクリーンショット: `shots/25-chrome-extensions.png`（読み込み後）、
`shots/30-before-375.png`（1000px）、`shots/31-after-375.png`（375px）。
後者 2 枚はウィンドウの実矩形を指定して撮っているので、画面上の幅がそのまま写っている。

**注意（測定経路の違い）**: 拡張の読み込みは CDP の `Extensions.loadUnpacked` で行った。
これは `chrome://extensions` の「パッケージ化されていない拡張機能を読み込む」と同じ結果に
なるが、**デベロッパーモードのトグルを ON にする操作は経ていない**
（`shots/25` でトグルが OFF のまま拡張が有効になっているのはこのため）。
購入者の手順ではトグル ON が必要で、その GUI 操作自体は未実測（§8）。

---

## 5. Gatekeeper の実挙動と、購入者に伝えるべきこと

### 5.1 初回起動時に出るもの（実測）

`/Applications` へ入れた quarantine 付きの .app を `open` した結果、
`CoreServicesUIAgent` が次のダイアログを出した（`shots/10-gatekeeper-first-launch.png`）。

> **"VIEWPORT BREAK.app" は開いていません**
>
> Apple は、"VIEWPORT BREAK.app" に Mac に損害を与えたり、プライバシーを侵害する
> 可能性のあるマルウェアが含まれていないことを検証できませんでした。
>
> ［ゴミ箱に入れる］（青・既定） ［完了］

**ここが一番の落とし穴で、実際に踏んだ。** 既定ボタンが「ゴミ箱に入れる」なので、
ダイアログに Return を送ったところ `/Applications/VIEWPORT BREAK.app` がゴミ箱へ移動した。
購入者が「とりあえず Enter」を押すと、買ったものが消える。
`はじめにお読みください.txt` にこの警告を明記した。

なお macOS 26 では、以前の「開発元を検証できないため…」という文言と
「開く」ボタン付きの右クリック回避（control + クリック →「開く」）**ではない**。
出口はシステム設定の「プライバシーとセキュリティ」→「このまま開く」だけ。

### 5.2 コマンドで見える状態

```
$ spctl -a -vvv -t exec "/Applications/VIEWPORT BREAK.app"
/Applications/VIEWPORT BREAK.app: rejected            (rc=3)

$ codesign --verify --verbose "/Applications/VIEWPORT BREAK.app"
valid on disk / satisfies its Designated Requirement   (rc=0)
```

ad-hoc 署名は**壊れていない**が、Gatekeeper の評価では拒否される。
つまり「署名が無効」なのではなく「Apple が誰が作ったか分からない」という扱い。

### 5.3 オートメーション（TCC）の許可

375 を最初に押したときに出るもの（`shots/40-automation-permission-prompt.png`）:

> **"VIEWPORT BREAK.app" が "Google Chrome.app" を制御するアクセスを要求しています。
> 制御を許可すると、"Google Chrome.app" の書類やデータにアクセスしたり、
> そのアプリ内で操作を実行したりできるようになります。**
>
> Chrome のウィンドウ幅を、Chrome 自身の下限（500px）より狭い 375px などへ
> 設定するために使います。
>
> ［許可しない］ ［許可］（青・既定）

説明文は `Info.plist` の `NSAppleEventsUsageDescription` に書いたもの。
**ここは Python 版から明確に良くなった点**で、`osascript` を呼ぶ実装だと
許可を求める主体が「python3」と表示されてしまう。`NSAppleScript` でインプロセス実行し、
バンドルの主実行ファイルが本物の Mach-O であるため、製品名で表示される。

### 5.4 購入者に必ず伝えること（`はじめにお読みください.txt` に反映済み）

1. Apple の公証を受けていないので、初回だけ許可の手順が要る
2. **最初のダイアログで Return を押さない。「ゴミ箱に入れる」が既定になっている**
3. システム設定 →「プライバシーとセキュリティ」→「このまま開く」（パスワード / Touch ID）
4. `chrome://extensions` でデベロッパーモードを ON にして拡張を読み込む
5. 「オートメーション」の許可を「許可」する。拒否すると 500px より狭くできない
6. `chrome://extensions` の「安全チェック」に
   「安全でない可能性がある 1 件の拡張機能を確認する／削除することをおすすめします」
   「Chrome では、この拡張機能の提供元を確認できません」が出る（`shots/25`）。
   ストア外の拡張に Chrome が必ず出すもので、動作には影響しない。**ゴミ箱アイコンを押さない**
7. アンインストール手順（`--uninstall`）

有料で売る以上、6 の表示は「壊れている / 騙された」と受け取られやすい。
販売ページ側にも先に書いておくべき項目として挙げておく。

---

## 6. 途中で設計を変えた点

### 6.1 Python → Swift（§1.1）

### 6.2 App Translocation — 実装しないと確実に壊れる

quarantine が付いたアプリを Finder でドラッグせずに実行すると、macOS は
`/private/var/folders/.../AppTranslocation/<uuid>/d/` に読み取り専用でコピーして起動する。
このとき `viewport-break` が自分のパスとして NM manifest に書く値は、
**その一時パスになり、次回起動時には存在しない**。購入者から見ると
「一度は動いたのに翌日動かない」という壊れ方をする。

対策として `translocationProblem()` を入れ、自分の実行パスが
`/AppTranslocation/` を含む場合と `/Volumes/` 配下の場合は**セットアップを実行せず拒否**する。
DMG をマウントしたまま中のアプリを直接実行したときの実測:

```
$ "/Volumes/VIEWPORT BREAK/VIEWPORT BREAK.app/Contents/MacOS/viewport-break" --install --json
{"error":"この App はディスクイメージの中から直接実行されています。\n\n
  VIEWPORT BREAK.app をアプリケーションフォルダへドラッグしてから、そちらを開いてください。",
 "ok":false}                                                              (rc=1)
```

`--doctor` にも `translocated` / `install_blocked` を出すようにした。

### 6.3 `xattr` コマンドを使わない

quarantine 属性の除去に `/usr/bin/xattr` を使うと、これも Python スクリプトなので §1.1 と
同じ理由で購入者の Mac で失敗する。`removexattr(2)` を直接呼ぶようにした。

---

## 7. SaaS 連動の現状 — **連動は存在しない**

指示 5 は「拡張がウェブアプリとどう通信しているか調べ、DMG インストールでも成立するか
判断する」だったが、調べた結果 **通信の実装が 1 行も無い**。壊れているのではなく、
まだ作られていない。

`extension/manifest.json` の宣言:

| キー | 値 |
| --- | --- |
| `permissions` | `["nativeMessaging"]` のみ |
| `optional_permissions` | なし |
| `host_permissions` | なし |
| `content_scripts` | なし |
| `externally_connectable` | なし |
| `web_accessible_resources` | なし |
| `content_security_policy` | なし |

コード側:

```
$ grep -nE 'fetch\(|XMLHttpRequest|WebSocket|externally_connectable|host_permissions|content_scripts|postMessage' extension/*.js extension/manifest.json
(該当なし)
```

**判定**: 現在の拡張はローカルの Chrome ウィンドウを操作するだけで、外部と一切通信しない。
したがって「DMG インストールでも SaaS 連動が成立するか」という問いに対しては
**成立も不成立も無い（対象が存在しない）**というのが正しい答えになる。

今後 SaaS 側と繋ぐときに、DMG 配布に固有の制約として効いてくるのは次の 2 点。

- **ウェブページから拡張を呼ぶには `externally_connectable` に SaaS のオリジンを列挙する**
  必要がある。拡張 ID は §2 で固定済みなので、SaaS 側は
  `chrome.runtime.sendMessage("ejlimgikbnaihoigbcmelaadniiminfj", ...)` を決め打ちで書ける。
  ここは DMG 配布でも問題にならない。
- **ライセンス認証を入れる場合、通信の実装場所は拡張とヘルパーのどちらでもよいが、
  ヘルパー（.app 側）に置く方が改竄しにくい。** ただし現状のヘルパーはネットワークを
  一切使わないので、使い始めるとファイアウォールの許可ダイアログが新たに出る。
  この挙動は未実測。

---

## 8. 未実測（推測を書かないための明示）

以下は**測っていない**。文書中の他の数値・文言はすべて実測。

1. **Finder で DMG からアプリケーションフォルダへドラッグする操作そのもの。**
   AppleScript の `duplicate` を試したところ、ターミナルに Finder の制御権限を求める
   TCC ダイアログが出た。この権限は付与しない判断をしたため、代わりに `ditto` でコピーし、
   ダウンロード済み DMG から実測した quarantine 値
   （`0281;6a93bf49;Chrome;1C4520A3-...`）を `.app` へ転記して同じ状態を作った。
   LaunchServices が行う伝播と一致するかは未確認。
2. **システム設定 →「プライバシーとセキュリティ」→「このまま開く」のクリック。**
   Gatekeeper の解除は `xattr -dr com.apple.quarantine` で代替した。
   ダイアログが出るところまでは実測済みだが、解除 UI の文言と挙動は未実測。
3. **`chrome://extensions` のデベロッパーモード トグルを ON にする GUI 操作**（§4.4 の注意）。
4. **Command Line Tools が入っていない Mac での動作。** Swift バイナリは依存なしで
   ユニバーサルなので動くはずだが、CLT 無しの実機では試していない。
5. **Intel Mac での実行。** `lipo -archs` で `x86_64 arm64` が入っていることは確認したが、
   実機での起動は未確認。
6. **公証済み版との比較。** 指示により署名・公証は行っていない。
7. **ファイアウォール許可ダイアログ**（§7 の 2 点目）。

---

## 9. 残課題

1. **公証（Notarization）。** $99/年の Apple Developer Program を取れば §5.1 の
   ダイアログは消え、購入者の手順は「ドラッグ → 開く」だけになる。
   有料製品としての体験差は大きい。取得は指示により行っていない。
2. **Chrome 安全チェックの警告（§5.4-6）。** 消す方法は事実上 2 つしかない。
   (a) Chrome Web Store に非公開/限定公開で載せる、
   (b) CRX に署名して配り、`ExtensionInstallForcelist` などの企業ポリシー経由で入れる。
   (b) は購入者に管理者権限のプロファイル導入を求めることになるので、個人向け販売では現実的でない。
   ストアに載せない方針を維持するなら、この警告は**説明で受けるしかない**。
3. ~~**拡張の表示名が製品名と違う。**~~ → **2026-08-31 解消。** `manifest.json` の `name` と
   `action.default_title` を "VIEWPORT BREAK" へ統一した。拡張 ID は `key` から導出されるので
   改名の影響を受けない（`ejlimgikbnaihoigbcmelaadniiminfj` のまま）。
   native messaging の `HOST_NAME = com.nanago.viewport_deck` は登録キーなので改名していない。
4. **ad-hoc 署名はビルドのたびに変わる。** 署名が変わると TCC のオートメーション許可が
   無効になり、アップデートのたびに購入者が再度「許可」を押すことになる。
   安定した Designated Requirement を得るには結局 Developer ID 署名が要る（＝課題 1 と同根）。
5. **Chrome が複数インスタンス起動している場合の AppleScript の対象。**
   `tell application "Google Chrome"` は実行中のどれか 1 つに解決される。
   使い捨てプロファイルでの測定中に実際に取り違えが起きた。
   購入者環境で複数プロファイルを同時に開いていると、意図しないウィンドウが縮む可能性がある。
6. **自動アップデート機構が無い。** 現状は DMG を配り直すしかない。
7. **ウィンドウ幅は Chrome 再起動で 500px に戻る**（既存の制約、`docs/WINDOW_FLOOR_2026-08-30.md`）。

---

## 付録: この作業で追加したファイル

| パス | 内容 |
| --- | --- |
| `packaging/helper/Sources/main.swift` | 配布用ヘルパー（Swift、依存なし、Python 版と同一プロトコル） |
| `packaging/build_dmg.sh` | ビルド〜 DMG 作成（`--app-only` 可） |
| `packaging/dmg/はじめにお読みください.txt` | 購入者向け手順（Gatekeeper の文言は実測に合わせて記載） |
| `tools/extension_id.py` | `key` → 拡張 ID の算出と manifest 検証 |
| `tools/make_extension_key.sh` | 鍵の新規作成と、更新が必要な 4 か所の提示 |
| `docs/evidence/dmg-installer-2026-08-30/run_download_gatekeeper.py` | ダウンロードと quarantine の実測 |
| `docs/evidence/dmg-installer-2026-08-30/run_gatekeeper_install.py` | インストールと Gatekeeper ダイアログの実測 |
| `docs/evidence/dmg-installer-2026-08-30/run_install_e2e.py` | セットアップ〜 375px の通し実測 |
| `docs/evidence/dmg-installer-2026-08-30/run_env_and_saas_checks.py` | 前提条件と SaaS 面の確認 |
| `docs/evidence/dmg-installer-2026-08-30/out/*.json` | 上記の生ログ |
| `docs/evidence/dmg-installer-2026-08-30/shots/*.png` | スクリーンショット 7 枚 |

---

# 追補（2026-08-30 15:00-15:35 JST）— 「応答しないため開けません」の原因と修正

オーナーの MacBook で、第一版の DMG が次の順で詰んだという報告に対する調査。

1. 「お使いの Mac を保護するために VIEWPORT BREAK.app がブロックされました / このまま開く」
2. その後「応答しないため開けません」になり、以後どうやっても開けない

対象コミット時点の成果物（`sha256 319787dd…`）を Mac mini（macOS 26.3.1 / 25D771280a）で
再現・実測した。証拠一式は `docs/evidence/app-hang-2026-08-30/`。

## 10. 結論 — 原因は 3 つ重なっていた

| # | 事象 | 実測での裏付け | 修正 |
| --- | --- | --- | --- |
| A | quarantine 付きの .app は Gatekeeper のブロック中、**バイナリがロードされないまま プロセスだけが残る**。この宙ぶらりんプロセスがある間、再度開いても LaunchServices は新しいインスタンスを起こさない | `lsappinfo` が `!cgsConnection !signalled flavor=[NULL] Version=[NULL] Arch=!!none` | 手順で quarantine を先に外す（§11） |
| B | `applicationDidFinishLaunching` が **kAEOpenApplication の Apple Event ハンドラの内側**で `NSAlert.runModal()` に入り、そこから返らない | `sample` のスタック（下記） | `DispatchQueue.main.async` で run loop の次のターンへ逃がした |
| C | DMG の中身が全て **0700 / 0600** で焼かれていた | `ls -la /Volumes/VIEWPORT BREAK` | `build_dmg.sh` でステージを 755/644 に正規化 |

**A が「応答しないため開けません」の直接原因**。B は A を悪化させる構造的欠陥、C は配布物としての不正。

### 10.1 A — 宙ぶらりんプロセス（決定的証拠）

quarantine を付けた .app を `/Applications` から開いた直後の `lsappinfo`:

```
pid = 33535 !cgsConnection !signalled type="Foreground" flavor=[ NULL ]  Version=[ NULL ]  Arch=!!none
```

正常に起動したときは `flavor=3 Version="1.0.0" Arch=ARM64`。
`Arch=!!none` は **Mach-O が読まれてすらいない**ことを示す。`sample` を取ると
メインスレッドは `_dyld_start` の 1 フレームだけだった。

このときの画面には `CoreServicesUIAgent` が次のダイアログを出していた
（`docs/evidence/app-hang-2026-08-30/gatekeeper-dialog.png`）:

> 「"VIEWPORT BREAK.app" は開いていません」
> 「Apple は、"VIEWPORT BREAK.app" に Mac に損害を与えたり、プライバシーを侵害する
>   可能性のあるマルウェアが含まれていないことを検証できませんでした。」
> ［ゴミ箱に入れる］［完了］

このダイアログを閉じずに再度開いても、新しいプロセスは起きない（実測: Finder 経由の
`open` を送っても pid が変わらない）。**オーナーが見た「応答しないため開けません」はこの状態**。
ダイアログの［完了］を押すと、宙ぶらりんプロセスも同時に消えることを確認した。

さらに、このダイアログが 1 枚残っている間は、**quarantine を外した別の .app を実行しても
ハングする**（`--version` すら返らない）。ダイアログを処理したあとは同じバイナリが即座に
`2.0.0` を返した。詰まりが後続に伝播するため、症状が「何をしても直らない」ように見える。

### 10.2 B — Apple Event ハンドラを塞いでいた

修正前、`sample` のメインスレッドは次のようになっていた（26 分間この状態で滞留）:

```
-[NSApplication run]
  → AEProcessAppleEvent                        ← kAEOpenApplication を処理中
    → -[NSApplication _handleAEOpenEvent:]
      → _sendFinishLaunchingNotification
        → SetupDelegate.applicationDidFinishLaunching
          → showSetupAlert()
            → -[NSAlert runModal]               ← ここから返らない
```

`applicationDidFinishLaunching` は 'oapp' ハンドラの内側から呼ばれる。ここで
`runModal()` に入ると、ハンドラは応答を返さないまま、セットアップのファイル I/O も
モーダルの待ち時間も全部その中で抱えることになる。

修正後（`docs/evidence/app-hang-2026-08-30/sample-after-fix-main-dispatch.txt`）:

```
__CFRUNLOOP_IS_SERVICING_THE_MAIN_DISPATCH_QUEUE__
  → showSetupAlert()
    → -[NSAlert runModal]
```

`AEProcessAppleEvent` の出現数は **0**。Apple Event ハンドラの外へ出た。

なお、この修正だけでは A は直らない（A はバイナリがロードされる前の話）。**手順の変更が必須**。

### 10.3 C — パーミッションが 0700 で焼かれていた

第一版の DMG:

```
drwx------@ VIEWPORT BREAK.app
-rwx------@ VIEWPORT BREAK.app/Contents/MacOS/viewport-break
```

ビルド機の `umask 077` がそのまま焼かれていた。参考までに `Google Chrome.app` は 0775。

原因は `cp -R`。macOS の `cp` は `-p` を付けない限りモードを引き継がず、コピー先で
umask が再適用される。**`$APP` 側を chmod しても、`$STAGE` へ `cp -R` した時点で 0700 に
戻り、それが DMG へ焼かれていた**（一度この順序で直そうとして失敗し、実測で気付いた）。
正規化は `hdiutil create` の直前、`$STAGE` に対して行う。

### 10.4 仮説の検証結果

依頼で挙がっていた 3 仮説の判定:

| 仮説 | 判定 | 根拠 |
| --- | --- | --- |
| 1. `LSUIElement=true` が無く、UI を出さない常駐ヘルパーをダブルクリックした | **否定** | このアプリは NSAlert でセットアップ結果を出す GUI 設計。`ApplicationType="Foreground"` が正しく、`LSUIElement` を付けてはいけない。**ダブルクリックする設計で合っている** |
| 2. ad-hoc 署名 + quarantine による translocation | **成立するが主因ではない** | quarantine 付きだと `/Applications` に置いても `/private/var/folders/…/AppTranslocation/<UUID>/d/` から実行されることを実測。ただしアプリはこれを検出して案内を出す（設計どおり）。ここまで到達する前に A で止まる |
| 3. 起動直後に stdin を待ってブロックしている | **否定** | 引数なし起動は `guiSetup()` へ分岐する。`serve()` に入るのは `chrome-extension://` 付きで起動されたときだけ |

## 10.5 修正版の配布物

| 項目 | 値 |
| --- | --- |
| ファイル | `VIEWPORT BREAK 1.0.0.dmg`（193K） |
| sha256 | `c2d1411f17abb9991e43f6c594ac86d579dc03062aaa272e40ded01239480114` |
| Dropbox | （共有 URL は非公開。配布担当者が Dropbox の `/viewport-break/` から取得する） |
| 配置 | Dropbox app sandbox `/viewport-break/` |

共有 URL から実際にダウンロードして sha256 がローカルの成果物と一致することを確認済み。
版番号は 1.0.0 のまま据え置き（中身は差し替わっている）。

## 11. 購入者が踏む手順（実測に基づく確定版）

`packaging/dmg/はじめにお読みください.txt` に反映済み。**手順 2 が新規で、これが本質**。

1. ダウンロードした DMG を**まだ開かない**
2. ターミナルで 1 行:
   ```
   xattr -dr com.apple.quarantine ~/Downloads/"VIEWPORT BREAK 1.0.0.dmg"
   ```
3. DMG をダブルクリックして開き、`VIEWPORT BREAK` を `Applications` へドラッグ
4. アプリケーションフォルダの `VIEWPORT BREAK` をダブルクリック
   → **Gatekeeper のダイアログは出ず**、「VIEWPORT BREAK の準備ができました」が出る
5. 案内どおり Chrome に拡張を読み込む
6. 初回だけオートメーション許可（§5.3 のまま）

### 11.1 なぜ DMG の段階で外すのか（実測）

quarantine された DMG をマウントすると、**中身のファイルには属性が見えない**のに、
そこから `/Applications` へコピーすると `0283;00000000;;` が付く。**`ditto` でも `cp -R` でも
同じく付いた**（ボリューム単位で伝播するため、コピー方法では回避できない）。

一方、**DMG 自体の quarantine を先に外してからマウントすると、コピー先に属性は付かない**。
だから外すのは DMG の段階でなければならない。

### 11.2 通しで確認した結果（2026-08-30 15:30-15:31）

sha256 `c2d1411f…` の DMG に quarantine を付け（ダウンロード再現）、上の手順どおりに実行:

| 確認項目 | 結果 |
| --- | --- |
| Gatekeeper ダイアログ | 出ない（`CoreServicesUIAgent` の onscreen window = 0） |
| App Translocation | されない（`/Applications/…` から直接起動） |
| LaunchServices | `flavor=3 Version="1.0.0" Arch=ARM64` = 正常ロード |
| 画面のアラート | 「VIEWPORT BREAK の準備ができました」 |
| native messaging manifest | 6 ブラウザぶん設置、`path_exists: true` |
| 拡張の展開 | 8 エントリ |
| `--doctor` | `automation_permission: true` / `chrome_running: true` / `extension_installed: true` |

### 11.3 既に詰まっている場合の復旧（実測で確認済み）

1. 「開いていません」のダイアログが出ていたら **［完了］**（［ゴミ箱に入れる］が既定選択なので Return を押さない）
2. ターミナルで:
   ```
   pkill -f "VIEWPORT BREAK"
   xattr -dr com.apple.quarantine "/Applications/VIEWPORT BREAK.app"
   ```
3. もう一度ダブルクリック

## 12. この追補で入れた変更

| ファイル | 変更 |
| --- | --- |
| `packaging/helper/Sources/main.swift` | `applicationDidFinishLaunching` を `DispatchQueue.main.async` へ退避（§10.2）。`hasQuarantine()` / `originalBundleURL()` / `recoverFromTranslocation()` を追加 |
| `packaging/build_dmg.sh` | `$STAGE` のパーミッション正規化（§10.3）、焼く前の `codesign --verify`、0700 残りの検出 |
| `packaging/dmg/はじめにお読みください.txt` | 手順 2（quarantine 除去）を新設し全面改訂。復旧手順を追加 |

### 12.1 未検証 — translocation の自己復帰

`recoverFromTranslocation()` は、translocated 実行を検出したら
`SecTranslocateCreateOriginalPathForURL`（Security.framework にシンボルはあるが Swift へ
import されないため `dlsym` で解決。解決できることは実測済み）で元パスを取り、
そこの quarantine を落として開き直す。

**この経路は通し実測できていない。** quarantine が付いている状態では A（Gatekeeper のブロック）
が先に効いてバイナリがロードされないため、コードが走る条件を Mac mini 上で作れなかった。
作るには GUI で「このまま開く」を押して署名を承認する必要があり、認証を伴うのでオーナーの
手作業になる。失敗時は従来どおり案内アラートへフォールバックする設計なので、
入っていることで悪化はしない。

## 13. 残る制約

`§11` の手順 2 でターミナルを 1 行使わせているのは、**ad-hoc 署名のままでは他に確実な方法が
無い**ため。Apple の公証（Developer ID + Notarization、年 99 ドル）を通せば、この手順も
Gatekeeper のダイアログも丸ごと不要になり、購入者はダブルクリックだけで済む。
配布を続けるなら、ここは費用対効果の判断がいる。

## 14. 1.0.1 ローカル配布候補（未公開）

この節は §10.5〜§12 の 1.0.0 配布記録を上書きせず、今回の修正版を別バージョンとして
記録する。状態は **PREPARED_NOT_PUBLISHED**。Dropbox 上の 1.0.0 は変更していない。

| 項目 | 値 |
| --- | --- |
| ファイル | `build/VIEWPORT BREAK 1.0.1.dmg` |
| sha256 | `8ebb2689204e55b9cefa29acc4126fae1f60f725636e4db2639eb1cab464504e` |
| アプリ | 1.0.1 / universal (`x86_64 arm64`) / ad-hoc署名 |
| 同梱拡張 | 1.4.1 |
| native host | 2.0.1 |
| 外部事前手順 | `build/VIEWPORT BREAK 1.0.1 - BEFORE OPENING.txt` |
| checksum | `build/VIEWPORT BREAK 1.0.1.dmg.sha256` |

1.0.1 では次を修正した。

- Native Messaging の新規登録先を標準版 Google Chrome の user data dir に限定し、旧版が
  Brave / Edge / Vivaldi / Arc / Canary / Chromium へ置いた manifest は更新時に削除する
- manifest を原子的に書き、展開済み拡張は検証済み一時ディレクトリとの rename swap で更新する
- `--uninstall` で全既知 manifest と `~/Library/Application Support/VIEWPORT BREAK` を削除し、
  削除失敗を非0終了と JSON の `failures` で返す
- popup の存在しない `README/install.sh` 案内を廃止し、ショートカット失敗時は拡張アイコンへ
  赤い `!` バッジとエラー内容を表示する
- DMG と別に、開く前の SHA-256 照合・Finder ドラッグ式 `xattr` 手順を生成する
- ビルド時に 0700/0600 の残存、ad-hoc署名、DMG の内部 checksum を fail-closed で検証する

配布するときは DMG だけを差し替えず、外部事前手順と SHA-256 を購入ページまたは購入メールへ
同時に掲載する。同じダウンロード元に checksum ファイルを置くだけでは配布元の真正性を
追加で証明できない。

## 15. 1.0.2 ローカル配布候補（未公開）

§14 の 1.0.1 記録を上書きせず、別バージョンとして記録する。状態は
**PREPARED_NOT_PUBLISHED**。Dropbox 上の 1.0.0 / 1.0.1 は変更していない。

| 項目 | 値 |
| --- | --- |
| ファイル | `build/VIEWPORT BREAK 1.0.2.dmg` |
| sha256 | `5a770981634b17d1d0d49771d7e16658a39594c05dff7c6d3fae0a01a053b09c`（内部記録。購入ページ・購入メール・手順書へ掲載しない） |
| アプリ | 1.0.2 / universal (`x86_64 arm64`) / ad-hoc署名 |
| 同梱拡張 | 1.4.1（1.0.1 から変更なし） |
| native host | 2.0.1（1.0.1 から変更なし） |
| 外部事前手順 | `build/VIEWPORT BREAK 1.0.2 - BEFORE OPENING.txt` |
| checksum | `build/VIEWPORT BREAK 1.0.2.dmg.sha256` |

1.0.2 で変えたのはバージョン番号だけで、コードの挙動は 1.0.1 と同じ。
c626a72（配布物から SHA-256 照合を廃止）で DMG の中身が変わったのに 1.0.1 のまま
再ビルドされ、既存の配布物と「同じ番号で中身違い」になっていた。それを解消するため
パッチ番号を上げた（2026-08-31 オーナー決裁: 差し替えるがバージョンは上げる）。

> [!warning]
> §14 の「配布するときは DMG だけを差し替えず、外部事前手順と SHA-256 を購入ページ
> または購入メールへ同時に掲載する」は、2026-08-31 のオーナー決裁で廃止した。
> 購入者向けの SHA-256 照合は行わない。同節の sha256 `8ebb2689…` は当時の記録で、
> 再ビルド後の実物とは一致しない。
