# 拡張単体（ヘルパー無し）で到達できるウィンドウ寸法の実測 — 2026-08-30

- 目的: **VIEWPORT BREAK を Chrome ウェブストアで「拡張を入れるだけでどんな環境でも動く」形に配布できるか**の判定材料を、実測で揃える
- 対象: `chrome.windows.update` / `chrome.windows.create` のみ。native messaging host・CLI・AppleScript を**一切使わない**
- 実施日時: 2026-08-30 13:41〜13:52 JST（UTC 04:41〜04:52）
- 実施機: macOS 26.3.1 (25D771280a) / Chrome **151.0.7922.174**
- ディスプレイ: 物理 3840×2160・論理 1920×1080・DPR 2 / 作業領域 `screen.availWidth×availHeight = 1920×960`（`top` の下限は 30）
- EVALUATION_MODE: **machine**（幅・高さはすべて Chrome 自身が返した数値と、ページ側 `outerWidth`/`innerWidth` の二重読み。スクリーンショットは PNG 実ピクセル数で裏を取る）

**本文書で「実測」と書いた数値は、すべてこの機で使い捨て Chrome プロファイルを起動して取得した値である。** 実測していない項目は §11 に未実測として分離してある。推測値は表に入れていない。

守った停止線: オーナーの常用 Chrome プロファイルへ未接触（別 `--user-data-dir` のみ）/ AppleScript を 1 度も実行していない（誤爆経路を最初から作っていない）/ native messaging host manifest を使い捨てプロファイルへ置いていない / スクリーンショットは計測対象ウィンドウの矩形ちょうどだけを撮影（画面全体は撮っていない）/ 外部送信なし / 使い捨てプロファイルとポート 9391〜9398 は解放済み（実行後に残プロセス 0・LISTEN 0 を確認）。

---

## 1. 結論

### 1.1 数値の結論

| 対象 | 幅の下限 | 高さの下限 | 幅の上限 | 高さの上限 |
|---|---|---|---|---|
| **通常のタブ付きウィンドウ**（`type: "normal"`） | **500 DIP** | **375 DIP** | 3840（画面幅の 2 倍・位置依存） | 960（＝作業領域の高さ） |
| **popup 型ウィンドウ**（`type: "popup"`） | **86 DIP** | **96 DIP** | 3840（同上） | 960（同上） |

すべて 1px 刻みで境界を確定した値であり、「だいたい 500」ではない（§3.2 / §4.2 / §6.2）。

### 1.2 製品としての結論

**「ヘルパー無し・タブ付きウィンドウのまま 375/390px」は成立しない。** `chrome.windows.update` は 500 DIP でクランプされる。399 も 499 も、1 も、すべて 500 になる。これは実測で確定した（§3）。

**ただし「ヘルパー無しで 375px の実ウィンドウを出す」こと自体は成立する。** `chrome.windows.create({type:'popup'})` は 500 下限の対象外で、**86px まで縮む**。しかも `permissions` を 1 つも宣言しない拡張で動く（§2.3 / §6）。失うのはタブバー・アドレスバー・ブックマークバー（タイトルバー 32 DIP だけが残る）。

したがってストア配布の判定は「可否」ではなく**どちらの製品にするか**の選択になる。

| 案 | ストア配布 | 375px 到達 | タブ/アドレスバー | 追加インストール | 権限 |
|---|---|---|---|---|---|
| **A. 現行（native host 併用）** | 不可に近い（§10.3） | する | **残る** | **必要**（host + Automation 許可） | `nativeMessaging` |
| **B. popup 型ウィンドウ方式** | **可** | **する（86px まで）** | 失う | 不要 | **ゼロ** |
| C. 拡張単体・タブ付きのまま | 可 | **しない（500 止まり）** | 残る | 不要 | ゼロ |

**案 B が「拡張を入れるだけでどんな環境でも動く」唯一の形。** ただし案 B は前回オーナーが不採用とした「ポップアップ方式」とは別物である点に注意が要る（§6.6）。案 B を採るかどうかは、DevTools が popup 型ウィンドウでどう使えるか（**未実測**・§11）に依存するため、この文書では判断を確定させずオーナー判断の材料として出す。

