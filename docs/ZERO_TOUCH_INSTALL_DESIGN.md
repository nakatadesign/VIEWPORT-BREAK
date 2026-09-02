# VIEWPORT BREAK — ゼロタッチ配布 設計

作成 2026-08-30 / 前提資料 `docs/DMG_DISTRIBUTION_2026-08-30.md`
検証機 macOS 26.3.1 (25D771280a, arm64) + Google Chrome 151.0.7922.174

**目的**: 購入者にターミナルで `xattr` を打たせずに、DMG を開いてドラッグするだけで
Chrome 拡張の native messaging まで通る配布方式を決める。

**結論（先に）**: **Apple Developer ID 署名 + notarization + stapling を採用する。**
これが「ターミナル 1 行」を消す唯一の方法で、比較した他 2 案（Chrome ポリシー配布 /
pkg インストーラ）はどちらも単独ではこの目的を達成できず、しかも実行するには結局
同じ Developer ID が要る。費用は年 99 USD、加入から配布物差し替えまで実作業 1 日 + 加入審査待ち。

拡張の読み込み（デベロッパーモード ON → 未パッケージ拡張を読み込む → 安全チェック警告）は
Developer ID では消えない。ここを消すには Chrome ウェブストアの**限定公開**が現実解だが、
既存の「ストア非経由」方針の変更になるため、**オーナーの判断が要る（§3.3）**。

**未検証**: 本設計の署名・公証・ポリシー・pkg のいずれも**実機で通していない**。
本機には署名 ID が 1 件も無く（`security find-identity -v -p codesigning` → `0 valid identities found`）、
MDM 未登録・`/Library/Managed Preferences` 不在のため、ポリシー適用も実施できない。
実測できたのは §7 に列挙した前提条件だけで、§4 のステップは**設計であって実績ではない**。

---

## 1. 現状の詰まりの因果

### 1.1 因果の連鎖（1 本道）

```
[根因] Apple が発行者を検証できない（Developer ID 署名も notarization ticket も無い）
   │
   ├─(1) 購入者が DMG をダウンロード
   │      → Chrome が com.apple.quarantine = 0281;6a93bf49;Chrome;<UUID> を DMG に付ける
   │
   ├─(2) DMG をマウントして .app を /Applications へコピー
   │      → quarantine はボリューム単位で伝播し、コピー先に 0283;00000000;; が付く
   │         （ditto でも cp -R でも同じ。コピー方法では回避できない）
   │
   ├─(3) /Applications の .app をダブルクリック
   │      → LaunchServices は exec 前に Gatekeeper 評価に入る
   │      → spctl -a -t exec = rejected（ad-hoc 署名は「無効」ではなく「発行者不明」）
   │      → CoreServicesUIAgent が「"VIEWPORT BREAK.app" は開いていません」を表示
   │         既定ボタンは［ゴミ箱に入れる］（Return で製品が消える）
   │
   ├─(4) このときプロセスは生成されるが Mach-O はロードされない
   │      → lsappinfo: flavor=[NULL] Version=[NULL] Arch=!!none（正常時は flavor=3 / ARM64）
   │      → sample のメインスレッドは _dyld_start の 1 フレームだけ
   │
   ├─(5) この「宙ぶらりんプロセス」が LaunchServices の起動済み枠を占有する
   │      → 再度ダブルクリックしても新しいインスタンスが起きない
   │      → 購入者から見える症状 =「応答しないため開けません」
   │
   ├─(6) 汚染が伝播する: このダイアログが 1 枚出ている間は、
   │      quarantine を外した別の .app すらハングする（--version すら返らない）
   │      → 「何をしても直らない」ように見える
   │
   └─(7) macOS 26 の出口は システム設定 →「プライバシーとセキュリティ」→「このまま開く」だけ。
          control + クリック →「開く」の回避路は無い。
          → 現行の回避策が「ターミナルで xattr -dr com.apple.quarantine」＝ 今回消したい手順
```

### 1.2 居座りプロセスを悪化させていた実装欠陥（修正済み・ただし主因ではない）

`applicationDidFinishLaunching` が `kAEOpenApplication` の Apple Event ハンドラの内側で
`NSAlert.runModal()` に入り、そこから返らなかった。`DispatchQueue.main.async` で
run loop の次のターンへ逃がし、`AEProcessAppleEvent` の出現数 0 を確認済み。

**この修正は (4)〜(5) を直さない。** (4) はバイナリがロードされる前の話で、
アプリ側のコードは 1 行も走っていない。**手順か署名のどちらかを変えない限り消えない。**

### 1.3 「xattr を打たせる」現行手順の位置づけ

`packaging/dmg/はじめにお読みください.txt` の手順 2 は、
DMG をマウントする**前**に quarantine を外させる。§1.1 (2) の伝播をボリューム単位で断つので
効果は確実で、実測でも Gatekeeper ダイアログは出なくなった。

