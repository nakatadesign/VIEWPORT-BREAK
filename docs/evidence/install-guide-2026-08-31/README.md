# インストール手順書 書き直しのための実測 — 2026-08-31

対象: VIEWPORT BREAK 1.0.1（ad-hoc 署名のみ / Developer ID 署名なし / 公証なし）
実測機: Mac mini, macOS 26.3.1 (25D771280a), Apple Silicon
実測者: dispatch vb-install-guide-rewrite-20260831

購入者と同じ条件を作るため、ビルド済み DMG を複製して既存の拡張属性を消し、
ブラウザのダウンロードと同じ形の quarantine を付け直してから通した。

    xattr -c test.dmg
    xattr -w com.apple.quarantine "0081;<hex time>;Google Chrome;<uuid>" test.dmg

---

## 1. quarantine 付き DMG は、確認ダイアログなしでマウントされた

`open` でマウントした時点では何のダイアログも出ず、そのまま Finder ウインドウが開いた。
旧手順書が書いていた「"…dmg" はインターネットからダウンロードされたディスクイメージです。
開いてもよろしいですか?」は、この OS・この経路では出なかった。

DMG ウインドウの中身は左から `Applications`（エイリアス） / `VIEWPORT BREAK.app` /
`はじめにお読みください.txt`。アイコン位置は build_dmg.sh が指定していないため
名前順の自動整列で、旧手順書の「左の VIEWPORT BREAK を右の Applications へ」は左右が逆。

## 2. アプリの初回起動はブロックされる（01-gatekeeper-block-dialog.png）

DMG から /Applications へコピーした .app には quarantine が伝播し（`0281;…`）、
ダブルクリックすると次が出て起動できない。

    「"VIEWPORT BREAK.app" は開いていません」
    「Apple は、"VIEWPORT BREAK.app" に Mac に損害を与えたり、プライバシーを
      侵害する可能性のあるマルウェアが含まれていないことを検証できませんでした。」
    ボタン: ［ゴミ箱に入れる］（青・デフォルト） ［完了］

**デフォルトボタンが［ゴミ箱に入れる］である。** Return で確定するとアプリが消える。
旧手順書が書いていた「開発元によって認証されていないため、開けません。」は
この OS では出ない文言だった。

この時点でプロセスは App Translocation 配下
（`/private/var/folders/…/AppTranslocation/<uuid>/d/VIEWPORT BREAK.app`）で
起動しようとして止まる。旧版で「応答しないため開けません」になっていた状態と同じ。

## 3. 右クリック →「開く」では回避できない（05-rightclick-open-also-blocked.png）

Finder のコンテキストメニューに「開く」は今も存在するが、選んでも 2 と同一の
ブロックダイアログが出た。macOS 26.3.1 では右クリック経由の Gatekeeper 回避は効かない。

## 4. システム設定に［このまま開く］が出る（02-settings-open-anyway.png）

ブロックの後、システム設定 → プライバシーとセキュリティ → 一番下の「セキュリティ」に
次が出た。ad-hoc 署名だけのアプリでも出ることを実機で確認した（従来は未確認だった項目）。

    「お使いの Mac を保護するために "VIEWPORT BREAK.app" がブロックされました。」
    ボタン: ［このまま開く］

同じ節の上に「アプリケーションの実行許可」＝「App Store と既知のデベロッパ」がある。

## 5.［このまま開く］の後は 2 段階（03 / 04）

5-1. 確認ダイアログ（03-open-anyway-confirm.png）

    「"VIEWPORT BREAK.app" を開きますか?」
    「Apple は、このアプリに Mac に損害を与えたり、プライバシーを侵害する可能性のある
      マルウェアが含まれていないことを検証できません。信頼できる提供元からのもので
      あることが確認できない限り、このアプリを開いていないでください。」
    ボタン: ［ゴミ箱に入れる］（青・デフォルト） ［このまま開く］ ［完了］

ここでもデフォルトは［ゴミ箱に入れる］。

