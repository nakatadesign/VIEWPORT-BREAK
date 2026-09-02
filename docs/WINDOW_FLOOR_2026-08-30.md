# 500 DIP ウィンドウ幅下限 — 回避可否の確定調査（2026-08-30）

- 対象: 通常の Chrome ウィンドウ（タブ付き）の横幅 500 DIP 下限を回避し、**ウィンドウ自体**を 375 / 390px にできるか
- 前提文書: `POC_RESULT_2026-08-30.md`（500 DIP 下限の実測、popup のみ 280px 到達、代替手段12件の比較）
- オーナー方針: **ポップアップ方式は不採用**（開発中に常時見るウィンドウのため）
- 実施日時: 2026-08-30 10:25〜11:10 JST
- Chrome: 151.0.7922.174 / ディスプレイ 3840×2160 物理・論理 1920×1080・DPR 2 / 30Hz
- EVALUATION_MODE: **hybrid**（幅の数値はすべて機械判定、UI の見えかたはスクリーンショット実測）

**本文書で「実測」と書いた数値は、すべてこの機で Chrome を起動して取得した値である。** 実測していない項目は §7 に未検証として分離した。

守った停止線: 運用中の X / CDP プロファイルに未接触（開始時に Chrome プロセスは 0 件だった）/ 新規ブラウザのインストールなし / Chromium のビルド・フォークなし / 外部送信・投稿なし / 一時プロファイル（56MB）とポート 9344 は削除・解放済み。

---

## 1. 結論

**回避可能。断定する。** 前回 PoC の「通常ウィンドウは 375/390 に到達できない」という結論は、**CDP `Browser.setWindowBounds` と起動フラグに限れば正しいが、経路全体としては誤りだった。**

500 DIP 下限を貫通し、**タブバー・アドレスバー・ブックマークバー・DevTools をすべて備えた通常の Chrome ウィンドウを 375 / 390px にする手段が 2 つ、実測で確定した。**

| # | 手段 | 375/390 到達 | 実測下限 | タブ | アドレスバー | DevTools | 常時開発 |
|---|---|---|---|---|---|---|---|
| **1** | **AppleScript `set bounds`（通常ウィンドウ）** | **到達する** | **50px（それ以下は未試行）** | **あり** | **あり** | **あり** | **可（本命）** |
| **2** | **`--app=URL` + `--window-size=375,900`** | **到達する** | **100px（それ以下は未試行）** | なし | なし | あり（別窓/bottom） | 可（用途限定） |
| 3 | CDP `Browser.setWindowBounds`（通常ウィンドウ） | しない | 500px でクランプ | — | — | — | — |
| 4 | 起動フラグ `--window-size=375,900`（通常ウィンドウ） | しない | 500px でクランプ | — | — | — | — |
| 5 | System Events / Accessibility API `set size` | しない | 500px でクランプ | — | — | — | — |
| 6 | `--kiosk` | しない | 解除すると 500px | — | — | — | — |

**推奨: 手段 1（AppleScript）。** 通常の Chrome ウィンドウがそのまま 375px になる。失うものが無い。唯一の制約は「Chrome 起動ごとに 1 回コマンドを打ち直す必要がある」ことだけで、これは 1 行のスクリプトで自動化できる。

---

## 2. Chromium ソース上の下限の実装箇所

### 2.1 定数の定義

`chrome/browser/ui/views/frame/layout/browser_view_layout.h`（Chrome 151 系 = `refs/branch-heads/7922`、L104）:

```cpp
// The minimum width for the normal (tabbed or web app) browser window's
// contents area. This should be wide enough that WebUI pages (e.g.
// chrome://settings) and the various associated WebUI dialogs (e.g. Import
// Bookmarks) can still be functional. This value provides a trade-off between
// browser usability and privacy - specifically, the ability to browse in a
// very small window, even on large monitors (which is why a minimum height is
// not specified). This value is used for the main browser window only, not
// for popups.
static constexpr int kMainBrowserContentsMinimumWidth = 500;
```

- **コメント自身が「main browser window only, not for popups」と明記している。** 前回 PoC の popup 280px 到達はこの仕様どおり。
- **高さの下限は意図的に設けられていない**（「which is why a minimum height is not specified」）。実測でも `--window-size=375,900` の高さ 900 はそのまま通った。
- 動機は**プライバシー**（極小ウィンドウでの閲覧を防ぐ）と WebUI の可用性。セキュリティ境界ではない。