だがこれは**症状の除去であって根因の除去ではない**。有料製品として次の 3 つが残る。

| 残る問題 | 内容 |
| --- | --- |
| 心理的ハードル | 「ターミナルにコマンドを貼れ」は、セキュリティ警告を自力で無効化させる指示に見える |
| 打ち間違いの事故 | ファイル名にスペースがあり、引用符を落とすと失敗する。パスが違えば無言で成功して見える |
| **アップデート毎の TCC 再許可** | ad-hoc 署名はビルドのたびに変わる → Designated Requirement が変わる → オートメーション許可が無効化され、購入者が毎回「許可」を押し直す |

3 番目は署名の問題であって手順では直らない。**§1.1 の根因と同じ根**を持つ。

---

## 2. 配布方式の比較

### 2.1 まず目的を 2 軸に分解する（これをやらないと 3 案は比較できない）

| 軸 | 何を消したいか | 現在の状態 |
| --- | --- | --- |
| **軸 A: macOS 側** | Gatekeeper ダイアログと `xattr` 手順 | ad-hoc 署名 → 止まる |
| **軸 B: Chrome 側** | デベロッパーモード ON / 未パッケージ拡張の読み込み / 安全チェック警告 | ストア外 unpacked → 全部出る |

指定された 3 案は、この 2 軸に**別々に**効く。同じ土俵の 3 択ではない。

| 案 | 軸 A | 軸 B |
| --- | --- | --- |
| A. Developer ID 署名 + notarization | **解決する** | 効かない |
| B. Chrome ポリシー配布 | 効かない（むしろ悪化） | **解決する** |
| C. pkg インストーラ | 単独では解決しない | 単独では解決しない（B の配送手段にはなる） |

### 2.2 案 A — Apple Developer ID 署名 + notarization

Apple Developer Program に加入し `Developer ID Application` 証明書で署名、Apple の公証サービスへ
提出して ticket を受け取り、成果物に staple する。

| 項目 | 内容 |
| --- | --- |
| **費用** | **99 USD / 年**（Apple Developer Program。日本での請求は円建て・税込。2026-08 時点の正確な円価格は未確認）。公証の提出自体は追加費用なし・回数無制限 |
| **所要日数** | 個人アカウント: 申込から承認まで **1〜2 営業日**が目安（本人確認が入ると延びる）。法人アカウントは D-U-N-S 番号の取得を含め **2〜4 週間**。承認後の実作業（ビルド改修 + 公証 + 検証）は **1 日**。公証 1 回の所要は数分〜1 時間 |
| **購入者の手順** | ダウンロード → ダブルクリック → **ドラッグ → 開く**。警告ダイアログなし、ターミナルなし |
| **効くもの** | §1.1 の (1)〜(7) が丸ごと消える。加えて Designated Requirement が安定するので、**アップデートしても TCC のオートメーション許可が維持される**（§1.3 の 3 番目） |
| **効かないもの** | 軸 B。拡張の読み込みは今までどおり手作業で、安全チェック警告も出る |
| **前提の追加作業** | Hardened Runtime が必須になる。Hardened Runtime 下で Apple Events を送るには `com.apple.security.automation.apple-events` entitlement が要る。**これを付け忘れると 375px 動作が壊れる**（§4 / §6） |
| **リスク** | 加入審査の遅延。証明書失効時の影響（§6.3） |

### 2.3 案 B — Chrome ポリシー配布

`ExtensionInstallForcelist` / `ExtensionSettings` で拡張を強制インストールする。
本機の Chrome 151 バンドルに同梱されたポリシースキーマから、以下を**実測で確認済み**。

- `ExtensionInstallForcelist`: 各要素は `<拡張 ID>;<update URL>`。update URL の scheme は
  **http / https / file** が使える。省略時はウェブストアの update URL。
  → **ストア外の CRX を自前ホストして強制インストールできる**（外部インストール機構と違い、
    ポリシー経由はストア掲載が要らない）
- `ExtensionDeveloperModeSettings` / `ExtensionUnpublishedAvailability` /
  `NativeMessagingAllowlist` / `NativeMessagingBlocklist` / `NativeMessagingUserLevelHosts` も存在

