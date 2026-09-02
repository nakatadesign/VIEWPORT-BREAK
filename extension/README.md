# VIEWPORT BREAK

Chrome の**ウィンドウ自体**を 375 / 390px などレスポンシブ確認用の幅へワンクリックで切り替える拡張。

通常のタブ付き Chrome ウィンドウには幅 **500 DIP の下限**があり、`chrome.windows.update` でも
CDP でも 500px より狭くできない（実測は `../docs/WINDOW_FLOOR_2026-08-30.md`、
本拡張での再実測は `../docs/EXTENSION_2026-08-30.md`）。
VIEWPORT BREAK は小さな **native messaging host** を併用し、AppleScript の `set bounds` 経由で
この下限を貫通する。**タブ・アドレスバー・ブックマークバー・DevTools はそのまま残る。**

デバイスエミュレーションではない。ウィンドウが本当にその幅になる。

---

## 構成

```
extension/
  manifest.json  popup.html  popup.css  popup.js  core.js  background.js
  host/viewport_deck_host.py   ← AppleScript を叩く本体（CLI としても動く）
  bin/vw                       ← CLI ショートカット
  install.sh                   ← native messaging host を登録する
  icons/                       ← 確定ロゴからの派生（assets/brand/build_brand_assets.py が生成）
```

拡張 ID は `manifest.json` の `key` で **`ejlimgikbnaihoigbcmelaadniiminfj` に固定**してある。
ディレクトリを移動しても ID は変わらないので、host 側の `allowed_origins` が壊れない。

---

## インストール

### 1. native messaging host を登録する

```bash
cd extension
./install.sh
```

`~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.nanago.viewport_deck.json`
が置かれる。冪等なので何度実行してもよい。

### 2. 拡張を読み込む

1. `chrome://extensions` を開く
2. 右上の **デベロッパー モード** を ON
3. **パッケージ化されていない拡張機能を読み込む** → `extension/` ディレクトリを選ぶ
4. ID が `ejlimgikbnaihoigbcmelaadniiminfj` になっていることを確認

> コマンドラインの `--load-extension` は **Chrome 151 では黙って無視される**（実測）。
> 必ず `chrome://extensions` から読み込む。

### 3. Automation 権限を許可する（初回のみ・必須）

最初に 500px 未満のプリセットを押すと、macOS が

> **"python3" が "Google Chrome.app" を制御するアクセスを要求しています**

と尋ねる。**「許可」を押す。** これを許可しないと 500px 未満へは切り替わらない。

後から変更する場合:
**システム設定 → プライバシーとセキュリティ → オートメーション**

許可を一度も出していない状態では、host 呼び出しが 15 秒待ってからタイムアウトし、
拡張は `chrome.windows.update` へフォールバックする（= 500px 止まり）。

---

## 使い方

ツールバーの VIEWPORT BREAK をクリック。

- 上に**現在のウィンドウ幅**が出る
- プリセット（320 / 360 / 375 / 390 / 414 / 430 / 640 / 768 / 1024 / 1280 / 1440 / 1920）を押すと即座に切り替わる。
  12 枠ちょうどで 3 列 × 4 行
  - 刻みの根拠は `../docs/PRESET_WIDTHS_2026-08-30.md`（StatCounter 日本のシェアと各機種の CSS viewport 実値）
  - 320 だけは実機シェアではなく**レスポンシブ設計の下限**（iPhone SE 1st / 5s の論理幅）。
    640 だけは実機ではなく Tailwind `sm` の境界。430 と 768 のあいだが空くのを埋める
  - 402 は 390 との差が 12px しかなく、同じレイアウトにしかならないので置いていない
- native host の状態は常設表示しない。要求した幅に届かなかったときだけ、その場に理由を出す
- キーボードショートカットからの失敗は、拡張アイコンの赤い `!` とツールチップにも残す。
  次の成功時に自動で消える
- 任意の幅も入力できる（**1〜4000**）。AppleScript 経路には技術的な下限が無く、1px まで本当に縮む
  （実測は `../docs/PRESET_WIDTHS_2026-08-30.md` §6.5・§6.9）。
  以前あった下限 50 は撤廃した。**狭くしすぎるとウィンドウから操作できなくなるので、
  戻し方（下記）を先に読む**
- **高さは変えない。** 縦の作業領域を勝手に削らない

### キーボードショートカット

| キー | 幅 |
|---|---|
| `⌥⇧1` | 375 |
| `⌥⇧2` | 390 |
| `⌥⇧3` | 768 |
| `⌥⇧4` | 1280 |
| （未割り当て） | 360 |