### 2.2 どのウィンドウ種別に効くか

`BrowserViewLayout::CreateLayout()`（`browser_view_layout.cc`）がブラウザ種別ごとにレイアウト実装を出し分けており、**下限はレイアウト実装ごとに違う**。

| ブラウザ種別 | レイアウト実装 | `GetMinimumSize()` の幅 |
|---|---|---|
| `TYPE_NORMAL`（通常のタブ付き） | `BrowserViewTabbedLayoutImpl` | `std::max({..., kMainBrowserContentsMinimumWidth})` → **500 固定** |
| `TYPE_APP` / `TYPE_APP_POPUP` | `BrowserViewAppLayoutImpl` | **`is_web_app` が true のときだけ 500**。false なら実質無制限 |
| `TYPE_POPUP` / `TYPE_DEVTOOLS` / `TYPE_PICTURE_IN_PICTURE` | `BrowserViewPopupLayoutImpl` | `kMinContentsSize(1, 1)` → **下限なし** |

`BrowserViewAppLayoutImpl::GetMinimumSize()`（151 系）の該当部:

```cpp
// The minimum size of a window is unrestricted for a unframed mode app.
if (delegate().GetUnframedModeEnabled()) {
  return gfx::Size(1, 1);
}
...
// For full PWAs, there is a minimum content width.
bool is_web_app = browser() && browser()->is_type_app() &&
                  web_app::AppBrowserController::IsWebApp(browser());
if (is_web_app) {
  contents_size.SetToMax(gfx::Size(kMainBrowserContentsMinimumWidth, 1));
}
```

**`--app=<URL>` は「インストール済み PWA」ではないため `AppBrowserController::IsWebApp()` が false になり、500 の適用対象外になる。** これが §4 の実測（100px まで到達）の機序である。

### 2.3 プラットフォーム

**macOS 固有ではない。全プラットフォーム共通。** 定数もレイアウト実装も `chrome/browser/ui/views/` 配下、すなわち Windows / Linux / ChromeOS / macOS が共有する toolkit-views の層にある。`#if BUILDFLAG(IS_MAC)` によるガードは無い（ChromeOS だけ system app を除外する分岐が 1 つあるのみ）。

macOS では、この値が `NativeWidgetMac::OnSizeConstraintsChanged` → `NativeWidgetNSWindowBridge::SetSizeConstraints` → `gfx::ApplyNSWindowSizeConstraints` の経路で **NSWindow の `contentMinSize` として AppKit に渡される**。さらに `NativeWidgetNSWindowBridge::SetBounds` には次のコメント付きの明示的なクランプがある:

```objc
// -[NSWindow contentMinSize] and [NSWindow contentMaxSize] are only checked
// by Cocoa for user-initiated resizes. This is not what toolkit-views
// expects, so clamp.
gfx::Size clamped_content_size = GetClientSizeForWindowSize(window_, new_bounds.size());
clamped_content_size.SetToMax(minimum_content_size);
```

**この「Cocoa は `contentMinSize` をユーザー操作のリサイズでしか見ない」という一文が、AppleScript が下限を貫通する理由そのものである（§5.2）。**

### 2.4 フラグで無効化できるか

`kMainBrowserContentsMinimumWidth` は `static constexpr` で、**`base::Feature` にも `switches::` にも紐づいていない。** `GetMinimumSize()` 内でも無条件に `std::max()` に渡されており、実行時に切り替える分岐が存在しない。`--enable-features` / `--disable-features` / `chrome://flags` で外す手段はソース上に無い。§4 の実測でも、起動フラグ経由では一切下がらなかった。

---

## 3. 起動オプション・フラグの実測（依頼 2）

専用プロファイル + `--remote-debugging-port=9344` で起動し、`Browser.getWindowBounds` と `window.innerWidth` の両方で確認した。

### 3.1 `--window-size` — 通常ウィンドウでは効かない

| 起動コマンド | 要求 | 実ウィンドウ幅 | `innerWidth` | 高さ |
|---|---|---|---|---|
| `--window-size=375,900`（通常） | 375 | **500** | **500** | 900（要求どおり） |
| `--window-size=375,900 --disable-infobars`（通常） | 375 | **500** | **500** | 900 |

**幅だけが 500 にクランプされ、高さは要求どおり通る。** §2.1 の「高さの下限は設けていない」というソースの記述と完全に一致した。

### 3.2 CDP `Browser.setWindowBounds` — 通常ウィンドウでは効かない