| 項目 | 内容 |
| --- | --- |
| **費用** | ポリシー自体は **0 円**。ただし配送手段が要る: ①MDM（1 台あたり月数百円〜、個人購入者には適用不可） ②構成プロファイル `.mobileconfig` を購入者が手動導入 ③root で `/Library/Managed Preferences/com.google.Chrome.plist` を設置（＝案 C が必要） |
| **所要日数** | update manifest XML と CRX ホスティングの構築に **1〜2 日**。CRX 署名鍵の運用設計を含めるとさらに 1 日 |
| **購入者の手順** | プロファイル導入: ダウンロード → ダブルクリック → **システム設定 → 一般 → デバイス管理**で承認 → **管理者パスワード**。未署名プロファイルは追加の警告あり |
| **効くもの** | 軸 B が完全に消える。デベロッパーモード不要、安全チェック警告なし、ID 固定、自動更新も回せる |
| **効かないもの** | **軸 A は 1 ミリも解決しない。** .app の Gatekeeper は別問題として残る |
| **致命的な難点** | 「ターミナル 1 行」を「構成プロファイル導入 + 管理者パスワード + システム設定操作」に置き換えるだけで、**購入者の手数は増える**。しかも強制インストールされた拡張は購入者が自分で削除できず、個人向け有料製品としては過剰な支配になる |
| **未検証** | 本機は MDM 未登録（`profiles status`: `Enrolled via DEP: No` / `MDM enrollment: No`）で `/Library/Managed Preferences` も存在しない。ポリシー適用の実機確認は**未実施**（実施にはオーナーの管理者パスワードと GUI 操作が要るため） |

### 2.4 案 C — pkg インストーラ

`pkgbuild` / `productbuild`（両方とも本機に存在を確認）で `.pkg` を作り、
postinstall スクリプトを root 権限で走らせる。

| 項目 | 内容 |
| --- | --- |
| **費用** | ツールは **0 円**。ただし署名には `Developer ID Installer` 証明書が要り、これは **案 A と同じ 99 USD / 年**に含まれる |
| **所要日数** | pkg 化 + postinstall の実装と検証で **1〜2 日** |
| **できること** | root で `/Library/Google/Chrome/NativeMessagingHosts/` に**全ユーザー共通**の manifest を置ける（このディレクトリは本機に実在し `root:wheel` で、Apple 自身が `com.apple.passwordmanager.json` を置いている＝実際に使われている経路）。案 B のポリシー plist も同時に設置できる。アプリを 1 度も起動させずにセットアップを完了できる |
| **できないこと** | **未署名 pkg も Gatekeeper に止まる。** 軸 A は解決しない。署名・公証すれば通るが、それは案 A を実施したということ |
| **副作用** | インストール時に**管理者パスワードが必ず要る**。現在の「ドラッグするだけ」より重い。アンインストールが Finder のドラッグでなくなり、専用手順が必要になる |
| **未検証** | pkg の作成・実行は**未実施** |

### 2.5 軸 B の第 4 選択肢 — Chrome ウェブストア限定公開（比較指定外だが必要なので併記）

指定された 3 案のどれも、「個人購入者に対して軸 B を軽く解決する」ことができない。
そのため実務上の第 4 選択肢を挙げる。

| 項目 | 内容 |
| --- | --- |
| **費用** | 開発者登録 **5 USD（一回限り）** |
| **所要日数** | 初回審査は数時間〜数営業日。`nativeMessaging` 権限があるとレビューが長引くことがある（**未検証**・一般的な目安） |
| **効くもの** | 限定公開（unlisted）なら検索に出ず、URL を知っている人だけが入れられる。デベロッパーモード不要、安全チェック警告なし、自動更新あり、購入者の操作は**リンクを開いて「Chrome に追加」の 1 クリック** |
| **難点** | ①既存の「ストア非経由」方針の変更（**要オーナー判断**） ②ストアが採番する拡張 ID は現在の `ejlimgikbnaihoigbcmelaadniiminfj` と変わる可能性があり、その場合 4 か所の同時更新が要る（§4.6） ③審査でリジェクトされうる |

### 2.6 比較まとめ

| | 案 A 署名+公証 | 案 B ポリシー | 案 C pkg | （案 D ストア限定公開） |
| --- | --- | --- | --- | --- |
| 費用 | 99 USD/年 | 0 円（配送手段は別） | 0 円（署名するなら A 込み） | 5 USD 一回 |
| 所要日数 | 加入 1〜2 営業日 + 実作業 1 日 | 1〜3 日 | 1〜2 日 | 審査 数時間〜数営業日 |
| ターミナル不要になるか | **なる** | ならない | ならない | 該当せず |
| 購入者の追加操作 | **なし** | プロファイル導入 + 管理者パスワード | 管理者パスワード | 1 クリック |
| 拡張の読み込みが消えるか | 消えない | **消える** | 消えない | **消える** |
| 単独で目的を達成するか | **軸 A を達成** | しない | しない | 軸 B を達成 |
| 他案への依存 | なし | C か MDM が要る | 署名するなら A が要る | なし |

---

## 3. 推奨案

### 3.1 推奨 — 案 A（Developer ID 署名 + notarization + stapling）を採用し、DMG ドラッグ配布を維持する

配布物の形は今のまま（DMG + Applications へのシンボリックリンク + アプリ初回起動で
native messaging manifest を自動設置）。**変えるのは署名だけ。**

### 3.2 選定理由

