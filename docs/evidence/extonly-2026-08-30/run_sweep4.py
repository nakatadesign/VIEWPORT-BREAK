# -*- coding: utf-8 -*-
"""
第 4 パス。製品判断に直結する 2 点だけを実測する。
  * 権限ゼロのまま「今見ているタブ」を popup 型ウィンドウへ移し、375px にできるか。
  * その popup を通常のタブ付きウィンドウへ戻せるか。
"""
import http.server, json, os, shutil, socketserver, subprocess, sys, threading, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "ext"); OUT = os.path.join(HERE, "out4"); os.makedirs(OUT, exist_ok=True)
WWW = os.path.join(HERE, "www"); PROFILE = os.path.join(HERE, "profile4")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT, WWWPORT = 9395, 9396
X, Y = 620, 140

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WWW, **k)
    def log_message(self, *a): pass
httpd = socketserver.TCPServer(("127.0.0.1", WWWPORT), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
MURL = f"http://127.0.0.1:{WWWPORT}/m.html"

log = {"meta": {"probe_url": MURL}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw); print(json.dumps(kw, ensure_ascii=False)[:460], flush=True)

shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    f"--window-size=900,760", f"--window-position={X},{Y}", MURL],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(80):
    try: ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: proc.kill(); sys.exit("no cdp")
log["meta"]["chrome"] = ver.get("Browser"); step(action="cdp_ready", browser=ver.get("Browser"))
time.sleep(2)

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True); self.i = 0
    def send(self, method, params=None, sid=None):
        self.i += 1
        m = {"id": self.i, "method": method, "params": params or {}}
        if sid: m["sessionId"] = sid
        self.ws.send(json.dumps(m))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.i:
                if "error" in r: raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

b = C(ver["webSocketDebuggerUrl"])
ext_id = b.send("Extensions.loadUnpacked", {"path": EXT})["id"]
step(action="load_unpacked", extension_id=ext_id)

# service worker から直接叩く（popup UI からの実行と同じ経路）
sw_sid = None
for _ in range(20):
    for x in b.send("Target.getTargets")["targetInfos"]:
        if x["type"] == "service_worker" and ext_id in x.get("url", ""):
            sw_sid = b.send("Target.attachToTarget", {"targetId": x["targetId"], "flatten": True})["sessionId"]
            b.send("Runtime.enable", {}, sw_sid); break
    if sw_sid: break
    time.sleep(0.5)
step(action="service_worker_attached", ok=bool(sw_sid))

def sw(expr):
    r = b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, sw_sid)
    if "exceptionDetails" in r: raise RuntimeError(json.dumps(r["exceptionDetails"])[:400])
    return r["result"].get("value")