要求 → (実ウィンドウ幅 / `innerWidth`):

```
800→800/800  600→600/600  520→520/520  500→500/500
480→500/500  450→500/500  390→500/500  375→500/500
360→500/500  320→500/500  280→500/500  200→500/500  100→500/500
```

**500 を境に完全にクランプする。** 前回 PoC の U-7 を再現した。

### 3.3 `--kiosk` — 使えない

| 状態 | ウィンドウ | `innerWidth` |
|---|---|---|
| `--kiosk` 起動直後 | 1920×1080 / `fullscreen` | 1920 |
| `windowState:normal` に戻して 375 を要求 | **500**×800 | **500** |

kiosk はフルスクリーン化するだけで、解除すると通常ウィンドウの 500 下限に戻る。**幅制御の手段にならない。**

### 3.4 `--enable-features` 系

§2.4 のとおりソース上に対応する feature flag が存在しないため、試すべき候補が無い。**フラグによる回避手段は無いと断定する。**

---

## 4. app モード `--app=URL` の実測（依頼 3）

### 4.1 下限は掛からない

`--app=file://.../probe.html` で起動し、`Browser.setWindowBounds` で幅を掃引した:

```
800→800/800  600→600/600  520→520/520  500→500/500
480→480/480  450→450/450  390→390/390  375→375/375
360→360/360  320→320/320  280→280/280  200→200/200  100→100/100
```

**13 段階すべてが ±0px で一致し、クランプは一度も起きなかった。** §2.2 のソース分岐（`is_web_app == false`）が実機で裏付けられた。

さらに **`--app=URL --window-size=375,900` は起動した時点で 375px** になる:

| 項目 | 値 |
|---|---|
| 起動直後のウィンドウ | 375 × 900 |
| `innerWidth` / `outerWidth` | **375 / 375** |
| `innerHeight` | 868（ウィンドウ装飾はタイトルバー 32px のみ） |
| DPR | 2 |

CDP も AppleScript も要らず、**起動フラグだけで 375px の実ウィンドウが得られる。**

### 4.2 開発用途としての使用感

実測（スクリーンショット `docs/evidence/window-floor-2026-08-30/crop-appmode.png`）:

| 項目 | 結果 |
|---|---|
| タブバー | **無い**。Cmd+T を送っても page target は 1 のまま増えなかった（実測） |
| アドレスバー / 戻る・進む / 再読込 | **無い**。タイトルバーにページタイトルが出るだけ |
| ブックマークバー | **無い** |
| 拡張のツールバーアイコン | **無い**（アイコンを置くツールバー自体が存在しない） |
| DevTools | `Target.openDevTools` は成功。**別ウィンドウで開き**、app ウィンドウの幅 375 と `innerWidth` 375 は変化しなかった（実測） |
| 縦の作業領域 | 868px。通常ウィンドウ（同じ 900px 高で 813px）より **55px 広い** |
| ウィンドウサイズの永続化 | **しない**。390×844 に設定して正常終了 → 再起動で既定の 1200×916 に戻った（実測）。`--window-size` を毎回渡せば決定的に解決する |

> 判定: **技術的には完全に成立する。**「375px の実寸ビューポートを、余計な UI 無しで常時表示する」という目的だけなら app モードが最も素直で、縦も広い。
>
> ただし**タブもアドレスバーも拡張アイコンも無い**ため、依頼 6 の「常時開発に使えるか」という基準では**単独では不足**する。URL を打ち替えながら制作する用途には向かない。**手段 1 が使える以上、app モードを選ぶ理由は無い。**

---

## 5. OS 側から縮められるか（依頼 4）

**ここが今回の最大の発見。同じ「OS 側」でも、2 つの経路で結果が正反対になった。**

### 5.1 AppleScript `set bounds` — **下限を貫通する**

`tell application "Google Chrome" to set bounds of window 1 to {left, top, right, bottom}` を**通常のタブ付きウィンドウ**に対して発行し、CDP で読み返した。