1. **目的に直接効く唯一の案。** 「ターミナルで xattr を打たせない」は軸 A の問題で、
   軸 A を解決するのは案 A だけ。案 B と案 C は軸 A を一切動かさない。
2. **他 2 案の前提になっている。** 案 C を警告なしで配るには `Developer ID Installer` 署名が要り、
   案 B を個人購入者へ届けるには案 C か MDM が要る。**どの道を通っても 99 USD は発生する**ので、
   最短で効く案 A に先に払うのが合理的。
3. **購入者の手数が純減する唯一の案。** 案 B / C は手数を「ターミナル → 管理者パスワード +
   システム設定」に置き換えるだけで、体験は良くならない。案 A は手順が丸ごと消える。
4. **既存コードの変更が最小。** `packaging/build_dmg.sh` の
   署名行の差し替えと entitlements 追加だけ。Swift ヘルパー（約 660 行）も拡張も無改修。
   translocation 対策・パーミッション正規化・Apple Event ハンドラ修正といった既存の実測資産が全部生きる。
5. **アップデート体験の欠陥が同時に直る。** ad-hoc 署名がビルド毎に変わる問題（§1.3）が
   Developer ID で安定し、購入者はアップデートのたびにオートメーション許可を押し直さなくて済む。
6. **案 B の副作用が個人向け販売に合わない。** 強制インストールされた拡張は購入者が削除できない。
   有料製品としてこれは支配的すぎる。

### 3.3 拡張側（軸 B）は第 2 段として分離し、オーナー判断を仰ぐ

案 A を入れても、購入者には**拡張の読み込み操作と安全チェック警告が残る**。
これを消す現実解は §2.5 のストア限定公開だが、既存の「ストア非経由」方針の変更にあたる。

**推奨は「案 A を先に実行し、ストア限定公開は方針判断を得てから第 2 段として着手」。**
案 A の実装はストアの採否と独立しており、後から拡張 ID だけ差し替えれば済む（§4.6）。

### 3.4 採らなかった案と理由

| 採らなかった案 | 理由 |
| --- | --- |
| 案 B 単独 | 軸 A を解決しない。購入者の手数が増える。強制インストールが個人向けに過剰 |
| 案 C 単独 | 未署名 pkg も Gatekeeper に止まる。管理者パスワードが増え、アンインストールが重くなる |
| 案 A + 案 C（署名済み pkg） | 案 A だけで目的を達成できるのに管理者パスワードを 1 つ足すことになる。全ユーザー共通 manifest の利点は、購入者が 1 人 1 台の想定では効かない |
| 現行の xattr 手順を磨く（`.command` ファイル同梱等） | `.command` も quarantine の対象で、二重に警告が出る。根因が残る |
| 何もしない | §1.3 の 3 リスクが残り続ける |

---

## 4. 実装ステップ

パスはすべてリポジトリルートからの相対で記す。

### 4.0 前提 — オーナーの GO

Apple Developer Program（99 USD / 年）の加入判断はオーナーのもの。**加入前に着手できるのは
4.1 のドライラン（entitlements 追加と ad-hoc のままでの動作確認）まで。**

### 4.1 Hardened Runtime + entitlements の準備（加入前に着手可）

Hardened Runtime を有効にすると Apple Events の送信が既定で塞がる。
本製品は `NSAppleScript` で Chrome を操作するため、entitlement が必須。

```
packaging/viewport-break.entitlements
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.automation.apple-events</key>
  <true/>
</dict>
</plist>
```

先に ad-hoc 署名のまま `--options runtime` + この entitlements を付けてビルドし、
375px が通ることを確認してから証明書に進む（entitlement 漏れの切り分けを分離するため）。

### 4.2 証明書の取得

1. Apple Developer Program に加入（個人）
2. `Developer ID Application` 証明書を作成し、この Mac のキーチェーンへ入れる
   （案 C を将来使う可能性を残すなら `Developer ID Installer` も同時に作っておく）
3. 確認: `security find-identity -v -p codesigning`
   → 現在は `0 valid identities found`。ここに `Developer ID Application: <名義> (<TeamID>)` が出れば成功
4. 公証用の認証情報を保管（App Store Connect API キー推奨。app-specific password でも可）
   ```
   xcrun notarytool store-credentials "viewport-break-notary" \
     --key <AuthKey_XXXX.p8 の絶対パス> --key-id <KEY_ID> --issuer <ISSUER_UUID>
   ```
   `xcrun notarytool` は本機に存在（`/Library/Developer/CommandLineTools/usr/bin/notarytool` 1.1.0）

### 4.3 `packaging/build_dmg.sh` の改修

対象: `packaging/build_dmg.sh`

