# -*- coding: utf-8 -*-
"""
第 3 パス。
  * popup 型ウィンドウの実下限を 1px 刻みで確定する。
  * 実際の Web ページ（localhost の HTTP ページ）を popup に読み込み、
    アドレスバーの有無・innerWidth を実測する。extension ページだけで判定しない。
  * 既存タブを popup 型ウィンドウへ移せるか（chrome.windows.create({tabId})）を確認する。
AppleScript・native host は一切使わない。HTTP サーバは 127.0.0.1 のみに bind する。
"""
import http.server, json, os, shutil, socketserver, subprocess, sys, threading, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "ext")
OUT = os.path.join(HERE, "out3"); os.makedirs(OUT, exist_ok=True)
WWW = os.path.join(HERE, "www"); os.makedirs(WWW, exist_ok=True)
PROFILE = os.path.join(HERE, "profile3")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT, WWWPORT = 9393, 9394
X, Y, W0, H0 = 620, 140, 900, 760

open(os.path.join(WWW, "m.html"), "w").write("""<!doctype html><meta charset="utf-8"><title>viewport probe</title>
<style>html,body{margin:0;font:13px/1.4 -apple-system,system-ui,sans-serif;background:#0f1216;color:#e9eef4}
#b{padding:10px}#w{font-size:30px;font-weight:700;letter-spacing:-.02em}
.k{color:#8b98a6;font-size:11px}.bar{height:6px;background:#3b82f6;margin-top:8px}</style>
<div id="b"><div id="w">-</div><div class="k" id="d">-</div><div class="bar"></div></div>
<script>
function p(){document.getElementById('w').textContent=outerWidth+' x '+outerHeight;
document.getElementById('d').textContent='inner '+innerWidth+' x '+innerHeight+' / dpr '+devicePixelRatio;}
addEventListener('resize',p);p();
window.vdM=()=>({outerWidth,innerWidth,outerHeight,innerHeight,devicePixelRatio,href:location.href});
</script>""")

class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=WWW, **k)
    def log_message(self, *a): pass
httpd = socketserver.TCPServer(("127.0.0.1", WWWPORT), H)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
MURL = f"http://127.0.0.1:{WWWPORT}/m.html"

log = {"meta": {"probe_url": MURL}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw); print(json.dumps(kw, ensure_ascii=False)[:420], flush=True)

shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
proc = subprocess.Popen(
    [CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
     "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
     f"--window-size={W0},{H0}", f"--window-position={X},{Y}", MURL],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(80):
    try: ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: proc.kill(); sys.exit("no cdp")
log["meta"]["chrome"] = ver.get("Browser")
step(action="cdp_ready", browser=ver.get("Browser"))
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

ctl = b.send("Target.createTarget", {"url": f"chrome-extension://{ext_id}/probe.html"})["targetId"]
csid = b.send("Target.attachToTarget", {"targetId": ctl, "flatten": True})["sessionId"]
b.send("Runtime.enable", {}, csid); time.sleep(1.5)

def ctl_ev(expr):
    r = b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, csid)
    if "exceptionDetails" in r: raise RuntimeError(json.dumps(r["exceptionDetails"])[:400])
    return r["result"].get("value")

def attach_url(substr, exclude=()):
    for x in b.send("Target.getTargets")["targetInfos"]:
        if x["type"] == "page" and substr in x.get("url", "") and x["targetId"] not in exclude:
            s = b.send("Target.attachToTarget", {"targetId": x["targetId"], "flatten": True})["sessionId"]
            b.send("Runtime.enable", {}, s)
            return x["targetId"], s
    return None, None

def measure(s):
    v = b.send("Runtime.evaluate", {"expression": "JSON.stringify(window.vdM())", "returnByValue": True}, s)
    return json.loads(v["result"]["value"])