| 要求幅 | AppleScript 読み返し | CDP ウィンドウ幅 | `innerWidth` | 実描画幅（CSS px） | 一致 |
|---|---|---|---|---|---|
| 500 | 500 | 500 | 500 | 500 | ±0 |
| 450 | 450 | 450 | 450 | 450 | ±0 |
| 430 | 430 | 430 | 430 | 430 | ±0 |
| 414 | 414 | 414 | 414 | 414 | ±0 |
| 393 | 393 | 393 | 393 | 393 | ±0 |
| **390** | **390** | **390** | **390** | **390** | **±0** |
| **375** | **375** | **375** | **375** | **375** | **±0** |
| 360 | 360 | 360 | 360 | 360 | ±0 |
| 320 | 320 | 320 | 320 | 320 | ±0 |
| 280 | 280 | 280 | 280 | 280 | ±0 |
| 240 | 240 | 240 | 240 | 240 | ±0 |
| 200 | 200 | 200 | 200 | 200 | ±0 |
| 150 | 150 | 150 | 150 | 150 | ±0 |
| 100 | 100 | 100 | 100 | 100 | ±0 |
| 50 | 50 | 50 | 50 | 50 | ±0 |

**15 段階すべて一致（15/15）。クランプは一度も起きなかった。** 実描画幅は `document.getElementById('bar').getBoundingClientRect().width` で測っており、レイアウトが実際にその幅で組まれていることを示す。**50px より下は試していない**（実用範囲外のため）。

`window.innerWidth` と CDP の `Browser.getWindowBounds` が独立に同じ値を返した。**縮小表示でもクリッピングでもなく、ウィンドウが本当にその幅になっている。**

スクリーンショット `crop-as-280.png`（280px の通常ウィンドウ）では、タブストリップ・タブ・`+`・戻る・再読込・アドレスバー・ブックマーク★・オーバーフロー `»` がすべて描画され、機能していた。

AppleScript の `bounds` は `{left, top, right, bottom}` の論理ポイントで、CDP の `Browser.getWindowBounds` と座標系・単位ともに一致した（`{60,60,435,960}` → CDP `left:60, top:60, width:375, height:900`）。

### 5.2 なぜ貫通するのか（機序）

`chrome/browser/ui/cocoa/applescript/window_applescript.mm` は `bounds` に専用のセッターを持たず、**未定義キーとして NSWindow へ KVC でそのまま転送している**:

```objc
- (void)setValue:(id)value forUndefinedKey:(NSString*)key {
  [self.nativeHandle setValue:value forKey:key];
}
```

つまり AppleScript の `set bounds` は `-[NSWindow setFrame:]` を直に叩き、**`Widget::SetBounds()` を一切通らない。** §2.3 で見た toolkit-views 側の明示的クランプ（`clamped_content_size.SetToMax(minimum_content_size)`）はこの経路には存在しない。そして AppKit 自身は、同コメントが述べるとおり `contentMinSize` を**ユーザー操作のリサイズでしか検査しない**。結果として下限が誰にも適用されない。

**これは Chrome の抜け道ではなく、Chrome 側の実装がクランプを 1 箇所（`Widget::SetBounds`）にしか置いていないことの帰結である。** 将来 AppleScript 層に専用セッターが入れば塞がりうる（§8 の残リスク）。

### 5.3 System Events / Accessibility API `set size` — **クランプされる**

`tell application "System Events" to tell process "Google Chrome" to set size of window 1 to {W, 900}`:

| 要求幅 | AX 読み返し | CDP ウィンドウ幅 | 判定 |
|---|---|---|---|
| 375 | **500** | **500** | クランプ |
| 420 | **500** | **500** | クランプ |
| 480 | **500** | **500** | クランプ |
| 500 | 500 | 500 | ちょうど下限 |
| 520 | 520 | 520 | 通る |

**AX 経由は 500 でクランプする。** AX の `AXSize` 設定は AppKit のユーザーリサイズ相当の経路を通るため、`contentMinSize` がそのまま効く。**下限が正確に 500 であることを、CDP とは独立した経路で裏付ける対照実験にもなっている。**

なお AX で**読む**ぶんには問題なく、AppleScript で 280px にした直後に AX が `280, 840` を正しく返した（=ウィンドウが本当に 280 だったことの三重確認）。

### 5.4 ウィンドウ管理ツール

この機には **Rectangle.app** がインストールされている。Rectangle をはじめとする macOS のウィンドウ管理ツールは **AX API（`AXSize` / `AXPosition`）を使う**ため、§5.3 と同じく 500 でクランプされる。またプリセット（画面 1/2、1/3 等）は 1920 幅では最小でも 640 になり、そもそも 500 を下回らない。**Rectangle 自体の実測は行っていない（§7 N-3）が、機序上ここに例外は無い。**

---

## 6. 手段 1（AppleScript）の運用適性（依頼 6）

### 6.1 耐久性 — 実測 12 項目すべてで 375px を維持

