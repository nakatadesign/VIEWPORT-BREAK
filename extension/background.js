// キーボードショートカット（manifest の commands）を処理する。
// popup はウィンドウのリサイズで閉じることがあるため、連続切り替えはこちらが快適。
import { setWidth } from './core.js';

const DEFAULT_TITLE = 'VIEWPORT BREAK — ウィンドウ幅を切り替える';

async function showFailure(message) {
  await Promise.all([
    chrome.action.setBadgeText({ text: '!' }),
    chrome.action.setBadgeBackgroundColor({ color: '#B42318' }),
    chrome.action.setTitle({ title: `VIEWPORT BREAK — ${message}` }),
  ]);
}

async function clearFailure() {
  await Promise.all([
    chrome.action.setBadgeText({ text: '' }),
    chrome.action.setTitle({ title: DEFAULT_TITLE }),
  ]);
}

async function reportFailure(message) {
  try {
    await showFailure(message);
  } catch (e) {
    console.error('[viewport-deck] 失敗バッジを更新できなかった', e);
  }
}

chrome.commands.onCommand.addListener(async (cmd) => {
  const m = /^width-(\d+)$/.exec(cmd);
  if (!m) return;
  const want = Number(m[1]);
  try {
    const r = await setWidth(want);
    if (r.clamped) {
      const message = `${want}px に届かず ${r.width}px で停止（${r.path}）`;
      await reportFailure(message);
      console.warn(`[viewport-deck] ${message}`);
    } else {
      await clearFailure();
    }
  } catch (e) {
    await reportFailure(`失敗: ${(e && e.message) || String(e)}`);
    console.error('[viewport-deck]', e);
  }
});