---

## 2. 実測方法

### 2.1 何をもって「ヘルパー無し」と言うか

寸法変更は **100% 拡張の service worker 内の `chrome.windows.update` / `chrome.windows.create`** で行った。CDP（`--remote-debugging-port`）は次の 3 つにしか使っていない。

1. 使い捨てプロファイルへ最小テスト拡張をロードする（`Extensions.loadUnpacked`）
2. 拡張のページ／service worker の関数を呼ぶ（＝ユーザーがボタンを押すのと同じ位置）
3. 結果を読む（`window.outerWidth` 等）

**CDP 自身の `Browser.setWindowBounds` は 1 度も使っていない。** 前回文書 `WINDOW_FLOOR_2026-08-30.md` の API 経路測定は CDP を拡張 API の代理として使っていたが、本文書は代理を挟まず `chrome.windows.update` そのものを叩いている。

`--load-extension` は Chrome 151 では無視される（`extension/README.md` に既記）ため、`Extensions.loadUnpacked` を使った。

### 2.2 最小テスト拡張

`docs/evidence/extonly-2026-08-30/ext/` に全文がある。manifest はこれだけ:

```json
{
  "manifest_version": 3,
  "name": "extonly-probe",
  "version": "1.0.0",
  "description": "chrome.windows.update だけでウィンドウ寸法を変える最小テスト拡張。...",
  "background": { "service_worker": "background.js", "type": "module" }
}
```

**`permissions` キーも `host_permissions` キーも存在しない。** content script も無い。`sendNativeMessage` の**呼び出し**はソースに 1 行も無い（`background.js` に識別子が 1 か所出るが、`typeof chrome.runtime?.sendNativeMessage` という存在確認だけで、§2.3 の権限測定のために置いてある）。

### 2.3 権限ゼロであることの実測

拡張の service worker 内で読んだ値（`out/sweep.json` → `api_availability`、`out2/sweep2.json` → `permissions_recheck`。2 回とも同一）:

```json
{ "hasWindowsApi": true, "hasWindowsUpdate": true,
  "hasNativeMessaging": false, "permissions": null, "hostPermissions": null }
```

- `chrome.windows.update` は**権限宣言ゼロで使える**（この後の全測定がその証拠）
- `chrome.runtime.sendNativeMessage` は **`undefined`**。`nativeMessaging` 権限が無ければ関数自体が生えない。現行 `extension/core.js` の host 経路は、権限を落とすと**コード上到達不能**になる

### 2.4 計測面

計測は 5 パスに分かれており、ページ側の値を読んだ面はパスごとに違う。どのパスの値かは各表の「出典」で辿れる。

| パス | スクリプト | ページ側を読んだ面 | 主な担当 |
|---|---|---|---|
| 1 | `run_sweep.py` | 拡張ページ（`chrome-extension://…/probe.html`） | §3.1 幅スイープ / §4.1 高さ / §5 |
| 2 | `run_sweep2.py` | 同上 | §3.2 / §4.2 の 1px 境界 / §5 上限 |
| 3 | `run_sweep3.py` | **実 HTTP ページ**（`http://127.0.0.1:9394/m.html`） | §6.1 / §6.2 popup 下限 |
| 4 | `run_sweep4.py` | 実 HTTP ページ | §6.5 / §10.4 |
| 5 | `run_shots.py` | 実 HTTP ページ | §7 実写 |

**タブ付きウィンドウの 500 クランプは、拡張ページ（パス 1・2）と実 HTTP ページ（パス 3 の `tabbed_375`、パス 5 の実写 02/03）の両方で同じ値を確認してある。** 面の違いによる差は出ていない。ページは `outerWidth / innerWidth / outerHeight / innerHeight / devicePixelRatio` を返す。

スクリーンショットは `screencapture -x -R <計測したウィンドウ矩形>`。DPR 2 なので **PNG の実ピクセル数は DIP の 2 倍**になり、これが数値の独立した裏付けになる。