375px にした通常ウィンドウに対して操作を行い、その都度ウィンドウ幅と `innerWidth` を測った。

| # | 操作 | ウィンドウ幅 | `innerWidth` | 判定 |
|---|---|---|---|---|
| 0 | AppleScript で 375 に設定 | 375 | 375 | — |
| 1 | **10 秒放置**（遅延クランプの有無） | 375 | 375 | 維持 |
| 2 | リロード | 375 | 375 | 維持 |
| 3 | `about:blank` へ遷移 | 375 | 375 | 維持 |
| 4 | 元ページへ遷移 | 375 | 375 | 維持 |
| 5 | 新規タブを開く | 375 | 375 | 維持 |
| 6 | タブを閉じる | 375 | 375 | 維持 |
| 7 | DevTools を開く（right dock） | 375 | **150** | ウィンドウは維持、contents が DevTools に食われる |
| 8 | DevTools を閉じる | 375 | 375 | 維持 |
| 9 | 最小化 | 375 | 375 | 維持 |
| 10 | 最小化から復帰 | 375 | 375 | 維持 |
| 11 | AppleScript でウィンドウを移動 | 375 | 375 | 維持 |
| 12 | ブックマークバー切替 | 375 | 375 | 維持 |

**スナップバックは一度も起きなかった。** 一度縮めれば、そのセッション中は放っておいても 375 のままである。CDP の override（前回 PoC 方式 A）と違い、**接続を張り続ける必要が無い。**

### 6.2 DevTools との併用 — bottom dock か undocked なら成立

375px ウィンドウで DevTools を開いたときの `innerWidth`:

| dock 位置 | ウィンドウ幅 | `innerWidth` | `innerHeight` | 判定 |
|---|---|---|---|---|
| right（既定） | 375 | **150** | 813 | **使えない**。DevTools が 225px を奪う |
| **bottom** | 375 | **375** | 813 → **513** | **成立。幅は無傷、縦を分け合う** |
| **undocked（別ウィンドウ）** | 375 | **375** | **813** | **成立。幅も縦も無傷。最良** |

スクリーンショット `crop-bottom.png` で、375px ウィンドウ + bottom dock の DevTools が Elements / Styles パネルまで正常に機能していることを確認した。

> 前回 PoC の「dock=bottom を既定にする」という推奨は、この方式でもそのまま有効。**さらに undocked を選べば縦も失わない。** dock 位置はプロファイルの `devtools.preferences.currentDockState` に永続化されるため、一度設定すれば維持される（本検証でも Preferences 直接書き換えで dock を切り替えて起動している）。

### 6.3 UI の利用可否

| 項目 | 375px | 実測根拠 |
|---|---|---|
| タブバー・タブ・新規タブ `+` | **使える** | `crop-bottom.png` / 耐久性 #5・#6 |
| アドレスバー（omnibox） | **使える**。ただし表示テキストは `/private/...` まで切り詰められる | `tb-375.png` |
| 戻る・再読込・ブックマーク★ | **使える**（ツールバーに直接残る） | `tb-375.png` |
| 進む・プロファイルアバター | **オーバーフロー `»` に畳まれる**（500px では直接表示） | `tb-375.png` vs `tb-500.png` |
| ブックマークバー | **使える**。375px で表示すると `innerHeight` 813 → **779**（バー 34px）、幅は 375 のまま | `t9_ext.json` / `crop-ext.png` |
| 拡張機能 | ローカル unpacked MV3 拡張を `--load-extension` で読み込み、**375px でも service worker target が生存**していることを実測。ただし**拡張のアクションアイコン自体は 600 / 500 / 430 / 375 のどの幅でもツールバーに現れなかった**ため、「375px でアイコンが押せるか」は**依然として未実測**（§7 N-1） | `t9_ext.json` / `tb-*.png` |
| `⋮` メニュー | **使える** | `tb-375.png` |
| DevTools | **使える**（bottom / undocked） | §6.2 |
| WebUI（`chrome://settings`） | **使える**。ナロー版レイアウトに切り替わり、ハンバーガー + 検索で操作可能。ただし**横スクロールバーがわずかに出る** | `crop-settings.png` |

**ツールバーの構成を 600 / 500 / 430 / 375px で比較したところ、375px 固有の機能欠落は無かった。** 500px から 375px へ縮めて起きる変化は「進む・アバターが `»` に畳まれる」「omnibox のテキストが短く切れる」の 2 点だけで、どちらも到達不能にはならない。