| 現行 | 変更後 |
| --- | --- |
| 135 行目 `codesign --force --deep --sign - --timestamp=none "$APP"` | Developer ID 署名 + Hardened Runtime + entitlements + セキュアタイムスタンプ |
| （なし） | .app の公証 → staple → その .app を DMG へ |
| 163 行目 `hdiutil create ...` | DMG 作成後に DMG も公証 → staple |

署名は `--deep` を使わない（非推奨で、entitlements が内側に伝播しない）。
本バンドルは実行ファイル 1 本なので `.app` を 1 回署名すれば足りる。

```sh
SIGN_ID="${SIGN_ID:-Developer ID Application: <名義> (<TeamID>)}"
NOTARY_PROFILE="${NOTARY_PROFILE:-viewport-break-notary}"
ENTITLEMENTS="packaging/viewport-break.entitlements"

# 1) 署名（Hardened Runtime + Apple Events entitlement + セキュアタイムスタンプ）
codesign --force --sign "$SIGN_ID" \
         --options runtime --timestamp \
         --entitlements "$ENTITLEMENTS" \
         "$APP"
codesign --verify --strict --verbose=2 "$APP"

# 2) .app を公証（zip に固めて提出）
ditto -c -k --keepParent "$APP" "$BUILD_DIR/notarize-app.zip"
xcrun notarytool submit "$BUILD_DIR/notarize-app.zip" \
      --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$APP"          # ticket を .app に埋める

# 3) staple 済み .app を STAGE へ入れ、既存のパーミッション正規化はそのまま実行
#    （155-158 行目の chmod 群は残す。cp -R でモードが落ちる問題への対策）

# 4) DMG を作る（既存 163 行目のまま）

# 5) DMG 自体も公証して staple（DMG を配るのでこちらが本命）
xcrun notarytool submit "$DMG" --keychain-profile "$NOTARY_PROFILE" --wait
xcrun stapler staple "$DMG"
```

`--wait` を付けても失敗することはある。失敗時は必ずログを見る:
```
xcrun notarytool log <submission-id> --keychain-profile viewport-break-notary
```

**staple を .app と DMG の両方に打つ理由**: DMG に staple しておけば購入者が
**オフラインでも**検証が通る。.app 側にも打っておくと、DMG から取り出した後も自己完結する。

### 4.4 `はじめにお読みください.txt` の改訂

対象: `packaging/dmg/はじめにお読みください.txt`

| 行 | 対応 |
| --- | --- |
| 52 行目 `xattr -dr com.apple.quarantine ~/Downloads/...` を含む手順 2 | **削除**（本設計の目的そのもの） |
| 57 行目の xattr の補足 | 削除 |
| 119 行目（復旧手順の xattr） | **残す**。旧版 DMG を掴んでいる購入者の救済に要る。「旧版をお持ちの場合」と明示 |
| Gatekeeper 警告の説明（「Return を押さない」） | **残す**。公証済み版では出ないはずだが、§5 で出ないことを実測するまでは消さない |
| 拡張の読み込み手順・安全チェック警告の説明 | そのまま（軸 B は未対応） |

### 4.5 配布と記録

- `hdiutil` の出力にはタイムスタンプが入り、同一ソースでも DMG の sha256 は毎回変わる。
  **配ったファイルの sha256 を都度控える**運用は継続する。
- Dropbox の配布先は現行どおり `/viewport-break/`。差し替え時は旧版を消さず別名で残す（§6 の rollback）。

### 4.6 （第 2 段・オーナー判断後）拡張のストア限定公開

ストアが採番する ID が現行と変わった場合、**次の 4 か所を同時に更新**する。
1 か所でもズレると native messaging が拒否される。

1. `extension/manifest.json` の `key`
2. `extension/EXTENSION_ID`
3. `packaging/helper/Sources/main.swift` の `EXT_ID`（31 行目）
4. `packaging/dmg/はじめにお読みください.txt` の案内文中の ID

`packaging/build_dmg.sh` は 1 と 3 の一致をビルド前に検証して食い違いを止める。
併せて `extension/manifest.json` の `name` を製品名 `VIEWPORT BREAK` に
揃えるのはこのタイミングが適切。
→ 2026-08-31 に対応済み（`name` / `default_title` を `VIEWPORT BREAK` へ統一）。
`HOST_NAME = com.nanago.viewport_deck` は native messaging の登録キーなので**改名していない**。

---

## 5. 検証手順

各項目は **command / cwd / 対象 artifact の sha256 / exit code / timestamp / 生出力の保存先**を
記録する。保存先は `docs/evidence/notarized-dmg-<日付>/`。

### 5.1 ビルド成果物の静的検証（機械判定）