---

## 3. 通常のタブ付きウィンドウ — 幅

### 3.1 依頼された N での実測

`chrome.windows.update(id, {width: N, state: 'normal'})`。起動時 900×760、位置 (620,140) 固定。

| 要求 N | `chrome.windows.get().width` | ページ `outerWidth` | ページ `innerWidth` | 実写 PNG 実ピクセル | 到達 |
|---:|---:|---:|---:|---|---|
| 1 | **500** | 500 | 500 | 1000×1520 | ✗ |
| 50 | **500** | 500 | 500 | 1000×1520 | ✗ |
| 200 | **500** | 500 | 500 | 1000×1520 | ✗ |
| 300 | **500** | 500 | 500 | 1000×1520 | ✗ |
| 400 | **500** | 500 | 500 | 1000×1520 | ✗ |
| 500 | 500 | 500 | 500 | 1000×1520 | ✓ |
| 600 | 600 | 600 | 600 | 1200×1520 | ✓ |

- **エラーにならない。** `chrome.windows.update` は resolve し、返り値の `width` が既に 500 になっている。呼び出し側から見ると「成功したのに幅が違う」。現行 `core.js` が返り値を読み直して `clamped` を立てているのは正しい設計である
- `outerWidth === innerWidth === ウィンドウ幅`。**タブ付きウィンドウに横方向のクロームは無い**ので、ウィンドウ幅がそのまま CSS viewport 幅になる
- PNG 実ピクセルが 1000 = 500 DIP × 2。表示上も本当に 500px

出典: `docs/evidence/extonly-2026-08-30/out/sweep.json` → `summary.width_sweep`

### 3.2 下限の境界（1px 刻み）

| 要求 | 実測 |
|---:|---:|
| 495 | 500 |
| 496 | 500 |
| 497 | 500 |
| 498 | 500 |
| 499 | **500** |
| 500 | **500** |
| 501 | **501** |
| 502 | 502 |
| 505 | 505 |

**下限はちょうど 500 DIP。** 499 と 501 で挙動が割れる。`browser_view_layout.h` の `kMainBrowserContentsMinimumWidth = 500`（`WINDOW_FLOOR_2026-08-30.md` §2.1 に引用済み）と一致する。

出典: `out2/sweep2.json` → `summary.width_edge`

### 3.3 最大化からの復帰でも同じ

`state:'maximized'`（1920×960）にしてから `{width:375, state:'normal'}` を要求 → **500**。最大化を経由しても抜け道にはならない。

出典: `out/sweep.json` → `summary.misc`

---

## 4. 通常のタブ付きウィンドウ — 高さ

### 4.1 依頼された N での実測

| 要求 N | 実測 `height` | ページ `outerHeight` | ページ `innerHeight` | 到達 |
|---:|---:|---:|---:|---|
| 1 | **375** | 375 | 288 | ✗ |
| 50 | **375** | 375 | 288 | ✗ |
| 100 | **375** | 375 | 288 | ✗ |
| 200 | **375** | 375 | 288 | ✗ |
| 300 | **375** | 375 | 288 | ✗ |
| 400 | 400 | 400 | 313 | ✓ |
| 600 | 600 | 600 | 513 | ✓ |

### 4.2 下限の境界（1px 刻み）

| 要求 | 実測 |
|---:|---:|
| 330 / 350 / 360 / 370 / 372 / 373 | 375 |
| 374 | **375** |
| 375 | **375** |
| 376 | **376** |
| 380 | 380 |
| 390 | 390 |

**高さの下限はちょうど 375 DIP。**

> **既存文書の訂正が要る。** `WINDOW_FLOOR_2026-08-30.md` §2.1 は Chromium のコメント（"which is why a minimum height is not specified"）を根拠に「高さの下限は意図的に設けられていない」と書いている。`kMainBrowserContentsMinimumWidth` に高さ相当の定数が無いのはそのとおりだが、**`chrome.windows.update` 経由では実際に 375 DIP でクランプされる**。起動フラグ `--window-size=375,900` で高さ 900 が通ったこと（前回実測）と矛盾はしない — 前回は下限より大きい値しか試していない。この 375 の出所（`BrowserFrame` の最小サイズか、`views` の別経路か）は**ソース未確認・未実測**。

