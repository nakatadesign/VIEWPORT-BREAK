# -*- coding: utf-8 -*-
"""文書に載せる実写。撮る直前にページを再描画させ、画面の数字と実測値を一致させる。"""
import http.server, json, os, shutil, socketserver, subprocess, sys, threading, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "ext"); OUT = os.path.join(HERE, "shots"); os.makedirs(OUT, exist_ok=True)
WWW = os.path.join(HERE, "www"); PROFILE = os.path.join(HERE, "profile5")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT, WWWPORT = 9397, 9398
X, Y = 620, 140

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WWW, **k)
    def log_message(self, *a): pass
httpd = socketserver.TCPServer(("127.0.0.1", WWWPORT), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
MURL = f"http://127.0.0.1:{WWWPORT}/m.html"

res = {"meta": {"probe_url": MURL}, "shots": []}
shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    "--window-size=900,760", f"--window-position={X},{Y}", MURL],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(80):
    try: ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: proc.kill(); sys.exit("no cdp")
res["meta"]["chrome"] = ver.get("Browser")
time.sleep(2.5)

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True); self.i = 0
    def send(self, m, p=None, sid=None):
        self.i += 1
        msg = {"id": self.i, "method": m, "params": p or {}}
        if sid: msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.i:
                if "error" in r: raise RuntimeError(f"{m}: {r['error']}")
                return r.get("result", {})

b = C(ver["webSocketDebuggerUrl"])
ext_id = b.send("Extensions.loadUnpacked", {"path": EXT})["id"]
sw_sid = None
for _ in range(20):
    for x in b.send("Target.getTargets")["targetInfos"]:
        if x["type"] == "service_worker" and ext_id in x.get("url", ""):
            sw_sid = b.send("Target.attachToTarget", {"targetId": x["targetId"], "flatten": True})["sessionId"]
            b.send("Runtime.enable", {}, sw_sid); break
    if sw_sid: break
    time.sleep(0.5)

def sw(e):
    r = b.send("Runtime.evaluate", {"expression": e, "returnByValue": True, "awaitPromise": True}, sw_sid)
    if "exceptionDetails" in r: raise RuntimeError(json.dumps(r["exceptionDetails"])[:400])
    return r["result"].get("value")

def page_sid():
    for x in b.send("Target.getTargets")["targetInfos"]:
        if x["type"] == "page" and "127.0.0.1" in x.get("url", ""):
            s = b.send("Target.attachToTarget", {"targetId": x["targetId"], "flatten": True})["sessionId"]
            b.send("Runtime.enable", {}, s); return s
    return None

def capture(name, rect, note, requested, sid):
    b.send("Runtime.evaluate", {"expression": "p()"}, sid)   # 撮る直前に再描画
    time.sleep(0.5)
    m = json.loads(b.send("Runtime.evaluate", {"expression": "JSON.stringify(window.vdM())",
                                               "returnByValue": True}, sid)["result"]["value"])
    l, tp = max(int(rect["left"]), 0), max(int(rect["top"]), 0)
    w, h = max(min(int(rect["width"]), 1920 - l), 4), max(min(int(rect["height"]), 1080 - tp), 4)
    p = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{l},{tp},{w},{h}", p], timeout=40)
    px = subprocess.run(["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                        capture_output=True, text=True).stdout.split()
    e = {"file": name, "note": note, "requested": requested, "window_rect": rect, "page": m,
         "png_pixels": " ".join(px[-4:]) if px else None}
    res["shots"].append(e); print(json.dumps(e, ensure_ascii=False)[:400], flush=True)
    return e

SET = """(async (id, patch) => { const u = await chrome.windows.update(id, patch);
  await new Promise(r=>setTimeout(r,800)); const a = await chrome.windows.get(id);
  return {left:a.left,top:a.top,width:a.width,height:a.height,type:a.type}; })(%s, %s)"""

mid = sw("(async()=>(await chrome.windows.getCurrent()).id)()")
psid = page_sid()

# 1) 通常タブ付き: 900 → 375 要求 → 500 でクランプ
a = sw(SET % (mid, json.dumps({"left": X, "top": Y, "width": 900, "height": 760})))
capture("01-tabbed-900-baseline.png", a, "通常ウィンドウ 基準 900px", 900, psid)
a = sw(SET % (mid, json.dumps({"left": X, "top": Y, "width": 375, "height": 760})))
capture("02-tabbed-request375-actual500.png", a, "通常ウィンドウに 375px を要求 → 500px でクランプ", 375, psid)
a = sw(SET % (mid, json.dumps({"left": X, "top": Y, "width": 1, "height": 760})))
capture("03-tabbed-request1-actual500.png", a, "通常ウィンドウに 1px を要求 → 500px でクランプ", 1, psid)
a = sw(SET % (mid, json.dumps({"left": X, "top": Y, "width": 900, "height": 1})))
capture("04-tabbed-requestH1-actualH375.png", a, "通常ウィンドウに 高さ1px を要求 → 375px でクランプ", 1, psid)

# 2) アクティブタブを popup 化してから縮める
mv = sw("""(async () => {
  const [t] = await chrome.tabs.query({active:true, lastFocusedWindow:true});
  const w = await chrome.windows.create({tabId: t.id, type:'popup', left:620, top:140, width:375, height:760});
  await new Promise(r=>setTimeout(r,1200));
  const a = await chrome.windows.get(w.id);
  return {id:w.id, type:a.type, left:a.left, top:a.top, width:a.width, height:a.height};
})()""")
print("moved:", json.dumps(mv, ensure_ascii=False), flush=True)
res["meta"]["moved_popup_create_result"] = mv
time.sleep(1.0)
psid = page_sid()
pid_ = mv["id"]
for n, name, note in [(375, "05-popup-375.png", "同じタブを popup 型ウィンドウにして 375px"),
                      (320, "06-popup-320.png", "同 popup を 320px"),
                      (86,  "07-popup-86-floor.png", "同 popup の実下限 86px（1px を要求した結果）")]:
    req = 1 if n == 86 else n
    a = sw(SET % (pid_, json.dumps({"left": X, "top": Y, "width": req, "height": 760})))
    capture(name, a, note, req, psid)
a = sw(SET % (pid_, json.dumps({"left": X, "top": Y, "width": 500, "height": 1})))
capture("08-popup-heightfloor-96.png", a, "popup の高さ下限 96px（1px を要求した結果）", 1, psid)

# 3) 画面幅超え 3000px（左端に寄せた場合のみ通る）
a = sw(SET % (pid_, json.dumps({"left": 0, "top": 30, "width": 3000, "height": 700})))
capture("09-popup-3000-onscreen-part.png", a, "3000px 要求が通った状態（画面に映る 1920px 分のみ撮影）", 3000, psid)

json.dump(res, open(os.path.join(OUT, "shots.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "shots.json"))
httpd.shutdown(); proc.terminate()
try: proc.wait(20)
except Exception: proc.kill()
print("DONE")