| # | 確認 | コマンド | 期待 |
| --- | --- | --- | --- |
| 1 | 署名の中身 | `codesign -dv --verbose=4 "/Applications/VIEWPORT BREAK.app"` | `Authority=Developer ID Application: ...` / `TeamIdentifier=<TeamID>`（`not set` でない） / `flags=0x10000(runtime)` |
| 2 | entitlement | `codesign -d --entitlements - "/Applications/VIEWPORT BREAK.app"` | `com.apple.security.automation.apple-events` = true |
| 3 | Gatekeeper 評価 | `spctl -a -vvv -t exec "/Applications/VIEWPORT BREAK.app"` | **`accepted` / `source=Notarized Developer ID`**（現在は rc=3 `rejected`） |
| 4 | staple | `xcrun stapler validate "/Applications/VIEWPORT BREAK.app"` と DMG 側 | `The validate action worked!` |
| 5 | 公証ログ | `xcrun notarytool log <id> --keychain-profile viewport-break-notary` | `status: Accepted` / `issues: null` |
| 6 | パーミッション | `ls -la` でマウント済み DMG 直下 | 755/644（0700 が残っていない。第一版の不具合） |
| 7 | ユニバーサル | `lipo -archs "/Applications/VIEWPORT BREAK.app/Contents/MacOS/viewport-break"` | `x86_64 arm64` |

### 5.2 ダウンロード再現（既存の実測資産を再利用）

`docs/evidence/dmg-installer-2026-08-30/run_download_gatekeeper.py`
を新 DMG に対して実行し、**quarantine が付いた本物の状態**から確認する。

| # | 確認 | 期待 |
| --- | --- | --- |
| 8 | DMG の quarantine | 付いている（`0281;...;Chrome;<UUID>`）。**外さない** |
| 9 | マウント → `/Applications` へドラッグ相当のコピー | rc=0 |
| 10 | **Gatekeeper ダイアログ** | **出ない**。`CoreServicesUIAgent` の onscreen window = 0 |
| 11 | 起動状態 | `lsappinfo` が `flavor=3 Version="1.0.0" Arch=ARM64`（`Arch=!!none` でない＝§1.1 (4) が起きていない） |
| 12 | translocation | されない（`--doctor` の `translocated: false`、`/Applications/...` から直接実行） |
| 13 | 画面のアラート | 「VIEWPORT BREAK の準備ができました」 |

**10 が本設計の合否そのもの。** これが false なら公証が効いていない。

### 5.3 オフライン検証（stapling が効いているか）

| # | 確認 | 手順 | 期待 |
| --- | --- | --- | --- |
| 14 | ネット遮断での初回起動 | Wi-Fi / Ethernet を切った状態で 5.2 を通す | ダイアログなしで起動する（ticket がローカルに埋まっている証明） |

staple を忘れると、オンラインでは通るのにオフラインで止まる。**この項目を省略しない。**

### 5.4 機能の通し（既存スクリプト）

`docs/evidence/dmg-installer-2026-08-30/run_install_e2e.py`

| # | 確認 | 期待 |
| --- | --- | --- |
| 15 | native messaging manifest | 存在するブラウザのプロファイルに設置、`path_exists: true` |
| 16 | 拡張の展開 | `~/Library/Application Support/VIEWPORT BREAK/extension` に 8 エントリ |
| 17 | 拡張 → ヘルパー ping | `{"impl":"swift","host_version":"2.0.0","ok":true}` |
| 18 | **オートメーション許可ダイアログ** | 主体が **"VIEWPORT BREAK.app"** と表示される（"python3" でない）。Hardened Runtime で壊れていないことの確認でもある |
| 19 | **375 を押す** | `reached_375: true`（AppleScript 読み戻しと `chrome.windows` API の両方で 375） |
| 20 | `--doctor` | `automation_permission: true` / `extension_installed: true` / `install_blocked: false` |

**18 と 19 は entitlement 漏れを検出する唯一の経路。** 静的検証だけで済ませない。

### 5.5 アップデート耐性（Developer ID を入れる主目的の 1 つ）

| # | 確認 | 手順 | 期待 |
| --- | --- | --- | --- |
| 21 | 再ビルド後の TCC 維持 | 同一証明書で再ビルド → 上書きインストール → 375 を押す | **オートメーション許可を再度求められない**（ad-hoc では毎回求められた） |

### 5.6 実機でしか確認できない項目（オーナー環境が要る）

| # | 項目 | 理由 |
| --- | --- | --- |
| 22 | Intel Mac での起動 | 本機は arm64 のみ。`lipo` で x86_64 が入っていることは確認できるが実行は不可 |
| 23 | Command Line Tools 無しの Mac | 本機には CLT が入っている。Swift バイナリは依存なしのはずだが未確認 |
| 24 | Finder での実ドラッグ操作 | AppleScript の `duplicate` に Finder の TCC 権限が要る。付与しない方針のため `ditto` で代替してきた |
| 25 | オーナーの MacBook での通し | 第一版が詰まった実機。ここで 10 が false なら設計の見直し |

---

## 6. 残リスクと rollback

### 6.1 実装上のリスク