def shot(name, rect):
    l, tp = max(int(rect["left"]), 0), max(int(rect["top"]), 0)
    w, h = max(min(int(rect["width"]), 1920 - l), 4), max(min(int(rect["height"]), 1080 - tp), 4)
    p = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{l},{tp},{w},{h}", p], timeout=40)
    px = subprocess.run(["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                        capture_output=True, text=True).stdout.split()
    return {"file": os.path.relpath(p, HERE), "png_pixels": " ".join(px[-4:]) if px else None}

# ---- 0. 通常タブ付きウィンドウ + 実 HTTP ページの基準値 ----
tid, tsid = attach_url("127.0.0.1")
SET = """(async (id, patch) => { try {
  const u = await chrome.windows.update(id, patch);
  await new Promise(r => setTimeout(r, 700));
  const a = await chrome.windows.get(id);
  return {ok:true, after:{left:a.left,top:a.top,width:a.width,height:a.height,state:a.state}};
} catch(e){ return {ok:false, error:e.message}; } })(%s, %s)"""
main_id = ctl_ev("(async()=>(await chrome.windows.getCurrent()).id)()")
r = ctl_ev(SET % (main_id, json.dumps({"left": X, "top": Y, "width": 375, "height": 700})))
time.sleep(0.6)
tabbed_375 = {"api": r, "page": measure(tsid) if tsid else None}
tabbed_375["shot"] = shot("tabbed-request375.png", r["after"])
step(action="tabbed_window_request_375", **tabbed_375)

# ---- 1. popup 型を作り、実 HTTP ページで幅を掃く ----
pop = ctl_ev(f"""(async () => {{
  const w = await chrome.windows.create({{url: {json.dumps(MURL)}, type: 'popup',
    left: {X}, top: {Y}, width: 900, height: 700, focused: true}});
  return {{id: w.id, type: w.type, width: w.width, height: w.height}};
}})()""")
step(action="popup_created", **pop)
time.sleep(2.0)
ptid, psid = attach_url("127.0.0.1", exclude=(tid,))
step(action="popup_target", found=bool(psid))

popup_w = []
for n in [1, 50, 80, 84, 85, 86, 87, 88, 90, 100, 200, 300, 320, 375, 390, 414, 430, 500, 600]:
    r = ctl_ev(SET % (pop["id"], json.dumps({"left": X, "top": Y, "width": n, "height": 700})))
    time.sleep(0.35)
    m = measure(psid) if psid else None
    e = {"requested": n, "ok": r.get("ok"), "actual": (r.get("after") or {}).get("width"),
         "outerWidth": (m or {}).get("outerWidth"), "innerWidth": (m or {}).get("innerWidth"),
         "error": r.get("error")}
    if n in (1, 320, 375, 430):
        e["shot"] = shot(f"popup-http-{n:04d}.png", r["after"])
    popup_w.append(e); step(action=f"popup_w_{n}", **e)

popup_h = []
for n in [1, 50, 90, 94, 95, 96, 97, 100, 200, 375, 400, 700]:
    r = ctl_ev(SET % (pop["id"], json.dumps({"left": X, "top": Y, "width": 375, "height": n})))
    time.sleep(0.35)
    m = measure(psid) if psid else None
    e = {"requested": n, "ok": r.get("ok"), "actual": (r.get("after") or {}).get("height"),
         "outerHeight": (m or {}).get("outerHeight"), "innerHeight": (m or {}).get("innerHeight"),
         "error": r.get("error")}
    if n in (1, 96):
        e["shot"] = shot(f"popup-http-h{n:04d}.png", r["after"])
    popup_h.append(e); step(action=f"popup_h_{n}", **e)

# popup で画面幅超え
popup_big = []
for patch in [{"left": 0, "top": 30, "width": 3000, "height": 800},
              {"left": 0, "top": 30, "width": 3840, "height": 800},
              {"left": 0, "top": 30, "width": 3841, "height": 800}]:
    r = ctl_ev(SET % (pop["id"], json.dumps(patch)))
    time.sleep(0.35)
    m = measure(psid) if psid else None
    e = {"requested": patch, "ok": r.get("ok"), "after": r.get("after"),
         "outerWidth": (m or {}).get("outerWidth"), "error": r.get("error")}
    popup_big.append(e); step(action="popup_big", **e)

# 375 に戻して最終実写
r = ctl_ev(SET % (pop["id"], json.dumps({"left": X, "top": Y, "width": 375, "height": 700})))
time.sleep(0.8)
final = {"api": r, "page": measure(psid) if psid else None, "shot": shot("popup-http-375-final.png", r["after"])}
step(action="popup_375_final", **final)

# ---- 2. 既存タブを popup 型ウィンドウへ移せるか ----
move = ctl_ev(f"""(async () => {{
  try {{
    const tabs = await chrome.tabs.query({{}});
    const t = tabs.find(x => x.url && x.url.startsWith('http://127.0.0.1'));
    if (!t) return {{ok:false, error:'target tab not found', tabCount: tabs.length,
                     note:'chrome.tabs.query は tabs 権限が無いと url を返さない'}};
    const w = await chrome.windows.create({{tabId: t.id, type: 'popup', left: 620, top: 140, width: 375, height: 700}});
    await new Promise(r => setTimeout(r, 800));
    const a = await chrome.windows.get(w.id);
    return {{ok:true, type: w.type, after:{{left:a.left,top:a.top,width:a.width,height:a.height}}}};
  }} catch(e) {{ return {{ok:false, error: e.message}}; }}
}})()""")
step(action="move_tab_into_popup", **move)
if move.get("ok"):
    move["shot"] = shot("moved-tab-popup-375.png", move["after"])
    step(action="move_tab_shot", **move["shot"])

# ---- 3. tabs 権限なしで chrome.tabs.query が何を返すか ----
tabsinfo = ctl_ev("""(async () => {
  const t = await chrome.tabs.query({});
  return {count: t.length, sample: t.slice(0,3).map(x => ({id:x.id, hasUrl: !!x.url, hasTitle: !!x.title, windowId: x.windowId}))};
})()""")
step(action="tabs_query_without_permission", **tabsinfo)

log["summary"] = {"tabbed_375": tabbed_375, "popup_created": pop, "popup_width": popup_w,
                  "popup_height": popup_h, "popup_big": popup_big, "popup_375_final": final,
                  "move_tab_into_popup": move, "tabs_query_without_permission": tabsinfo}
json.dump(log, open(os.path.join(OUT, "sweep3.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "sweep3.json"))
httpd.shutdown()
proc.terminate()
try: proc.wait(20)
except Exception: proc.kill()
print("DONE")