def shot(name, rect):
    l, tp = max(int(rect["left"]), 0), max(int(rect["top"]), 0)
    w, h = max(min(int(rect["width"]), 1920 - l), 4), max(min(int(rect["height"]), 1080 - tp), 4)
    p = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{l},{tp},{w},{h}", p], timeout=40)
    px = subprocess.run(["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                        capture_output=True, text=True).stdout.split()
    return {"file": os.path.relpath(p, HERE), "png_pixels": " ".join(px[-4:]) if px else None}

# ---- 1. 権限ゼロで「アクティブタブ」を popup 化して 375px ----
r1 = sw("""(async () => {
  try {
    const [tab] = await chrome.tabs.query({active: true, lastFocusedWindow: true});
    if (!tab) return {ok:false, error:'no active tab'};
    const w = await chrome.windows.create({tabId: tab.id, type: 'popup',
                                           left: 620, top: 140, width: 375, height: 700, focused: true});
    await new Promise(r => setTimeout(r, 1000));
    const a = await chrome.windows.get(w.id, {populate: true});
    return {ok:true, movedTabId: tab.id, hadUrl: !!tab.url, newWindowId: w.id, type: a.type,
            after: {left:a.left, top:a.top, width:a.width, height:a.height},
            tabCount: (a.tabs||[]).length};
  } catch (e) { return {ok:false, error: e.message}; }
})()""")
step(action="active_tab_to_popup_375", **r1)
if r1.get("ok"):
    time.sleep(0.6)
    r1["shot"] = shot("moved-tab-popup-375.png", r1["after"])
    step(action="shot", **r1["shot"])

# 移した popup の中身を実測
inner = None
for x in b.send("Target.getTargets")["targetInfos"]:
    if x["type"] == "page" and "127.0.0.1" in x.get("url", ""):
        s = b.send("Target.attachToTarget", {"targetId": x["targetId"], "flatten": True})["sessionId"]
        b.send("Runtime.enable", {}, s)
        inner = json.loads(b.send("Runtime.evaluate", {"expression": "JSON.stringify(window.vdM())",
                                                       "returnByValue": True}, s)["result"]["value"])
        break
step(action="moved_popup_viewport", **(inner or {"note": "not found"}))

# さらに縮める
shrink = []
for n in [320, 200, 86]:
    r = sw(f"""(async () => {{
      const w = (await chrome.windows.getAll()).find(x => x.type === 'popup');
      if (!w) return {{ok:false, error:'no popup'}};
      await chrome.windows.update(w.id, {{width: {n}, left: 620, top: 140, height: 700}});
      await new Promise(r => setTimeout(r, 600));
      const a = await chrome.windows.get(w.id);
      return {{ok:true, width: a.width, height: a.height}};
    }})()""")
    step(action=f"shrink_{n}", **r); shrink.append({"requested": n, **r})

# ---- 2. popup を通常のタブ付きウィンドウへ戻せるか ----
r2 = sw("""(async () => {
  try {
    const w = (await chrome.windows.getAll({populate:true})).find(x => x.type === 'popup');
    if (!w) return {ok:false, error:'no popup window'};
    const tabId = w.tabs[0].id;
    const nw = await chrome.windows.create({tabId, type: 'normal', left: 620, top: 140, width: 900, height: 700});
    await new Promise(r => setTimeout(r, 1000));
    const a = await chrome.windows.get(nw.id);
    return {ok:true, type: a.type, after:{left:a.left, top:a.top, width:a.width, height:a.height}};
  } catch (e) { return {ok:false, error: e.message}; }
})()""")
step(action="popup_back_to_normal", **r2)
if r2.get("ok"):
    r2["shot"] = shot("restored-normal-900.png", r2["after"])
    step(action="shot", **r2["shot"])

# ---- 3. 参考: 権限ゼロで使える window/tab API の可否 ----
caps = sw("""(async () => {
  const out = {};
  const t = async (k, f) => { try { out[k] = {ok:true, v: await f()}; } catch(e){ out[k] = {ok:false, error:e.message}; } };
  await t('windows.getAll', async () => (await chrome.windows.getAll()).length);
  await t('windows.create_popup', async () => {
      const w = await chrome.windows.create({url:'about:blank', type:'popup', width:375, height:400, left:0, top:600});
      const id = w.id; await chrome.windows.remove(id); return 'created+removed'; });
  await t('tabs.query_url', async () => { const [x] = await chrome.tabs.query({active:true, lastFocusedWindow:true});
      return {hasUrl: !!x?.url, hasTitle: !!x?.title, hasPendingUrl: !!x?.pendingUrl}; });
  await t('tabs.captureVisibleTab', async () => await chrome.tabs.captureVisibleTab());
  await t('scripting', async () => typeof chrome.scripting);
  await t('storage', async () => typeof chrome.storage);
  await t('sendNativeMessage', async () => typeof chrome.runtime.sendNativeMessage);
  await t('debugger', async () => typeof chrome.debugger);
  await t('system.display', async () => typeof chrome.system?.display);
  return out;
})()""")
step(action="zero_permission_capabilities", caps=caps)

log["summary"] = {"active_tab_to_popup": r1, "moved_popup_viewport": inner, "shrink": shrink,
                  "popup_back_to_normal": r2, "zero_permission_capabilities": caps}
json.dump(log, open(os.path.join(OUT, "sweep4.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "sweep4.json"))
httpd.shutdown(); proc.terminate()
try: proc.wait(20)
except Exception: proc.kill()
print("DONE")