- 縦のクローム（タブバー＋ツールバー）は **87 DIP 固定**（375−288 = 400−313 = 600−513 = 87）
- 高さ 375 のとき CSS viewport の高さは **288px** しか残らない

出典: `out/sweep.json` → `summary.height_sweep` / `out2/sweep2.json` → `summary.height_edge`

---

## 5. 画面幅を超える拡大

`chrome.windows.update` には **「bounds の 50% 以上が可視画面内にあること」** という別種の制約があり、これは**クランプではなくエラー**になる。

| 要求 | 結果 |
|---|---|
| `{left:620, top:140, width:3000}` | **失敗** `Invalid value for bounds. Bounds must be at least 50% within visible screen space.` |
| `{left:0, top:30, width:3000, height:800}` | **成功** → 3000×800（`outerWidth`/`innerWidth` とも 3000） |
| `{left:0, top:30, width:3840, height:800}` | **成功** → 3840×800 |
| `{left:0, top:30, width:3841, height:800}` | **失敗**（同じエラー） |
| `{left:0, top:30, width:5000, height:800}` | **失敗**（同じエラー） |

**画面幅 1920 に対し、左端に寄せれば 3840（＝画面幅の 2 倍）までちょうど拡げられる。** 3841 で落ちるのは 50% ルールと厳密に一致する（1920 / 3840 = 50%、1920 / 3841 < 50%）。**同じ 3000px でも `left` を指定しなければ失敗する**ので、拡大側は「幅だけ渡す」実装では通らない。位置を同時に指定する必要がある。

高さ側は挙動が違い、**エラーではなく作業領域へクランプ**される。

| 要求 | 結果 |
|---|---|
| `{left:0, top:30, height:1200}` | 成功 → **960**（＝`availHeight`） |
| `{left:0, top:30, height:2000}` | 成功 → **960** |

実写: `out/over-3000-at-0.png`（3000×960 のうち画面に映る 1920×960 分＝PNG 3840×1920）、`shots/09-popup-3000-onscreen-part.png`

出典: `out2/sweep2.json` → `summary.big` / `out/sweep.json` → `summary.over_screen`

---

## 6. popup 型ウィンドウ — 500 下限の外にある経路

`chrome.windows.create({type:'popup'})` で作ったウィンドウは `BrowserViewPopupLayoutImpl`（最小 1×1）を使うため、500 下限の対象外になる。**権限宣言ゼロのまま実測した。**

### 6.1 幅（実 HTTP ページを読み込んだ状態）

| 要求 | 実測 `width` | `outerWidth` | `innerWidth` |
|---:|---:|---:|---:|
| 1 | **86** | 86 | 86 |
| 50 | **86** | 86 | 86 |
| 80 / 84 / 85 | **86** | 86 | 86 |
| 86 | 86 | 86 | 86 |
| **87** | **87** | 87 | 87 |
| 88 / 90 / 100 / 200 / 300 | 要求どおり | 同左 | 同左 |
| **320** | **320** | 320 | 320 |
| **375** | **375** | 375 | 375 |
| **390** | **390** | 390 | 390 |
| **414** | **414** | 414 | 414 |
| **430** | **430** | 430 | 430 |
| 500 / 600 | 要求どおり | 同左 | 同左 |

**幅の下限は 86 DIP。** 現行プリセット（320 / 360 / 375 / 390 / 414 / 430 …）は**全部そのまま通る**。`innerWidth` が常に `outerWidth` と一致するので、CSS viewport はウィンドウ幅そのもの。

### 6.2 高さ

| 要求 | 実測 `height` | `outerHeight` | `innerHeight` |
|---:|---:|---:|---:|
| 1 / 50 / 90 / 94 / 95 | **96** | 96 | 64 |
| 96 | 96 | 96 | 64 |
| **97** | **97** | 97 | 65 |
| 100 | 100 | 100 | 68 |
| 200 / 375 / 400 / 700 | 要求どおり | 同左 | 要求−32 |