5-2. 管理者認証（04-open-anyway-auth.png）

    「プライバシーとセキュリティ」
    「Mac に損害を与えたり、プライバシーを侵害する可能性のあるアプリを開こうとしています」
    「許可するには管理者のユーザ名とパスワードを入力してください。」
    ユーザ名欄 + パスワード欄 + ［キャンセル］［OK］

**未確認**: この Mac mini のログインパスワードを worker は持たないため、
ここでキャンセルした。パスワード入力後にアプリが実際に開くところまでは未確認。
Touch ID 搭載機では指紋で代替されるはずだが、それも未確認。

## 6. quarantine を外せば、そのまま起動してセットアップが通る（06-app-setup-dialog.png）

    xattr -dr com.apple.quarantine "/Applications/VIEWPORT BREAK.app"

この後は Gatekeeper のダイアログを一切出さずに起動し、App Translocation も起きず
（`translocated: false`）、セットアップが完了した。アプリが出す案内は

    「VIEWPORT BREAK の準備ができました」
    「あと 3 ステップで使えます。」…
    ボタン: ［閉じる］ ［拡張フォルダを Finder で開く］

`--doctor --json` の結果:

    extension_installed: true
    extension_id: ejlimgikbnaihoigbcmelaadniiminfj
    native_messaging_manifests[0].path: /Applications/VIEWPORT BREAK.app/Contents/MacOS/viewport-break
    path_exists: true
    translocated: false
    automation_permission: true

## 7. Chrome 側の実文言

chrome://extensions 上の表示は「拡張機能」「デベロッパー モード」
「パッケージ化されていない拡張機能を読み込む」。手順書の引用と一致。

## 8. 旧手順書の SHA-256 が実物と合っていない

    実物 build/VIEWPORT BREAK 1.0.1.dmg  fc257912d97dd853bf217b6a106e689128452fb7252db4a7ade827a6734d30aa
    build/…dmg.sha256                    fc257912…（一致）
    build/…BEFORE OPENING.txt            fc257912…（一致）
    build/…MacBook入れ直し手順.txt       8ebb2689204e55b9cefa29acc4126fae1f60f725636e4db2639eb1cab464504e（不一致）

入れ直し手順.txt の値だけ古い。この手順書どおりに照合すると、正しい DMG が
「改変されている」と判定される。

---

## 未確認事項

- 5-2 の管理者パスワード入力後にアプリが開くところ（worker がパスワードを持たないため）。
- Touch ID による代替。
- VIEWPORT BREAK 自身のオートメーション許可ダイアログの実文言。この Mac では既に
  許可済み（`automation_permission: true`）で、再表示させるには許可を取り消す必要があり、
  合成クリックでは TCC ダイアログを操作できないため、取り消すと復旧できなくなる。
  そのため同型ダイアログ（ターミナル → Finder）で文言の型だけ確認した:
  「"A" が "B" を制御するアクセスを要求しています。制御を許可すると、"B" の書類やデータに
  アクセスしたり、そのアプリ内で操作を実行したりできるようになります。」
  ボタンは［許可しない］［許可］。
- MacBook 実機での通し実行。

---

## 9. Chrome の拡張フォルダ選択も実操作で確認（07 / 08 / 09）

chrome://extensions の「パッケージ化されていない拡張機能を読み込む」を押すと出る窓は
macOS 標準の選択パネルで、見出しは「拡張機能のディレクトリを選択してください。」。
確定ボタンは［開く］ではなく **［選択］**。

⌘ + Shift + G は効き、「移動先:」欄に

    ~/Library/Application Support/VIEWPORT BREAK

を貼り付けると「ユーザ › macmini › ライブラリ › Application Support › VIEWPORT BREAK」
と解決された。Return で移動し、右列の `extension` を選んで［選択］で読み込み完了。
chrome://extensions 上で「VIEWPORT BREAK 1.4.1 / ID: ejlimgikbnaihoigbcmelaadniiminfj」
として読み込まれることを確認した（09-extension-loaded.png）。
