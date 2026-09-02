# VIEWPORT DECK — 最小 PoC 実測結果（2026-08-30）

- 対象: `MAC_MINI_HANDOFF_2026-08-30.md` §6 Step 0〜3 / `HANDOFF_REPLY_2026-08-30.md` §7 の未確認 7 項目（U-1〜U-7）
- 実施根拠: オーナー承認（「Chrome を起動して最小 PoC を実施してよい。あわせて幅制御の代替手段をリサーチしてよい」）
- 実施日時: 2026-08-30 09:40〜09:55 JST
- **本文書に「確認済み」と書いた項目は、すべてこの機で実際に Chrome を起動して実測した結果である。** 実測していない項目は §6 に未検証として分離した。

## 実施環境

| 項目 | 値 |
|---|---|
| Chrome | 151.0.7922.174（`/Applications/Google Chrome.app`） |
| CDP プロトコル | 1.3 / 57 ドメイン（`/json/protocol` を取得して解析） |
| 専用プロファイル | `/Users/macmini/Library/Caches/viewport-deck-poc/chrome-profile`（新規作成 → **PoC 後に削除済み**） |
| デバッグポート | `127.0.0.1:9333`（PoC 中のみ。終了により解放） |
| CDP クライアント | Python + `websocket-client`（既存）。**`npm i` もネットワークも不要だった** |
| ディスプレイ | 3840×2160 物理 / 論理 1920×1080、`devicePixelRatio = 2` |
| 検証形態 | EVALUATION_MODE = hybrid（数値は機械判定、表示の見えかたはスクリーンショット実測） |

守った停止線: Dropbox 正本は未変更 / 運用中プロファイル（`Default`・`Profile 1`・`/tmp/chrome-cdp-profile`）に未接触 / 拡張インストールなし / Native Messaging 登録なし / AX 権限要求なし（DevTools UI 操作は CDP `Input` で代替）/ 外部送信なし / 専用プロファイルは削除済み。

---

## 1. 結論（先に）

| # | 判定 | 内容 |
|---|---|---|
| 1 | **成功** | **DevTools を表示した状態で、外部 CDP からの幅 override は効く。** 375 / 390 / 768 / 1920 すべて `innerWidth` が指定値と ±0px 一致。方式 A の最大リスク（U-2 / U-3）は解消した |
| 2 | **成功** | `Target.openDevTools` は Chrome 151 に実在し、実際に呼べる（Experimental） |
| 3 | **成功** | 375px 指定時、ページは**画面上でも実寸 375 CSS px で 1:1 描画**される。縮小でも拡大でもない。「物理 DevTools」のコンセプトは成立する |
| 4 | **条件付き成功** | 1920 プリセットは **dock=right では 555px が切れて見えない**。**dock=bottom なら実質全幅表示できる**。D-04 は「dock=bottom を既定にする」で解ける |
| 5 | **条件付き成功** | Device Toolbar を **ON にした瞬間だけ** 外部 override が上書きされる（390 → 1600）。ただし後から外部 CDP で上書きし返せる（last-writer-wins）。**Device Toolbar は OFF 運用が正解** |
| 6 | **失敗（仕様）** | 外部 CDP で変えた幅は **DevTools の幅表示 UI に同期しない**（実 375 に対し UI は `400 × 786` のまま）。§5.4 最終項目への回答は「同期しない」 |
| 7 | **成功** | 500 DIP 下限を実測で確定。通常ウインドウ外形は 500 でクランプし、375/390 に到達できない。**ただし popup ウインドウは下限の対象外で 280px まで到達できた** |

**推奨: 方式 A（専用プロファイル + 直接 CDP、width-only override）を本命として確定してよい。** 併せて DevTools は **dock=bottom / Device Toolbar OFF** を既定とする。

---

## 2. Step 0 — protocol discovery（U-1）

`/json/protocol` を取得（1,605,774 bytes、sha256 は §7）。

| メソッド | 実在 | Experimental | 備考 |
|---|---|---|---|
| `Target.openDevTools` | **あり** | **true** | 引数 `targetId`, `panelId` |
| `Emulation.setDeviceMetricsOverride` | あり | **false（安定版）** | 引数 16 個 |
| `Emulation.clearDeviceMetricsOverride` | あり | false | |
| `Emulation.setPageScaleFactor` | あり | true | |
| `Browser.setWindowBounds` / `getWindowForTarget` | あり | true | |
| `Page.setDeviceMetricsOverride` | あり | true | 旧エイリアス |