`chrome://settings` の挙動は、まさに定数のコメントが守ろうとしていたもの（§2.1）である。**実際には 375px でも機能しており、劣化は横スクロールバーが出る程度だった。**

### 6.4 再起動をまたぐか — またがない

| タイミング | ウィンドウ | `innerWidth` |
|---|---|---|
| AppleScript で 375 に設定 | left 60 / top 60 / **375** × 840 | 375 |
| Chrome を正常終了 → 再起動 | left 60 / top 60 / **500** × 840 | **500** |

**位置（60,60）と高さ（840）は復元されるが、幅だけが 500 に戻る。** 復元時に通常ウィンドウの下限が適用されるため。

> **したがって「Chrome を起動したら 1 回コマンドを打つ」運用が必要になる。** これが手段 1 の唯一の実質的な制約である。

### 6.5 ユーザーがウィンドウ枠をドラッグすると 500 に戻る

§5.3 のとおり、**ユーザー操作のリサイズには `contentMinSize` = 500 がそのまま効く。** 375px のウィンドウの端を掴んで動かした瞬間、幅は 500 以上にジャンプする。縮め直すには再度 AppleScript を打つ。

同様に、**緑の拡大ボタンを押すと最大化される**（実測: `set bounds` で 375 にした後に zoom ボタンをクリック → `0, 88, 1920, 1080`）。

### 6.6 運用レシピ

```bash
# 起動後に一度だけ。W=幅, H=高さ, X/Y=左上
osascript -e 'tell application "Google Chrome" to set bounds of window 1 to {60, 60, 435, 960}'   # 375 × 900
osascript -e 'tell application "Google Chrome" to set bounds of window 1 to {60, 60, 450, 960}'   # 390 × 900
```

- ウィンドウは **ID で名指しできる**（実測）。`tell application "Google Chrome" to get id of every window` で列挙し、`set bounds of window id <ID> to {...}` で特定のウィンドウだけを縮められる。複数ウィンドウを開いていても誤爆しない。
- 実行には **Automation 権限**（システム設定 → プライバシーとセキュリティ → オートメーション）で、コマンドを実行する側のアプリから「Google Chrome」への許可が必要。本検証の環境では既に許可済みで、プロンプトは出なかった。
- DevTools は **undocked**（別ウィンドウ）にしておくと、375px の縦を一切削らない。

---

## 7. 未検証のまま残る項目

| # | 項目 | なぜ未検証か |
|---|---|---|
| **N-1** | **拡張機能のアクションアイコンが 375px で押せるか** | ローカル unpacked 拡張を読み込ませ、375px で service worker が生存することまでは実測した。しかし**アクションアイコン自体が 600/500/430/375 のどの幅でもツールバーに現れなかった**（この使い捨てプロファイル固有の事情と見られる）ため、アイコンの操作性は確認できていない。Web Store からの拡張導入は行っていない |
| **N-2** | **拡張の content script の動作** | `file://` に対する content script が動かなかった（`data-ext-ran` が null）。拡張ごとの「ファイル URL へのアクセスを許可」トグルが未設定のためで、幅とは無関係。`http(s)` での確認は行っていない |
| **N-3** | **Rectangle.app 実物での挙動** | AX 経由なので §5.3 と同じくクランプされるはずだが、Rectangle 自体は起動していない |
| **N-4** | **Edge / Brave / Arc / Vivaldi 等の Chromium 系別ブラウザ** | **この機には 1 つもインストールされていない**（`/Applications`・`~/Applications`・Spotlight で確認済み）。停止線でインストールを禁じられているため**実測不能**。調査のみ → §7.1 |
| **N-5** | **運用中の X / CDP プロファイルでの再現** | 停止線により未接触。機序はプロファイル非依存なので同じはずだが、実測していない |
| **N-6** | **長時間の常駐運用での安定性** | 最長 10 秒放置までしか見ていない。数時間〜数日の維持は未検証 |
| **N-7** | **50px 未満の挙動** | 実用範囲外のため試していない |
| **N-8** | **外部ディスプレイ・別 DPR 環境での挙動** | 単一ディスプレイ（DPR 2）でのみ実測 |
| **N-9** | **`window.outerWidth` の値ズレ** | 280px 時に `innerWidth` 280 に対し `outerWidth` が 320（直前の値）を返す事例を観測。AppleScript 経路では `outerWidth` の更新が遅れる可能性がある。**再現条件を詰めていない** |

### 7.1 別ブラウザ（依頼 5）— 全て未検証