| リスク | 影響 | 対策 |
| --- | --- | --- |
| **Apple Events entitlement の付け忘れ** | Hardened Runtime 下で `NSAppleScript` が塞がれ、**375px が動かなくなる**。公証は通るので静的検証では気付けない | §5.4 の #18/#19 を必須にする。§4.1 で ad-hoc のまま先に切り分ける |
| **staple 忘れ** | オンラインでは通り、オフラインの購入者だけ詰まる。再現しにくい | §5.3 の #14 を必須にする |
| **公証のリジェクト** | 配布物が出せない | `notarytool log` を必ず読む。よくある原因は Hardened Runtime 未有効・セキュアタイムスタンプ欠落・内包バイナリの署名漏れ |
| **加入審査の遅延** | 個人 1〜2 営業日、法人は D-U-N-S 取得で 2〜4 週間。着手が止まる | 個人アカウントで加入する。法人名義が要るなら日程を先に確保 |
| `--deep` の誤用 | entitlements が内側に伝播せず、原因が分かりにくい失敗になる | `--deep` を使わない（§4.3） |

### 6.2 移行時のリスク（既存購入者）

| リスク | 内容 |
| --- | --- |
| **署名 identity の変更で TCC 許可が 1 度だけリセットされる** | ad-hoc → Developer ID で Designated Requirement が変わるため、既存購入者は**移行時に 1 回だけ**オートメーション許可を押し直す。以後は安定する（§5.5）。案内文に 1 行入れる |
| 旧版 DMG を掴んだままの購入者 | 旧版の復旧手順（`pkill` + `xattr`）を `はじめにお読みください.txt` に残す（§4.4） |

### 6.3 運用上の残リスク

| リスク | 内容 |
| --- | --- |
| **年 99 USD の継続費用** | 更新を止めると証明書が失効する。**既に公証済みの配布物は ticket があるため動き続ける**が、新しいビルドは出せなくなる。証明書が Apple に **revoke** された場合は既存の配布物も起動しなくなる（失効と revoke は別物） |
| **軸 B が未解決のまま残る** | 拡張の読み込み操作・デベロッパーモード・安全チェック警告（「Chrome では、この拡張機能の提供元を確認できません」）は案 A では消えない。**有料製品として「壊れている / 騙された」と受け取られやすい**ため、販売ページに先回りして書く |
| Chrome 側の将来変更 | 未パッケージ拡張やデベロッパーモードの扱いが Chrome の更新で変わりうる。制御外。ストア限定公開（§2.5）はこのリスクへの保険でもある |
| 複数 Chrome インスタンス | `tell application "Google Chrome"` は実行中のどれか 1 つに解決される。意図しないウィンドウが縮む可能性（既知・本設計では未対応） |
| 自動アップデート機構が無い | DMG を配り直すしかない。ストア限定公開にすれば拡張側だけは自動更新になる |
| ウィンドウ幅は Chrome 再起動で 500px に戻る | 既存の制約。`docs/WINDOW_FLOOR_2026-08-30.md` |
| **本設計の実効 effort が推奨より低い** | 推奨 max に対し実効 high（context safety cap）。§5 の検証設計は実行されていないため、実施時に項目の抜けが見つかる可能性がある |

### 6.4 rollback

**戻す単位を 3 つに分ける。どれも独立して戻せる。**

| # | 対象 | 戻し方 | 条件 |
| --- | --- | --- | --- |
| 1 | **ビルドスクリプト** | `packaging/build_dmg.sh` の変更を git で戻す（`git revert <commit>`）。ad-hoc 署名に戻り、従来どおり DMG が焼ける | 公証が通らない / entitlement 問題が解けない |
| 2 | **配布物** | 現行の公証なし DMG（sha256 `c2d1411f17abb9991e43f6c594ac86d579dc03062aaa272e40ded01239480114`）を Dropbox から**消さずに残しておき**、URL を差し戻す | 新 DMG に想定外の不具合 |
| 3 | **購入者向け手順** | `はじめにお読みください.txt` の xattr 手順を復活（§4.4 で 119 行目を残してあるので全消ししない） | 上記いずれか |

**rollback の前提条件**: 新旧の DMG を同時に保持し、**どちらの sha256 も記録しておく**こと。
`hdiutil` のタイムスタンプで sha256 は毎回変わるため、後から再現できない。
差し替え前に旧版を別名で退避する。

**rollback しても失われないもの**: Developer ID の取得そのもの（年費は残るが、
案 C・案 D へ進むときに再利用できる）。

### 6.5 判断が要る分岐（オーナー）

| 分岐 | 選択肢 | 本設計の推奨 |
| --- | --- | --- |
| **Apple Developer Program に加入するか** | する / しない（xattr 手順を維持） | **する**。しない場合、軸 A は原理的に解決しない |
| ストア限定公開へ進むか | 進む（軸 B が消える・ストア非経由方針の変更） / 進まない（警告を説明で受ける） | 案 A の完了後に**別途判断**。案 A の実装はこの選択と独立 |
| 名義 | 個人 / 法人 | **個人**（1〜2 営業日）。法人は D-U-N-S で 2〜4 週間 |