さらに `Target.openDevTools` を**実際に発行して成功**した（戻り値に DevTools target の `targetId`）。

> 判定: **成功。** HANDOFF_REPLY 1.4 の「バイナリ文字列からの傍証」は実呼び出しで裏付けられた。ただし Experimental なので固定依存はしない方針は維持すべき。

---

## 3. Step 1 — CDP のみ（DevTools なし）

ウインドウを作業領域いっぱい（contents 幅 1920）にし、`{width:W, height:0, deviceScaleFactor:0, mobile:false}` を順次適用。

| 要求幅 | `innerWidth` | `visualViewport.width` | DPR | `innerHeight` | 一致 |
|---|---|---|---|---|---|
| 320 | **320** | 320 | 2 | 873 | ±0 |
| 360 | **360** | 360 | 2 | 873 | ±0 |
| 375 | **375** | 375 | 2 | 873 | ±0 |
| 390 | **390** | 390 | 2 | 873 | ±0 |
| 430 | **430** | 430 | 2 | 873 | ±0 |
| 768 | **768** | 768 | 2 | 873 | ±0 |
| 1280 | **1280** | 1280 | 2 | 873 | ±0 |
| 1920 | **1920** | 1920 | 2 | 873 | ±0 |

- media query も指定幅で正しく切り替わった（375 → `(min-width:375px) and (max-width:389px)`、390 → `(min-width:390px)`、768 → `(min-width:768px)`、1920 → `(min-width:1280px)`）。
- `clearDeviceMetricsOverride` 後は 1920 へ完全復帰。
- `height:0` は `innerHeight` に一切介入しない（ウインドウ由来の 873 のまま）。**height 非介入は成立する。**

### 3.1 画面上の実寸（スクリーンショット実測）

375 指定時のスクリーンショットで、ページ先頭のグラデーションバー（CSS 幅 = viewport 幅 − body padding 24px）の実描画幅を測った。

- 実測 **702 device px** ÷ DPR 2 = **351 CSS px** = 375 − 24（body padding）→ **誤差 0。等倍描画。**
- レイアウトは**ウインドウ左上に寄せ**、右側の残り（約 1545 CSS px）は**白い余白**になる。縮小表示でもレターボックスでもない。

> 判定: **成功。** 「指定した幅が、画面上でも実寸でその幅」という G1 の核は成立する。ただし右側の広い余白をどう見せるか（枠・センタリング・背景）は UX 設計項目として残る。

---

## 4. Step 2 — DevTools 併用（U-2 / U-3 / U-4 / U-6）

### 4.1 dock=right / Device Toolbar OFF ← **本命構成**

| 状態 | `innerWidth` |
|---|---|
| DevTools を開く前 | 1920 |
| DevTools を right dock で表示（override なし） | **1365**（DevTools が 555px を占有） |

その状態で外部 CDP から override:

| 要求幅 | `innerWidth` | 一致 |
|---|---|---|
| 375 | **375** | ±0 |
| 390 | **390** | ±0 |
| 768 | **768** | ±0 |
| 1920 | **1920** | ±0 |

スクリーンショットで、DevTools の Styles パネルに `@media (min-width:375px) and (max-width:389px)` が**マッチ表示**されていることも確認した。DevTools frontend も同じ幅で評価している。

> **U-2 = 成功 / U-3 = 成功。** DevTools 表示中も外部 CDP の override は有効で、frontend に潰されない。**これが方式 A の成否を分ける最大の分岐点だったが、通過した。**

### 4.2 1920 の表示挙動（U-6 / D-04）

dock=right で 1920 を適用したときの実測:

- `innerWidth` = 1920、`scrollWidth` = 1920、`clientWidth` = 1920（レイアウトは正しく 1920）
- **画面上に見えているのは 1354 CSS px 分だけ**（バー実測 2708 device px ÷ 2）
- **横スクロールバーは出ない。残り約 555 CSS px は不可視かつ到達不能。**

