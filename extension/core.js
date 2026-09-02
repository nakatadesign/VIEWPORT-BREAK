// VIEWPORT BREAK — 拡張とバックグラウンドで共有する中核ロジック。
//
// 背景（docs/WINDOW_FLOOR_2026-08-30.md）:
//   通常のタブ付き Chrome ウィンドウには幅 500 DIP の下限がある。
//   chrome.windows.update は Widget::SetBounds を通るためこの下限でクランプする。
//   AppleScript の `set bounds` だけが NSWindow へ直接届き、下限を貫通する。
//   よって 500px 未満へは native messaging host 経由でしか到達できない。

export const HOST_NAME = 'com.nanago.viewport_deck';

// 幅 500 未満は拡張 API では到達不能。UI 側でバッジを出すために使う。
export const API_FLOOR = 500;

// 並びは狭い順に 12 個ちょうど（3 列 × 4 行）。刻みの根拠は
// docs/PRESET_WIDTHS_2026-08-30.md（StatCounter 日本のモバイル解像度シェア 2026-07 と
// 各機種の CSS viewport 実値）。3px 差など「同じレイアウトにしかならない幅」は代表 1 つに
// 寄せ、レイアウトが実際に変わる刻みだけを残している。
// 320 は実機シェアではなく「レスポンシブ設計の下限」として先頭に置く。別枠の
// 最小幅チェックボタンは、320 が通常プリセットに入って役割が重複したため撤去した。
export const PRESETS = [
  { w: 320,  label: '320',  note: 'iPhone SE(1st)/5s の論理幅。レスポンシブ設計の下限として押さえる幅' },
  { w: 360,  label: '360',  note: 'Android で最多の論理幅（Galaxy S 系 360×780 ほか）' },
  { w: 375,  label: '375',  note: 'iPhone SE / 8 / X / 13 mini — 日本のモバイル約 20%' },
  { w: 390,  label: '390',  note: 'iPhone 12–14 — 日本 14.0%' },
  { w: 414,  label: '414',  note: 'iPhone XR / 11 / Plus 系 — 日本の最多 23.4%。Android の 412 もこの帯' },
  { w: 430,  label: '430',  note: 'iPhone 15/16 Plus・Pro Max（440 の 17 Pro Max もこの帯）' },
  { w: 640,  label: '640',  note: 'Tailwind sm の境界。実機ではなくブレークポイントの確認用' },
  { w: 768,  label: '768',  note: 'iPad 縦 / md ブレークポイント' },
  { w: 1024, label: '1024', note: 'iPad 横 / lg' },
  { w: 1280, label: '1280', note: 'ノート / xl' },
  { w: 1440, label: '1440', note: 'デスクトップ' },
  { w: 1920, label: '1920', note: 'FHD' },
];

/** native host へ 1 往復。host 未導入なら {ok:false, unavailable:true} を返す。 */
export async function callHost(payload) {
  try {
    const res = await chrome.runtime.sendNativeMessage(HOST_NAME, payload);
    if (!res || typeof res !== 'object') {
      return { ok: false, error: 'host から不正な応答' };
    }
    return res;
  } catch (e) {
    const msg = (e && e.message) || String(e);
    // host manifest 未設置 / 実行不可のときはここに来る。
    return { ok: false, unavailable: true, error: msg };
  }
}

/** 現在のウィンドウを取得する。最大化・全画面なら normal に戻してから読み直す。 */
export async function getTargetWindow() {
  let win = await chrome.windows.getCurrent();
  if (win.state && win.state !== 'normal') {
    await chrome.windows.update(win.id, { state: 'normal' });
    win = await chrome.windows.get(win.id);
  }
  return win;
}

/**
 * ウィンドウ幅を targetWidth にする。高さは変えない。
 * 戻り値 { ok, width, path, clamped, error }
 *   path: 'host'（AppleScript 経由）| 'api'（chrome.windows.update フォールバック）
 *   clamped: 要求幅に到達しなかった場合 true
 */
export async function setWidth(targetWidth) {
  const win = await getTargetWindow();

  const res = await callHost({
    cmd: 'set',
    width: targetWidth,
    match: { left: win.left, top: win.top, width: win.width, height: win.height },
  });

  if (res.ok) {
    const actual = res.bounds.width;
    return {
      ok: true,
      width: actual,
      height: res.bounds.height,
      path: 'host',
      clamped: actual !== targetWidth,
      requested: targetWidth,
    };
  }

  // ---- フォールバック: 拡張 API。500px 未満には到達できない。 ----
  await chrome.windows.update(win.id, { width: targetWidth, state: 'normal' });
  const after = await chrome.windows.get(win.id);
  return {
    ok: true,
    width: after.width,
    height: after.height,
    path: 'api',
    clamped: after.width !== targetWidth,
    requested: targetWidth,
    hostError: res.error,
    hostUnavailable: !!res.unavailable,
  };
}