**この機にインストールされている Chromium 系ブラウザは Google Chrome のみ。** Edge・Brave・Arc・Vivaldi・Opera・Chromium はいずれも存在しない（Safari は非 Chromium）。停止線「新規ブラウザのインストールはしない」により、**実測は行っていない。**

調査に基づく見込み（**すべて未検証**）:

- `kMainBrowserContentsMinimumWidth` は upstream Chromium の `chrome/browser/ui/views/` にあり、Chromium 系ブラウザは通常この層をそのまま継承する。**Edge・Brave・Vivaldi・Opera でも 500 下限が同様に存在する可能性が高い。**
- 同様に、AppleScript による貫通（§5.2）は「AppleScript の `bounds` を NSWindow へ KVC 転送する」という Chromium 由来の実装に依存する。**各ブラウザがこの層を変更していなければ同じ抜け道が成立する見込みだが、AppleScript 辞書は各社が独自に拡張している領域であり、確度は低い。**
- Arc は Chromium ベースだがウィンドウ UI を大幅に作り替えており、**推測が最も当てにならない。**

**この節は「調査止まり」であり、断定材料にしてはならない。** そもそも手段 1 が Chrome 単体で成立しているため、別ブラウザを検証する実務上の必要は無い。

---

## 8. 残リスクと、前回 PoC 結論への訂正

### 8.1 残リスク

1. **AppleScript 経路は Chrome の更新で塞がれうる。** §5.2 のとおり、これは仕様として保証された API ではなく「クランプが `Widget::SetBounds` にしか置かれていない」という実装上の帰結である。`window_applescript.mm` に `bounds` の専用セッターが入れば、その日から 500 に戻る。**固定依存する場合は、Chrome 更新のたびに 1 行で再検証できるようにしておくべき。**
2. **フォールバックは app モード（§4）。** こちらはソース上「PWA でなければ下限を適用しない」という明示的な分岐であり、AppleScript 経路より意図的で、塞がれにくい。タブとアドレスバーを失う代償はあるが、375px 自体は確実に得られる。
3. **ユーザーが枠をドラッグ／緑ボタンを押すと 500 以上に戻る**（§6.5）。事故ではなく仕様。打ち直せば済む。
4. **再起動ごとに打ち直しが必要**（§6.4）。
5. **Automation 権限が要る**（§6.6）。
6. **実効 effort が推奨より低い状態で実行した。** `RECOMMENDED_EFFORT=max` に対し `EFFECTIVE_EFFORT=high`（context safety cap）。§7 の未検証項目は、この制約下で意図的に切り落とした範囲である。

### 8.2 `POC_RESULT_2026-08-30.md` への訂正

同文書 §8 の代替手段テーブルのうち、**行 8「AppleScript / System Events」の判定「回避できない・未実測・採る理由がない」は誤りだった。** 正しくは:

- **AppleScript（Chrome 独自の scripting）= 回避できる。50px まで実測。**
- System Events / AX = 回避できない（500 でクランプ。今回実測）。

両者を「OS 側」として 1 行に束ねていたことが誤判定の原因である。**この 2 つは Chrome 内部で別経路であり、結果が正反対になる。**

また、同 §1 の結論 7「通常ウインドウ外形は 500 でクランプし、375/390 に到達できない」は、**「CDP と起動フラグでは到達できない」に限定して読むべき**であり、経路全体としては到達できる。

---

## 9. 証拠（CLAWD_EVIDENCE）

生データは `docs/evidence/window-floor-2026-08-30/` に同梱した（本 commit に含む）。