つまり **縮小表示ではなく「無警告のクリッピング」** である。HANDOFF_REPLY 2.3 の「等倍にはならない」は正しいが、機序は縮小ではなく切り落としで、より問題が大きい。

**dock=bottom で再測定したところ解決した:**

| 構成 | contents 幅 | `innerHeight` | 1920 適用時 |
|---|---|---|---|
| dock=right | 1365 | 853 | 555px 不可視 |
| **dock=bottom** | **1900** | 853 → **553** | **切れるのは約 20 CSS px のみ。実質全幅表示** |

> 判定: **条件付き成功。** D-04 は「スコープ外し」も「外部モニタ必須」も不要で、**dock=bottom を既定にする**ことで現構成のまま解ける。代償は縦が 853 → 553 に減ること。

### 4.3 Device Toolbar ON（U-3 の追試）

DevTools UI 操作は AX 権限を使わず CDP `Input.dispatchKeyEvent`（Cmd+Shift+M）で行った。

| 操作 | `innerWidth` | 解釈 |
|---|---|---|
| 外部 override で 390 適用済み | 390 | — |
| **Device Toolbar を ON にした直後** | **1600** | **frontend が override を上書きした** |
| その後、外部 CDP で 375 を再適用 | **375** | 外部側が勝つ |
| その後、外部 CDP で 768 を再適用 | **768** | 外部側が勝つ |

- 描画は Device Toolbar ON でも **702 device px = 351 CSS px で 1:1 のまま**（キャンバスが中央寄せ + 灰色の余白になるだけ）。
- **DevTools の寸法表示は `400 × 786` のまま**で、実際の 375 と一致しなかった。

> 判定: **条件付き成功。** 競合は「常時上書き」ではなく **Device Toolbar を操作した瞬間だけの単発上書き**で、last-writer-wins。アプリ側はいつでも取り返せる。ただし競合ライターを増やす意味がないので、**Device Toolbar は OFF で運用するのが正解**。
>
> **§5.4 最終項目「外部 CDP で変更した幅が DevTools の幅入力 UI にも同期表示されるか」への回答は「同期しない」。** UX として許容できるかはオーナー判断が要る（§8-2）。Device Toolbar OFF 運用ならそもそも寸法 UI が出ないため、この不一致は表面化しない。

### 4.4 状態の永続性（U-4）

専用プロファイルで DevTools を開き Device Toolbar を ON にしてから Chrome を正常終了させ、`Default/Preferences` を読んだ。

```
devtools.preferences.currentDockState            = "right" → "bottom"（変更が保存された）
devtools.preferences.emulation.show-device-mode  = true    （ON 状態が保存された）
```

- **Device Toolbar の ON 状態と dock 位置はプロファイルに永続化され、再起動後も読み込まれる。**
- ただし **DevTools 自体は再起動時に自動では開かない**（再起動直後の target 一覧に `devtools://` は無し）。開くのは毎回アプリ側の責務。

> 判定: **成功。** HANDOFF_REPLY 1.5 が「専用プロファイルを作らないと判定不能」とした項目は、作って実測したことで確定した。dock=bottom を既定にする設定も、プロファイルに書いておけば再起動をまたいで維持できる。

---

## 5. Step 3 — 復帰性・副作用

### 5.1 復帰性（全 8 ケース通過）

| ケース | 期待 | 実測 | 判定 |
|---|---|---|---|
| override 適用直後 | 390 | 390 | OK |
| リロード後 | 390 維持 | 390 | OK |
| 同一タブ内で URL 遷移 | 390 維持 | 390 | OK |
| **別タブへ波及しないか** | 波及しない | 1920 | OK |
| 別タブを閉じた後、元タブ | 390 維持 | 390 | OK |
| DevTools 再オープン後 | 390 維持 | 390 | OK |
| DevTools 再クローズ後 | 390 維持 | 390 | OK |
| `clearDeviceMetricsOverride` 後 | 復帰 | 1920 | OK |

### 5.2 override の寿命は CDP セッションに縛られる（新規発見）

PoC 中に想定外の挙動を踏んだので、明示的に切り分けて確認した。

| 手順 | `innerWidth` |
|---|---|
| session#1 で 375 を適用 | 375 |
| 別 session#2 から観測（session#1 は接続維持） | 375 |
| **session#1 を切断** | **1900（自動で override 解除）** |

