// 計測面。CDP からは window.vdStep() / window.vdRead() だけを叩く。
// ウィンドウ寸法の変更は必ず background service worker の chrome.windows.update を経由する。
let WID = null;

async function ensureWindowId() {
  if (WID === null) {
    const w = await chrome.windows.getCurrent();
    WID = w.id;
  }
  return WID;
}

function readPage() {
  return {
    outerWidth: window.outerWidth,
    innerWidth: window.innerWidth,
    outerHeight: window.outerHeight,
    innerHeight: window.innerHeight,
    devicePixelRatio: window.devicePixelRatio,
    screenWidth: window.screen.width,
    screenHeight: window.screen.height,
    availWidth: window.screen.availWidth,
    availHeight: window.screen.availHeight,
  };
}

function paint(p) {
  document.getElementById('w').textContent = `${p.outerWidth} × ${p.outerHeight}`;
  document.getElementById('d').textContent =
    `inner ${p.innerWidth} × ${p.innerHeight} / dpr ${p.devicePixelRatio} / avail ${p.availWidth}×${p.availHeight}`;
}

window.vdRead = async () => {
  await ensureWindowId();
  const p = readPage();
  paint(p);
  return { windowId: WID, page: p };
};

window.vdPing = () => chrome.runtime.sendMessage({ op: 'ping' });

window.vdStep = async (patch) => {
  const windowId = await ensureWindowId();
  const api = await chrome.runtime.sendMessage({ op: 'update', windowId, patch });
  await new Promise((r) => setTimeout(r, 500));
  const p = readPage();
  paint(p);
  return { requested: patch, api, page: p };
};

window.vdRead();