---

## 7. 本設計の作成時に実測した事実（2026-08-30）

以下は本機で実行して確認した。これ以外の記述は §2.2 の費用・日数を含め**設計上の見積り**であり、実績ではない。

| # | 確認したこと | コマンド | 結果 |
| --- | --- | --- | --- |
| 1 | 署名 ID が 1 件も無い | `security find-identity -v -p codesigning` | `0 valid identities found` → 案 A は**現時点で実行不能** |
| 2 | 公証ツールは揃っている | `xcrun --find notarytool` / `xcrun notarytool --version` | `/Library/Developer/CommandLineTools/usr/bin/notarytool` / `1.1.0 (39)` |
| 3 | staple ツールがある | `xcrun --find stapler` | `/Library/Developer/CommandLineTools/usr/bin/stapler` |
| 4 | pkg ツールがある | `which pkgbuild productbuild` | `/usr/bin/pkgbuild` / `/usr/bin/productbuild` |
| 5 | MDM 未登録 | `/usr/bin/profiles status -type enrollment` | `Enrolled via DEP: No` / `MDM enrollment: No` |
| 6 | 管理環境設定が無い | `ls "/Library/Managed Preferences/"` | `No such file or directory` → 案 B の実機検証は不可 |
| 7 | Chrome 外部拡張ディレクトリが無い | `ls "/Library/Application Support/Google/Chrome/External Extensions/"` | `No such file or directory` |
| 8 | **全ユーザー共通の NM ホスト経路は実在する** | `ls -la "/Library/Google/Chrome/NativeMessagingHosts/"` | `root:wheel`。Apple の `com.apple.passwordmanager.json` が置かれている → 案 C の根拠 |
| 9 | **ストア外 CRX の強制インストールが可能** | Chrome 151 同梱の `com.google.Chrome.manifest` の `ExtensionInstallForcelist` 説明 | 各要素は `<拡張 ID>;<update URL>`、scheme は **http / https / file** |
| 10 | 拡張関連ポリシーの存在 | 同上 | `ExtensionSettings` / `ExtensionDeveloperModeSettings` / `ExtensionUnpublishedAvailability` / `NativeMessagingAllowlist` / `NativeMessagingBlocklist` / `NativeMessagingUserLevelHosts` |
| 11 | 環境 | `sw_vers` / `Google Chrome --version` | macOS 26.3.1 (25D771280a) / Google Chrome 151.0.7922.174 |
| 12 | 改修対象の位置 | `packaging/build_dmg.sh` | 135 行目 `codesign --force --deep --sign -` / 163 行目 `hdiutil create` |
| 13 | 現行の xattr 手順の位置 | `packaging/dmg/はじめにお読みください.txt` | 52 / 57 / 119 行目 |

## 8. 未検証（推測を書かないための明示）

1. **Developer ID 署名・公証・stapling の一切**（§7-1 のとおり証明書が無く実行できない）。
   §5 の期待値は Apple の仕様と既存実測からの設計であって、通した結果ではない。
2. **Chrome ポリシー適用の実機確認**（§7-5, §7-6）。ポリシーキーの存在は確認済みだが、
   実際に強制インストールが成立するかは未確認。構成プロファイル導入には
   オーナーの管理者パスワードと GUI 操作が要るため、本作業では実施しなかった。
3. **pkg の作成・実行**。ツールの存在のみ確認。
4. **Chrome ウェブストアの審査所要日数とリジェクト条件**（§2.5）。一般的な目安であり実績ではない。
5. **Apple Developer Program の日本円価格と加入所要日数**。99 USD / 年という公表価格に基づく見積り。
6. **Hardened Runtime 下で `NSAppleScript` が entitlement のみで通ること。** 仕様上はそうだが、
   本製品の実装で通したことはない（§6.1 の最重要リスク）。
7. §5.6 の #22〜#25（Intel Mac / CLT 無し / Finder 実ドラッグ / オーナー実機）。

---

## 付録: 関連ドキュメント

| パス | 内容 |
| --- | --- |
| `docs/DMG_DISTRIBUTION_2026-08-30.md` | 本設計の前提。DMG 第一版の実測と「応答しないため開けません」の原因調査 |
| `docs/WINDOW_FLOOR_2026-08-30.md` | Chrome の 500px 下限と再起動で戻る挙動 |
| `docs/evidence/dmg-installer-2026-08-30/` | §5.2 / §5.4 で再利用する実測スクリプトと生ログ |
| `docs/evidence/app-hang-2026-08-30/` | §1.1 (4)(5) の証跡（`lsappinfo` / `sample` / ダイアログ画像） |