- **override は、それを設定した CDP セッションが切れると Chrome が自動で解除する。**
- 良い面: アプリがクラッシュしても Chrome 側に override が残留しない **fail-safe** が最初から備わっている。D-21（切断時の復帰ポリシー）の実装負担が下がる。
- 注意面: 常駐アプリは **CDP 接続を張りっぱなしにする必要がある**。「値を設定して切断」という実装はできない。

### 5.3 副作用

- 既存 `Default` / `Profile 1` / `/tmp/chrome-cdp-profile` には一切接続していない（`/tmp/chrome-cdp-profile` はそもそも現存しなかった）。
- ポート 9333 は Chrome 終了で解放済み。
- 専用プロファイル（155MB まで肥大）は削除済み。

---

## 6. U-5 — パラメータ組合せ（width=390 固定）

| 組合せ | `innerWidth` | `innerHeight` | DPR | 判定 |
|---|---|---|---|---|
| `height=0, dsf=0, mobile=false` | **390** | 873（非介入） | 2（実機のまま） | **推奨。G1 の既定にする** |
| `height=0, dsf=1, mobile=false` | 390 | 873 | 1 | DPR を強制上書きできる |
| `height=0, dsf=3, mobile=false` | 390 | 873 | 3 | 同上 |
| `height=844, dsf=0, mobile=false` | 390 | 844 | 2 | height 指定は効く（G2 用） |
| **`height=0, dsf=0, mobile=TRUE`** | **1560** | 3376 | 2 | **幅指定が壊れる** |

`mobile=true` にすると、指定 390 に対し `innerWidth` が **1560** になった。検証ページに `<meta name="viewport">` が無いため、モバイル既定のレイアウトビューポートが適用されたと解される。

> 判定: **成功（結論は「`mobile=false` 必須」）。** 引き継ぎ文書が G1 を `mobile=false` と設計していたのは正しい。`mobile=true` は viewport meta の有無でページごとに挙動が変わるため、G1 では使えない。G2（Full Device Emulation）で使う際は、この差を仕様として明記する必要がある。

---

## 7. U-7 — 500 DIP 下限の実測

### 7.1 DevTools なし（clean）

| 要求外形 | 実外形 | `innerWidth` | |
|---|---|---|---|
| 800 | 800 | 800 | |
| 600 | 600 | 600 | |
| **500** | **500** | **500** | ちょうど下限 |
| 450 | **500** | 500 | クランプ |
| 390 | **500** | 500 | クランプ |
| 375 | **500** | 500 | クランプ |
| 320 | **500** | 500 | クランプ |

> 判定: **成功（＝「375/390 に到達できない」ことを実測で確定）。** 下限はソースの `kMainBrowserContentsMinimumWidth = 500` と完全に一致した。macOS では外形と `innerWidth` が一致する（左右のウインドウ装飾が 0px）。**C-solo / C+obs / D は 375 / 390 に到達できない。** HANDOFF_REPLY 2.1 の結論を実機で裏付けた。

### 7.2 補足: DevTools を right dock すると contents は 500 を割る

外形 700 / DevTools right dock の状態で `innerWidth` = **150** だった。500 DIP 制約は「ウインドウの contents 領域全体（docked DevTools を含む）」に掛かっており、ページの表示領域そのものを 500 以上に保証するものではない。

---

## 8. Part B — 幅制御の代替手段の比較

「実幅か擬似か」= ページが認識する CSS viewport が本当に変わるか。「実寸表示」= 画面上で 1 CSS px が等倍で描かれるか。

