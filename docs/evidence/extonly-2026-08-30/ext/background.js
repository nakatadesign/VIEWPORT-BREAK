// 最小テスト拡張の背景 service worker。
// 使うのは chrome.windows.update / chrome.windows.get だけ。
// native messaging も外部通信も一切しない（manifest に permissions キー自体が無い）。
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      if (msg.op === 'ping') {
        sendResponse({
          ok: true,
          hasWindowsApi: typeof chrome.windows !== 'undefined',
          hasWindowsUpdate: typeof chrome.windows?.update === 'function',
          hasNativeMessaging: typeof chrome.runtime?.sendNativeMessage === 'function',
          permissions: chrome.runtime.getManifest().permissions ?? null,
          hostPermissions: chrome.runtime.getManifest().host_permissions ?? null,
        });
        return;
      }
      if (msg.op === 'update') {
        const before = await chrome.windows.get(msg.windowId);
        const updated = await chrome.windows.update(msg.windowId, msg.patch);
        await new Promise((r) => setTimeout(r, 700));
        const after = await chrome.windows.get(msg.windowId);
        sendResponse({
          ok: true,
          before: { left: before.left, top: before.top, width: before.width, height: before.height, state: before.state },
          returned: { left: updated.left, top: updated.top, width: updated.width, height: updated.height, state: updated.state },
          after: { left: after.left, top: after.top, width: after.width, height: after.height, state: after.state },
        });
        return;
      }
      sendResponse({ ok: false, error: 'unknown op' });
    } catch (e) {
      sendResponse({ ok: false, error: (e && e.message) || String(e) });
    }
  })();
  return true;
});