**高さの下限は 96 DIP。** 縦のクロームは **32 DIP**（タイトルバーのみ）。タブ付きウィンドウの 87 DIP に対し **55 DIP 得をする**。

### 6.3 画面幅超え

タブ付きと同じ 50% ルール。`{left:0, top:30, width:3840}` まで成功、3841 で失敗。

### 6.4 見えかた（実写）

`shots/05-popup-375.png`（PNG 750×1520 ＝ 375×760 DIP）:

- **タブバー無し・アドレスバー無し・ブックマークバー無し**
- 残るのは高さ 32 DIP のタイトルバー（信号機ボタン ＋ ページタイトル）だけ
- **URL が一切表示されない**。今どのページを見ているかはタイトルでしか分からない
- 戻る／進む／リロードのボタンも無い

比較: `shots/02-tabbed-request375-actual500.png`（375 を要求して 500 になったタブ付きウィンドウ。タブ・アドレスバー・拡張アイコンが全部見える）

### 6.5 「今見ているタブ」を popup 化できるか — できる（権限ゼロ）

`chrome.windows.create({tabId, type:'popup'})` で、開いているタブをそのまま popup 型ウィンドウへ移せた。**`tabs` 権限は不要**（`chrome.tabs.query({active:true, lastFocusedWindow:true})` は権限が無くても `id` は返す。返さないのは `url` / `title` / `pendingUrl` — 実測で 3 件とも `false`）。

実測した挙動と落とし穴:

- **`create` 時に渡した `width` は無視される。** `{tabId, type:'popup', width:375, height:760}` で作っても実際は移動元と同じ 900×760 で生まれた（2 回の独立した実行で同じ結果）。**直後にもう一度 `chrome.windows.update` を呼ぶ必要がある**
- その後の `chrome.windows.update` は 375 / 320 / 86 すべて要求どおり通る
- `chrome.windows.create({tabId, type:'normal'})` で**通常のタブ付きウィンドウへ戻せる**（実測: 900×760 の `type:"normal"` になった）

出典: `out4/sweep4.json` → `summary.active_tab_to_popup` / `summary.shrink` / `summary.popup_back_to_normal`、`shots/shots.json`

### 6.6 前回不採用の「ポップアップ方式」とは別物

`WINDOW_FLOOR_2026-08-30.md` と `POC_RESULT_2026-08-30.md` でオーナーが不採用としたのは、**ツールバーアイコンを押すと出る extension popup パネル（280px・フォーカスを外すと消える）**にサイトを表示する案だった。ここで測ったのは **`type:'popup'` のブラウザウィンドウ**で、独立して存在し続け、フォーカスを外しても消えず、リロードもナビゲーションもできる別の対象である。前回の不採用理由がそのまま当てはまるとは限らないので、改めて判断が要る。

---

## 7. スクリーンショット一覧

すべて `docs/evidence/extonly-2026-08-30/shots/`。撮影直前にページを再描画させてあるので、**画面に写っている数字と API の実測値が一致している**。

| ファイル | 内容 | 要求 | 実測 | PNG 実ピクセル |
|---|---|---:|---:|---|
| `01-tabbed-900-baseline.png` | タブ付き 基準 | 900 | 900 | 1800×1520 |
| `02-tabbed-request375-actual500.png` | タブ付きに 375 を要求 | 375 | **500** | 1000×1520 |
| `03-tabbed-request1-actual500.png` | タブ付きに 1 を要求 | 1 | **500** | 1000×1520 |
| `04-tabbed-requestH1-actualH375.png` | タブ付きに 高さ1 を要求 | 1 | **375** | 1800×750 |
| `05-popup-375.png` | 同じタブを popup 化して 375 | 375 | **375** | 750×1520 |
| `06-popup-320.png` | popup 320 | 320 | **320** | 640×1520 |
| `07-popup-86-floor.png` | popup に 1 を要求（下限） | 1 | **86** | 172×1520 |
| `08-popup-heightfloor-96.png` | popup に 高さ1 を要求（下限） | 1 | **96** | 1000×192 |
| `09-popup-3000-onscreen-part.png` | 3000px が通った状態 | 3000 | **3000** | 3840×1400（画面に映る分） |