| # | 手段 | 実幅/擬似 | 500 DIP 回避 | 実寸表示 | 常時運用 | 実測 | 評価 |
|---|---|---|---|---|---|---|---|
| **1** | **CDP `Emulation.setDeviceMetricsOverride`（方式 A）** | **実幅** | **回避する** | **等倍** | **可**（接続維持が必要） | **本 PoC で全項目実測** | **本命** |
| 2 | CDP `Emulation` の `scale` パラメータ | 実幅（表示だけ縮小） | 回避する | **等倍でない** | 可 | 1920 / scale=0.5 → `innerWidth` は 1920 のまま、画面上は 948 CSS px | dock=right で 1920 を全部見せたい場合の退避策。等倍が崩れるので G1 既定にはしない |
| 3 | `Browser.setWindowBounds`（CDP） | 実幅（外形） | **できない（500 クランプ）** | 等倍 | 可 | §7.1 で実測 | ウインドウ配置の補助にのみ使う |
| 4 | **popup ウインドウ**（`window.open` + features） | **実幅（外形）** | **回避する** | **等倍** | 可 | **500/420/375/320/280 すべて要求どおり ±0 で到達** | **技術的には成立する。**ただしタブバー・アドレスバーが消えるためオーナー判断で不採用済み |
| 5 | `window.resizeTo`（ページ JS） | 外形 | — | — | 不可 | 通常タブで実行 → `innerWidth` は 1900 のまま変化せず | **無効。** スクリプトが開いたウインドウ以外は拒否される |
| 6 | `chrome.debugger`（拡張、方式 B） | 実幅 | 回避する | 等倍 | **不可** | 未実測（公式仕様で判断） | 対象タブで DevTools を開くと `onDetach` する。今回の UX と両立しない |
| 7 | `chrome.windows.update`（拡張、方式 D） | 外形 | できない | 等倍 | 可 | 未実測（#3 と同じ Chrome 制約） | 参考測定に格下げ |
| 8 | AppleScript / System Events | 外形 | できない | 等倍 | 可 | 未実測 | Chrome 本体の最小サイズ制約は解除できない。AX 権限も要る。採る理由がない |
| 9 | `--auto-open-devtools-for-tabs` | — | — | — | — | 未実測 | 起動時スイッチのみ。`Target.openDevTools` が使えたのでフォールバック不要 |
| 10 | ヘッドレス Chrome | 実幅 | 回避する | 画面に出ない | — | — | 「見ながら制作する」目的に反する |
| 11 | Chromium フォーク | 実幅 | 回避する | 等倍 | 可 | — | 更新追従・署名・保守が個人プロジェクトに見合わない（不採用済み） |
| 12 | 別ブラウザ（Safari / Firefox） | 実幅 | — | 等倍 | — | — | CDP 非対応。Chrome 前提の制作ワークフローから外れる |

### 8.1 推奨（1 案）

**方式 A を本命として確定する。** 具体構成:

```
Chrome 起動: --user-data-dir=<専用> --remote-debugging-port=<port>
DevTools   : Target.openDevTools で表示 / dock = bottom / Device Toolbar = OFF
幅制御     : Emulation.setDeviceMetricsOverride
             { width: W, height: 0, deviceScaleFactor: 0, mobile: false }
接続       : 常駐アプリが CDP セッションを張りっぱなしにする（切断＝自動復帰）
```

理由:

1. **375 / 390 を含む全プリセットで ±0px を実測した。** 500 DIP の影響を受けない唯一の実幅方式（popup を除く）。
2. **DevTools 表示中も override が生きることを実測した。** §5.4 の最大リスクが消えた。
3. **画面上も等倍描画される。** 「物理 DevTools」のコンセプトを壊さない。
4. 切断時の自動復帰が Chrome 側の仕様として最初から備わっている。
5. `Emulation.setDeviceMetricsOverride` は **Experimental ではない**ため、Chrome 更新への耐性が比較的高い（`Target.openDevTools` だけが Experimental で、ここは起動フラグのフォールバックがある）。

**dock=bottom を既定にすること**を併せて推奨する。dock=right では 1920 プリセットで 555 CSS px が無警告で切れる。

---

## 9. 未検証のまま残る項目

| # | 項目 | なぜ未検証か |
|---|---|---|
| N-1 | レイテンシ（p50 / p95）、100 試行の失敗率 | 既存 PoC 計画の Step 4。今回の承認範囲外。**「1px ずつ追い込む」追従感は未評価** |
| N-2 | ディスプレイ 30Hz が UX 評価に与える影響 | 表示更新の追従感は人間評価が要る。今回は数値検証のみ |
| N-3 | 実サイトでの挙動 | 検証は自作の `probe.html`（`viewport` meta なし）で行った。**`<meta name="viewport">` を持つ実サイトでの `mobile` 挙動は未確認** |
| N-4 | 方式 B / C-solo / C+obs / D の実測比較 | 今回は方式 A の成立性判定に絞った |
| N-5 | detached（別ウインドウ）dock での挙動 | right / bottom のみ実測した |
| N-6 | 長時間の常駐運用での安定性 | 単発の PoC。連続稼働は未検証 |
| N-7 | popup 方式の実運用適性 | 幅の到達性のみ実測。タブバー欠如以外の副作用は未確認 |