`chrome://extensions/shortcuts` で変更できる。360 はキー既定が埋まっているため未割り当てで登録してある。
ポップアップはウィンドウのリサイズで閉じることがあるため、連続で切り替えるならショートカットが速い。

### CLI

拡張を使わずに同じことができる。host の疎通確認にも使う。

```bash
./bin/vw 375          # 現在のウィンドウを 375px 幅に（高さは維持）
./bin/vw 390 900      # 幅と高さ
./bin/vw --list       # Chrome の全ウィンドウ
./bin/vw --get        # 現在の bounds
./bin/vw --restore    # 一番狭いウィンドウを 1280px へ戻す（→「戻し方」）
./bin/vw --restore 900
```

PATH に置くなら:

```bash
ln -s "$PWD/bin/vw" /usr/local/bin/vw
```

---

## 戻し方 — 狭くしすぎて popup を開けなくなったとき

**まずこれを打つ。**

```bash
./bin/vw --restore
```

一番狭い Chrome ウィンドウを **1280px** へ戻す。幅を指定するなら `--restore 900`。

### なぜ専用のコマンドが要るのか

任意幅の下限が 1px なので、**ウィンドウ自身からは戻せない状態を作れてしまう**。

| ウィンドウ幅 | ツールバーに何が残るか | popup から戻せるか |
|---|---|---|
| 320 | 拡張のパズルアイコンまで届く | **戻せる** |
| 50 | 信号機の赤・黄と戻るボタンだけ。**拡張アイコンは消えている** | 戻せない |
| 1 | 何も見えない。ウィンドウ枠が縦線 1 本になる | 戻せない |

実写: `../docs/evidence/min1px-recovery-2026-08-30/out/02-b-320px.png` /
`02-c-050px.png` / `02-d-001px.png`。
つまり **50px を切る前に拡張アイコンは既に押せない**。popup 以外の復帰口が必ず要る。

`--restore` が「現在のウィンドウ」ではなく**一番狭いウィンドウ**を選ぶのは、この経路を
打つ時点で Chrome は前面ですらなく、「狭くしすぎた 1 枚」を名指しできる情報がそれしか
無いため。

### 他の戻し方

- **キーボードショートカット**（`⌥⇧4` = 1280px など）。ウィンドウにフォーカスが
  当たっていれば popup を開かずに戻せる。ただし 1px のウィンドウをクリックで選ぶのは
  現実的でないため、`⌘\`` などで切り替える必要がある。**この経路は未検証**
- **緑ボタンで最大化**。1px では緑ボタン自体が見えないので当てにできない
- **Chrome を再起動する。** 幅だけは既定へ戻る（`制約` 参照）

PATH に `vw` を通しておくと、いざというとき `vw --restore` だけで済む（→ `使い方 > CLI`）。

---

## 仕組み

```
popup / ショートカット
      │  chrome.windows.getCurrent() で対象ウィンドウの bounds を取る
      ▼
core.js ── sendNativeMessage ──▶ viewport_deck_host.py
      │                              │ bounds が一致するウィンドウを AppleScript で特定
      │                              │ set bounds of window id N to {l,t,l+W,t+H}
      │                              ▼ 設定後に読み返した実測値を返す
      │◀─────────────────────────────┘
      ▼
host が使えなければ chrome.windows.update へフォールバック（500px 止まり・UI に明示）
```

対象ウィンドウは `chrome.windows` の bounds と AppleScript の bounds を突き合わせて特定する
（両者は座標系・単位とも一致する）。複数ウィンドウを開いていても誤爆しない。

---

## 制約

Chrome / macOS 側の仕様であって、拡張で直せるものではない。

- **ウィンドウ枠をドラッグすると 500px 以上に戻る。** ユーザー操作のリサイズには下限がそのまま効く。押し直せばよい
- **緑の拡大ボタンを押すと最大化される**
- **Chrome を再起動すると幅は 500 に戻る。** 位置と高さは復元されるが幅だけ戻る
- **DevTools は bottom dock か undocked にする。** right dock だと 375px のうち 225px を DevTools が奪う
- **Automation 権限が要る**（上記 3）
- AppleScript 経路は Chrome の更新で塞がれうる。塞がれたら 500px 未満は到達不能になり、
  拡張はフォールバックして 500px 止まりであることを UI に出す

---

## アンインストール

```bash
./install.sh --uninstall     # native messaging host を削除
```

拡張本体は `chrome://extensions` から削除する。