補助の実写: `out/width-*.png`（幅スイープ 7 点）、`out/height-*.png`、`out3/popup-http-*.png`、`out4/moved-tab-popup-375.png` ほか。

---

## 8. 現行 `extension/` のヘルパー依存箇所

`extension/` の全ファイルを読んで列挙した。**ヘルパー＝ native messaging host（`host/viewport_deck_host.py`）と、それを叩く CLI（`bin/vw`）、登録スクリプト（`install.sh`）**。

| # | ファイル:行 | 依存の内容 | 種別 |
|---|---|---|---|
| 1 | `manifest.json:8-10` | `"permissions": ["nativeMessaging"]` | 権限宣言 |
| 2 | `manifest.json:6` | `"key"`（拡張 ID を `ejlimgik…` に固定）。host の `allowed_origins` がこの ID に紐づく | ID 固定 |
| 3 | `core.js:9` | `HOST_NAME = 'com.nanago.viewport_deck'` | host 名 |
| 4 | `core.js:36-48` | `callHost()` → `chrome.runtime.sendNativeMessage` | **host 呼び出し本体** |
| 5 | `core.js:69-82` | `setWidth()` が**まず host を試す**（`cmd:'set'` ＋ 現在 bounds を `match` で送る） | 主経路 |
| 6 | `core.js:12, 85-99` | host 失敗時に `chrome.windows.update` へフォールバックし `API_FLOOR=500` を UI へ渡す | フォールバック |
| 7 | `background.js:3,10` | ショートカット処理が `core.js` の `setWidth()` を呼ぶ＝同じ host 経路 | 間接 |
| 8 | `popup.js:1,38-44` | `hostUnavailable` / `hostError` を読み「500px 未満には native host が要る」と表示 | UI |
| 9 | `host/viewport_deck_host.py` 全体 | `/usr/bin/osascript` で `set bounds` を実行。`ping` / `set` / `get` / `list` / `restore` の 5 コマンド | host 本体 |
| 10 | `bin/vw` | host を CLI として exec。`--restore`（復帰口） | CLI |
| 11 | `install.sh:11,17-19,45-46` | `NativeMessagingHosts/com.nanago.viewport_deck.json` を Chrome / Canary / Chromium へ設置。`allowed_origins` に固定 ID を焼き込む | インストーラ |
| 12 | `README.md`「Automation 権限を許可する（初回のみ・必須）」 | macOS のオートメーション許可がユーザー操作で必要 | OS 権限 |

---

## 9. 機能の切り分け

### 9.1 ヘルパー無しで成立する機能

実測で確認済みのものだけを挙げる。

| 機能 | 権限 | 実測根拠 |
|---|---|---|
| 幅 **500px 以上**へのプリセット切り替え（640 / 768 / 1024 / 1280 / 1440 / 1920） | ゼロ | §3.1（600 で到達確認） |
| 高さ **375px 以上**への変更 | ゼロ | §4.1 |
| 現在ウィンドウの寸法・位置の取得と表示（popup UI の「現在 N px」） | ゼロ | §2.3（`chrome.windows.getAll` 可） |
| 最大化 / `normal` 復帰（`state`） | ゼロ | §3.3 |
| **画面幅を超える拡大（最大 3840、`left` 同時指定が必須）** | ゼロ | §5 |
| キーボードショートカット（`commands`） | ゼロ（`commands` は権限ではない） | 現行 manifest どおり。**本測定では未実行**（§11） |
| **popup 型ウィンドウで 86〜 の任意幅**（320 / 375 / 390 / 414 / 430 すべて到達） | ゼロ | §6.1 |
| **今見ているタブを popup 型ウィンドウへ移す／戻す** | ゼロ | §6.5 |

### 9.2 ヘルパー必須の機能

