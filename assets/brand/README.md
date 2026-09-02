# VIEWPORT BREAK — ブランド資産

確定ロゴ（黒背景・アイソメの透明ガラス板 2 枚が重なった V と B のマーク）と、
そこから派生させたアプリアイコン一式。

## 構成

```
assets/brand/
  master/viewport-break-logo-master-1200.png   ← 無加工のマスター。1200x1200 RGB
  build_brand_assets.py                        ← master からすべての派生を作る
  out/                                         ← 派生物（コミット済み。再生成可能）
  hero/                                        ← README 冒頭用の別レンダー（手動入稿。out/ とは別系統）
```

`hero/` は master 由来ではない別レンダーで、`build_brand_assets.py` の対象外。
`viewport-break-hero-1280x640.png` が入稿された無加工の原本。
README 冒頭ではこれを加工せず `width="100%"` で本文幅いっぱいに使う。
マークは 1280x640 の中で 422x416px しか占めておらず左右は真っ黒（RGB 0,0,0）だが、
ロゴを大きく見せることを優先し、この黒余白は許容する方針。

master は **無加工**。sha256 `146f5da4d33df470db8544d4c610ac965471ef21ce9f1f9191399fdc742373e7`。
`build_brand_assets.py` は起動時にこの値を照合し、違っていれば何もせず止まる。
派生を再入力にしない（世代劣化を避ける）ので、派生し直すときは必ず master から回す。

再生成:

```
python3 assets/brand/build_brand_assets.py     # 要 Pillow + numpy（デザイン時のみの依存）
```

## 出力

| 出力 | 用途 | 形 |
| --- | --- | --- |
| `out/extension/icon{16,32,48,128}.png` | Chrome 拡張 | 黒の角丸正方形 |
| `out/macos/AppIcon.iconset/*.png`（10 枚） | macOS `.icns` | macOS グリッド（1024 中 824 の squircle） |
| `out/ios/AppIcon-*.png`（15 枚） | iOS / iPadOS | 黒ベタ全面・アルファ無し |
| `out/web/favicon-*.png` / `favicon.ico` | favicon | 黒の角丸正方形 |
| `out/web/apple-touch-icon.png` | apple-touch-icon | 黒ベタ全面 180px |
| `out/web/pwa-{192,512}.png` | PWA `manifest.icons` (`purpose: any`) | 黒の角丸正方形 |
| `out/web/pwa-maskable-{192,512}.png` | PWA `manifest.icons` (`purpose: maskable`) | 黒ベタ全面・マーク 55% |
| `out/share/og-image-1200x630.png` | OGP | 黒地 + マーク + ワードマーク |
| `out/share/twitter-card-1200x600.png` | Twitter card | 同上 |
| `out/logo/viewport-break-onblack-*.png` | 黒背景のまま使う版 | 黒ベタ全面 |
| `out/logo/viewport-break-transparent-*.png` | 透過版 | アルファ付き |
| `out/MANIFEST.json` | 全出力のサイズ・バイト数・sha256 | — |

## 設計上の決めごと

**透過版は「暗い面に置く」前提。** master は純黒地にガラスの反射だけが乗った絵で、
黒地 = 何も無い。つまり master の RGB は実質アルファ乗算済みなので、輝度をそのまま
アルファに使い、RGB を割り戻してストレートアルファへ直している。
結果としてガラス板の内側は透明になり、見えるのは縁のハイライトだけになる。
これはガラスとして正しい挙動だが、**白い面に置くとほぼ消える**。
白背景で使う必要がある場合は黒地版を使う。アイコン類が全部黒地なのも同じ理由。

**セーフエリア。** マークは master の中で中心からずれている（bbox が左に 34px・下に 16px）。
派生時は bbox 基準で置き直しているので、四辺の余白が揃う。
角丸マスク・macOS の squircle・PWA maskable の安全円（中央 80% 径）の 3 つとも、
マークが 1px も欠けないことを確認済み（失われる光量 0.00000%）。

**小サイズの輝度。** ガラスの縁は細い高輝度の線なので、sRGB 値のまま平均縮小すると
実際の光量より暗くなり、16px で潰れる。**リニア光で縮小**したうえで、
最大輝度が 250 に届くまで一様ゲイン（16px で約 1.8〜2.1 倍）をかけている。

**16px は「読める」より「見分けがつく」水準。** V と B の字形は 32px 以上でないと読めない。
16px 専用に簡略化したグリフを別に起こすのが本筋で、これは未対応。

## macOS `.icns` の注意

`packaging/build_icns.py` は 16x16 / 32x32 の **1x 枠（`icp4` / `icp5`）を入れていない**。
この 2 つは PNG を入れても macOS 側が 24bit 生データとして読むため、Finder で色ノイズになる
（2026-08-31 に NSWorkspace 実描画で確認。1.0.0 / 1.0.1 の DMG はこの状態で出ている）。
現在は `ic11` / `ic12`（@2x の PNG）だけを置き、1x は macOS に縮小させている。
Retina では 16pt = 32 デバイス px なので `ic11` がそのまま出る。
非 Retina の 1x でだけ 16pt がやや暗くなるのが既知の残課題。