| ファイル | sha256 | 内容 |
|---|---|---|
| `t2_app.json` | `6527bad1cd7ac40f573b8a746b9195eba6d636818fac2f0c52518e3ced0135de` | §3.2 / §4.1 通常ウィンドウ vs app モードの幅掃引 |
| `t3_appdetail.json` | `8abd3598459ca230154a464bdec39143dd5b447071f3dacfd81694f09dfbbc8d` | §4.1 `--app`+`--window-size` / §4.2 永続化・DevTools |
| `t4_osresize.json` | `1006f2f9412b9ff3b373bd5538f35736eaf3bb2630800257d64ffcea1a53943a` | §5.1 AppleScript 375/320/280 / §5.3 AX クランプ |
| `t5_durability.json` | `ba911e952f0ad3d3d9a0b5d39cb1207396b99c77717b4de0fbc37929e80084ea` | §6.1 耐久性 12 項目 |
| `t6_final.json` | `fd275232d4ac5b9bcf39cdc4863ad8ffd101eae9ee40e33c40d775e2207c4de6` | §6.4 再起動 / §5.3 AX 掃引 / §3.3 kiosk |
| `t7_devtools.json` | `1c9549f1739a8704f922dc8a201cd275648a67cd16db3254b11bdcf086dcd6bf` | §6.2 dock 位置別 / §4.2 app モード Cmd+T |
| `t8_limits.json` | `b930465f4086cf9e429204fdde7bbca6b4b7f334ea402c5e8e53d4e61f435bdc` | §5.1 AppleScript 15 段階掃引（500→50） |
| `t9_ext.json` | `2c3c6b2703153d37815a4a13c7fdb9c6a8915356bd74e1585648696114cd32ef` | §6.3 拡張読み込み・ブックマークバー・375px |
| `probe.html` | — | 計測に使った検証ページ（`viewport` meta なし） |
| `probe-extension/` | — | §6.3 で読み込んだローカル unpacked MV3 拡張（Web Store 未使用） |

スクリーンショット（実寸確認に使用、いずれもウィンドウ部分の切り出し）:

| ファイル | 内容 |
|---|---|
| `crop-as-280.png` | §5.1 AppleScript で 280px にした通常ウィンドウ（タブ・アドレスバーとも機能） |
| `crop-bottom.png` | §6.2 375px + DevTools bottom dock（Elements / Styles 動作） |
| `crop-appmode.png` | §4.2 app モード 375px（タイトルバーのみ） |
| `crop-settings.png` | §6.3 375px の `chrome://settings`（ナロー版レイアウト） |
| `crop-ext.png` | §6.3 375px + ブックマークバー表示 + 拡張読み込み済み |
| `tb-600.png` / `tb-500.png` / `tb-375.png` | §6.3 ツールバー構成の幅別比較 |

Chromium ソース（Chrome 151 系 = `refs/branch-heads/7922` から取得）の sha256:

| ファイル | sha256 |
|---|---|
| `browser_view_layout.h` | `e059f515a2f449f7ece7e01f89c4ee4ee761d3a871b2ecd12339991c9083323d` |
| `browser_view_tabbed_layout_impl.cc` | `b74868d58a5139e8742cfaeab6957a1a1e5b17c7f836b68f9b0f5052a4e37d6b` |
| `browser_view_app_layout_impl.cc` | `e1c17b030732d7f47e4f6e827c56c4c16b92deae14ecbd8bfe8d144b653e6060` |
| `browser_view_popup_layout_impl.cc` | `1980ed77a8853ec56246169a63185932c9965609238ba97d3a3e1f61d3ee62e5` |

ソース本体は容量の都合で repo に含めていない（`https://chromium.googlesource.com/chromium/src/+/refs/branch-heads/7922/chrome/browser/ui/views/frame/layout/` から同じ内容を再取得できる）。

---

## 10. オーナー判断を要する項目

1. **手段 1（AppleScript）を本命にしてよいか。** 通常の Chrome ウィンドウがそのまま 375/390px になり、タブもアドレスバーも DevTools も残る。代償は「起動ごとに 1 行打ち直す」「枠をドラッグすると 500 に戻る」の 2 点のみ。
2. **前回 PoC の方式 A（CDP `Emulation.setDeviceMetricsOverride`）はまだ必要か。** 手段 1 は**ウィンドウ自体**を縮めるため、右側の白い余白（前回 §3.1）も、CDP 接続の張りっぱなしも、DevTools 幅表示 UI の不一致（前回 §4.3）も発生しない。**目的が「375px の実ウィンドウ」だけなら、方式 A は不要になる可能性がある。** 1920 プリセットなど幅 > 画面の表示が要るなら方式 A との併用が要る。
3. **DevTools を undocked（別ウィンドウ）にしてよいか。** bottom dock だと縦が 813 → 513 に減る。undocked なら縦を失わない代わりにウィンドウが 2 枚になる。
4. **N-1（拡張のアクションアイコン）を追検証すべきか。** 常時開発で拡張のアイコンをクリックする運用なら、実際に使っている拡張を入れたプロファイルで 375px の操作性を確認する価値がある。ツールバー自体は 375px で欠落が無いこと（§6.3）まで確認済みなので、優先度は高くない。
5. **`POC_RESULT_2026-08-30.md` の訂正を正本に反映するか**（§8.2）。行 8 の判定が誤っていた。