| 機能 | なぜ必須か |
|---|---|
| **タブ付きウィンドウのまま幅 500px 未満**（375 / 390 / 414 / 430 / 320） | `chrome.windows.update` が 500 でクランプする（§3）。AppleScript `set bounds` だけが `Widget::SetBounds()` を通らず貫通する（`WINDOW_FLOOR_2026-08-30.md` §2） |
| **タブ付きウィンドウのまま高さ 375px 未満** | 同上（§4） |
| 任意幅 1〜49px（現行 popup UI の `min=1`） | 同上 |
| `vw --restore`（狭くしすぎて拡張アイコンが押せなくなったときの復帰口） | 拡張の外から叩く必要がある。50px を切ると拡張アイコンは既に画面に無い（`README.md`「戻し方」） |
| `--list` / `--get`（全ウィンドウの AppleScript 座標） | host 経由でしか取れない |

### 9.3 popup 型ウィンドウに切り替えた場合に失われるもの

| 失うもの | 影響 |
|---|---|
| タブバー | 1 ウィンドウ 1 ページ。タブ切り替えができない |
| アドレスバー | **URL が見えない・URL を打てない**。リンク遷移は可能 |
| 戻る／進む／リロードのボタン | キーボード（⌘[ / ⌘R）に頼ることになる。**未実測** |
| ブックマークバー | — |
| ツールバーの拡張アイコン | popup ウィンドウ自身からは拡張 UI を開けない。**復帰口の設計が別途要る**（§9.2 の `--restore` と同じ問題が権限ゼロ版でも起きる） |
| 得るもの | 縦クロームが 87 → **32 DIP**。高さ 375 のとき CSS viewport は 288 → **343px** |

---

## 10. ストア申請で問題になりうる permissions

### 10.1 現行 manifest の宣言

```json
"permissions": ["nativeMessaging"]
"key": "MIIBIjANBgkq…"
"minimum_chrome_version": "116"
"commands": { … }
```

### 10.2 `nativeMessaging`

- **`chrome.runtime.sendNativeMessage` はこの権限が無いと関数ごと生えない**（§2.3 実測）。「宣言だけ外してコードは残す」ができない
- ストア掲載時、ユーザーには**インストール前に権限警告が出る**（`nativeMessaging` は警告を伴う権限）
- **拡張本体だけをストアからインストールしても動かない。** `com.nanago.viewport_deck.json` と `viewport_deck_host.py` は OS 側のディレクトリに置く必要があり、**ストアはこれを配布できない**。ユーザーは別途 `install.sh` 相当を実行することになる
- さらに macOS の**オートメーション許可**をユーザーが手動で与える必要がある（`README.md`）

→ 依頼の条件「**拡張を入れるだけでどんな環境でも動く**」は、`nativeMessaging` を使う限り**定義上満たせない**。

### 10.3 `key` と固定 ID

`install.sh:11` が `EXT_ID="ejlimgikbnaihoigbcmelaadniiminfj"` を `allowed_origins` へ焼き込んでいる。ストア公開版の拡張 ID はストアが払い出すため、**現行の host manifest はストア版拡張からの接続を拒否する**。案 A を採るなら `install.sh` を「ストア版 ID も許可する」形に直す必要がある。

なお **CWS がアップロード時に manifest の `key` フィールドをどう扱うか（受理されるか拒否されるか）は未実測**（§11）。

### 10.4 案 B（popup 型ウィンドウ方式）で必要な権限

**ゼロ。** `permissions` キー自体を書かなくてよい。実測で以下がすべて権限なしに動いた。

- `chrome.windows.getAll` / `get` / `update` / `create` / `remove`
- `chrome.tabs.query`（`id` と `windowId` は返る）
- `chrome.windows.create({tabId, type:'popup'})`

権限が無いと使えないものも実測した（案 B で使いたくなりそうな順）:

| API | 結果 |
|---|---|
| `chrome.tabs.query()` の `url` / `title` / `pendingUrl` | すべて `undefined`（`tabs` または host 権限が要る） |
| `chrome.tabs.captureVisibleTab()` | `Either the '<all_urls>' or 'activeTab' permission is required.` |
| `chrome.scripting` | `undefined` |
| `chrome.storage` | `undefined`（**プリセットの保存をしたければ `storage` 権限が要る**。警告なしの軽い権限） |
| `chrome.debugger` | `undefined` |
| `chrome.system.display` | `undefined`（マルチディスプレイ対応をするなら `system.display` が要る） |
| `chrome.runtime.sendNativeMessage` | `undefined` |

出典: `out4/sweep4.json` → `summary.zero_permission_capabilities`

### 10.5 その他

- `commands`（キーボードショートカット）は権限ではなく、警告も出ない
- `minimum_chrome_version: "116"` は掲載範囲を狭めるだけで審査上の問題にはならない
- content script も host_permissions も**現行拡張には無い**。ここは元々きれい

---

## 11. 未実測の項目

**実測していないものをここに全部出す。§1〜§10 の表の数値と混ぜていない。**

1. **popup 型ウィンドウで DevTools がどう使えるか。** ⌥⌘I が効くか、docked にできるか、bottom dock が使えるか。**案 B を採用できるかの決め手はここ**だが、CDP からユーザー操作としての DevTools 起動を再現できず未実測
2. popup 型ウィンドウでのキーボード操作（⌘R リロード、⌘[ / ⌘] 戻る進む、⌘L）
3. `commands`（`⌥⇧1` 等のショートカット）の実キー入力による発火。本測定は API 直呼びのみ
4. **Windows / Linux での下限。** 本測定は macOS 26.3.1 のみ。500 は Chromium 共通定数だが、高さ 375 の出所が未特定なので他 OS で同じとは言えない
5. **Retina でない環境（DPR 1）・マルチディスプレイ**での挙動。本測定は DPR 2・単一ディスプレイのみ
6. 高さ下限 375 DIP の Chromium ソース上の出所
7. Chrome Web Store が manifest の `key` フィールドを受理するか
8. `nativeMessaging` を宣言した拡張の実際の審査結果・所要日数
9. popup 型ウィンドウを Chrome 再起動後に復元できるか（現行版はタブ付きでも幅が 500 に戻る）
10. 案 B での「狭くしすぎて操作できなくなったときの復帰口」の設計と実装（86px の popup にはツールバーが無い）

---

## 12. 証拠ファイル

すべて `docs/evidence/extonly-2026-08-30/`。

| パス | 内容 |
|---|---|
| `ext/` | 最小テスト拡張のソース全文（manifest / background.js / probe.html / probe.js） |
| `www/m.html` | 計測用の実 HTTP ページ |
| `run_sweep.py` | 第 1 パス: 幅 N=1,50,200,300,400,500,600 / 高さ / 3000px / state |
| `run_sweep2.py` | 第 2 パス: 幅・高さの境界を 1px 刻み / 画面超えの上限 / popup 型の初測定 |
| `run_sweep3.py` | 第 3 パス: 実 HTTP ページでの popup 型スイープ・下限確定 |
| `run_sweep4.py` | 第 4 パス: アクティブタブの popup 化・通常復帰・権限ゼロで使える API の可否 |
| `run_shots.py` | 文書用の実写（撮影直前に再描画して数字を一致させる） |
| `out/sweep.json` … `out4/sweep4.json` | 各パスの全ステップ（要求値・返り値・読み直し・ページ側実測・タイムスタンプ） |
| `shots/shots.json` | 実写 9 点のメタ（要求値・ウィンドウ矩形・ページ実測・PNG 実ピクセル） |
| `out*/​*.png`, `shots/*.png` | 実写 |

再現手順:

```bash
cd docs/evidence/extonly-2026-08-30
python3 run_sweep.py      # 使い捨てプロファイルを作り、終了時に Chrome を落とす
python3 run_sweep2.py
python3 run_sweep3.py
python3 run_sweep4.py
python3 run_shots.py
```

`websocket-client` が要る。各スクリプトは自分専用の `--user-data-dir` と CDP ポートを使い、**オーナーの Chrome プロファイルには触れない**。