---

## 10. オーナー判断を要する項目

1. **Device Toolbar OFF 運用でよいか。** OFF なら幅表示 UI の不一致（§4.3）は表面化しない。ON にしたい理由があるなら、UI が実値とズレることを許容するか判断が要る。
2. **dock=bottom を既定にしてよいか。** 1920 の全幅表示と引き換えに、縦が 853 → 553 CSS px に減る。
3. **1920 プリセットの扱い（D-04）。** dock=bottom で解けるため「スコープから外す」必要はなくなった。dock=right を選ぶ場合のみ、§8 の `scale` 退避策か外部モニタが要る。
4. **正本文書の改訂。** `HANDOFF_REPLY_2026-08-30.md` §3 の改訂案は、本 PoC の結果を反映して更新すべき項目がある（特に C-6「A の確定条件」は**通過したので確定に書き換えられる**、C-5「1920 は等倍表示不可能」は**dock=bottom なら可能に訂正**）。Dropbox 正本は今回も未変更。

---

## 11. 証拠（CLAWD_EVIDENCE）

生データ保存先: `/private/tmp/claude-501/-Users-macmini-Projects/d232197a-ee85-43ed-a162-d7249851ddae/scratchpad/evidence/`
（セッション用スクラッチパッド。恒久保存が要る場合は別途移設が必要）

| ファイル | sha256 | 内容 |
|---|---|---|
| `protocol-151.json` | `c61c953ca9e11d498943ded43fd3d5b1870e0107413dec4e84a4e7cdebc61458` | Step 0: `/json/protocol` 全文 |
| `step1-nodevtools.json` | `9403fd09ef7495cbb167d909d45f0fdda3a4f3561293886823da75fb985fb87b` | Step 1: 8 幅の観測値 |
| `step2-devtools.json` | `e534002772225b16ae56c71ecbba92dd639e2a52a3a1d9ba326ecf351809794e` | Step 2: DevTools 併用 |
| `step2b-devicetoolbar.json` | `c8a812e2999733be1f418330c97609bf8095ac073f7e52596b8d350654fefd22` | Device Toolbar ON の競合 |
| `step2c-bottomdock.json` | `475acc161225d5095a484269fcf2d109177c56915be52fa36e0d4c10fb95b882` | dock=bottom / 1920 |
| `step3.json` | `fe143db3685290af17aa1e0966e525b749d4a171549a8446bf258f89a5bdafb7` | U-7 clean + 復帰性 8 ケース |
| `u5-u7.json` | `504f6d454aa9111e5868b519f083de838142949aea08dd2b394d86410c8ffb2c` | U-5 組合せ + U-7 |
| `detach.json` | `f366dcb0a57d6ff23cd60f9adeeb74531267d62741514353bc7b21ca458c3c9c` | セッション切断時の自動解除 |
| `alternatives.json` | `593111529e9d76e8bde819e644e916077b0605f9a33595d8062b7ee2a2b3b4f9` | scale / `window.resizeTo` |
| `alternatives2.json` | `b675a32c6f758ddeeff789c6b8ff00983da8c5b9cd12cbae28e67c7d97a1e3b3` | popup の外形下限 |

スクリーンショット（実寸測定に使用）: `shot-375-held.png`（Step 1 等倍）/ `shot-devtools-375.png`（DevTools 併用 375）/ `shot-devtools-1920.png`（dock=right の 1920 クリップ）/ `shot-devicetoolbar.png`（Device Toolbar ON）/ `shot-bottomdock-1920.png`（dock=bottom の 1920）。

PoC コードは専用プロファイルとともにスクラッチパッドに置き、本リポには commit していない（`poc/` は空のまま）。方式 A の実装に着手する時点で、`HANDOFF_REPLY` §4.2 のツリーとして正式に作り直すのが妥当。
