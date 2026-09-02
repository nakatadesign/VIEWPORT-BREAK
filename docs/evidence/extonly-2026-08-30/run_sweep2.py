# -*- coding: utf-8 -*-
"""
第 2 パス。第 1 パスで出た境界を 1px 刻みで確定し、
さらに「拡張単体で 500 DIP 下限を回避できる唯一の経路」候補である
chrome.windows.create({type:'popup'}) の実下限を測る。
第 1 パスと同じく AppleScript・native host は一切使わない。
"""
import json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "ext")
OUT = os.path.join(HERE, "out2"); os.makedirs(OUT, exist_ok=True)
PROFILE = os.path.join(HERE, "profile2")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9392
X, Y, W0, H0 = 620, 140, 900, 760

log = {"meta": {}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:420], flush=True)

shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
proc = subprocess.Popen(
    [CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
     "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
     f"--window-size={W0},{H0}", f"--window-position={X},{Y}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(80):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver:
    proc.kill(); sys.exit("no cdp")
log["meta"]["chrome"] = ver.get("Browser")
step(action="cdp_ready", browser=ver.get("Browser"), pid=proc.pid)
time.sleep(1.5)

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
log["meta"]["extension_id"] = ext_id
step(action="load_unpacked", extension_id=ext_id)

t = b.send("Target.createTarget", {"url": f"chrome-extension://{ext_id}/probe.html"})["targetId"]
sid = b.send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
b.send("Page.enable", {}, sid); b.send("Runtime.enable", {}, sid)
time.sleep(2.0)

def ev(expr):
    r = b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, sid)
    if "exceptionDetails" in r: raise RuntimeError(json.dumps(r["exceptionDetails"])[:400])
    return r["result"].get("value")

def reset():
    ev(f"window.vdStep({{left:{X},top:{Y},width:{W0},height:{H0},state:'normal'}})"); time.sleep(0.5)

def run(patch, tag):
    r = ev(f"window.vdStep({json.dumps(patch)})")
    step(action=tag, requested=patch, after=r["api"].get("after"), error=r["api"].get("error"),
         page={k: r["page"][k] for k in ("outerWidth", "innerWidth", "outerHeight", "innerHeight")})
    return r

def shot(name, rect, screen_w=1920, screen_h=1080):
    l, tp = max(int(rect["left"]), 0), max(int(rect["top"]), 0)
    w = max(min(int(rect["width"]), screen_w - l), 4)
    h = max(min(int(rect["height"]), screen_h - tp), 4)
    p = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{l},{tp},{w},{h}", p], timeout=40)
    px = subprocess.run(["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                        capture_output=True, text=True).stdout.split()
    return {"file": os.path.relpath(p, HERE), "png_pixels": " ".join(px[-4:]) if px else None,
            "captured_rect": {"left": l, "top": tp, "width": w, "height": h}}

# ---- A. 高さ下限を 1px 刻みで確定 ----
h_edge = []
for n in [330, 350, 360, 370, 372, 373, 374, 375, 376, 380, 390]:
    reset(); r = run({"height": n, "state": "normal"}, f"h-{n}")
    h_edge.append({"requested": n, "actual": r["api"]["after"]["height"] if r["api"].get("ok") else None,
                   "outerHeight": r["page"]["outerHeight"], "innerHeight": r["page"]["innerHeight"]})

# ---- B. 幅下限を 1px 刻みで再確認（両側） ----
w_edge = []
for n in [495, 496, 497, 498, 499, 500, 501, 502, 505]:
    reset(); r = run({"width": n, "state": "normal"}, f"w-{n}")
    w_edge.append({"requested": n, "actual": r["api"]["after"]["width"] if r["api"].get("ok") else None,
                   "outerWidth": r["page"]["outerWidth"], "innerWidth": r["page"]["innerWidth"]})

# ---- C. 高さ・幅の上限（画面超え） ----
big = []
reset()
for patch, tag in [({"left": 0, "top": 30, "height": 1200}, "big-h-1200"),
                   ({"left": 0, "top": 30, "height": 2000}, "big-h-2000"),
                   ({"left": 0, "top": 30, "width": 3000, "height": 800}, "big-w-3000"),
                   ({"left": 0, "top": 30, "width": 3840, "height": 800}, "big-w-3840"),
                   ({"left": 0, "top": 30, "width": 3841, "height": 800}, "big-w-3841"),
                   ({"left": 0, "top": 30, "width": 5000, "height": 800}, "big-w-5000"),
                   ({"left": 620, "top": 140, "width": 3000, "height": 800}, "big-w-3000-off")]:
    r = run(patch, tag)
    big.append({"requested": patch, "ok": r["api"].get("ok"), "after": r["api"].get("after"),
                "error": r["api"].get("error"),
                "page": {k: r["page"][k] for k in ("outerWidth", "innerWidth", "outerHeight", "innerHeight")}})
    reset()

# ---- D. popup 型ウィンドウ（拡張単体で 500 下限を回避できるか） ----
POPUP_JS = """(async () => {
  const created = await chrome.windows.create({
    url: chrome.runtime.getURL('probe.html'),
    type: 'popup', left: 620, top: 140, width: 900, height: 700, focused: true
  });
  return { id: created.id, type: created.type,
           bounds: {left: created.left, top: created.top, width: created.width, height: created.height} };
})()"""
pop = ev(POPUP_JS)
step(action="popup_created", **pop)
PW = pop["id"]

POP_SET = """(async (id, patch) => {
  try {
    const u = await chrome.windows.update(id, patch);
    await new Promise(r => setTimeout(r, 700));
    const a = await chrome.windows.get(id);
    return { ok: true, after: {left: a.left, top: a.top, width: a.width, height: a.height, state: a.state} };
  } catch (e) { return { ok: false, error: e.message }; }
})(%d, %s)"""

popup_sweep = []
for n in [1, 50, 100, 200, 300, 375, 390, 400, 500, 600]:
    r = ev(POP_SET % (PW, json.dumps({"width": n, "left": 620, "top": 140, "height": 700})))
    step(action=f"popup-w-{n}", **r)
    entry = {"requested": n, "ok": r.get("ok"), "after": r.get("after"), "error": r.get("error")}
    if r.get("ok") and n in (1, 50, 200, 375, 500):
        entry["shot"] = shot(f"popup-{n:04d}.png", r["after"])
    popup_sweep.append(entry)

popup_h = []
for n in [1, 50, 100, 200, 375, 400]:
    r = ev(POP_SET % (PW, json.dumps({"height": n, "left": 620, "top": 140, "width": 500})))
    step(action=f"popup-h-{n}", **r)
    popup_h.append({"requested": n, "ok": r.get("ok"), "after": r.get("after"), "error": r.get("error")})

# popup 内の実 viewport を読む（別 target）
targets = b.send("Target.getTargets")["targetInfos"]
ptgt = [x for x in targets if x["type"] == "page" and x["targetId"] != t and "probe.html" in x.get("url", "")]
popup_viewport = None
if ptgt:
    psid = b.send("Target.attachToTarget", {"targetId": ptgt[-1]["targetId"], "flatten": True})["sessionId"]
    b.send("Runtime.enable", {}, psid)
    ev2 = b.send("Runtime.evaluate", {"expression": "JSON.stringify({o:outerWidth,i:innerWidth,oh:outerHeight,ih:innerHeight})",
                                      "returnByValue": True}, psid)["result"]["value"]
    popup_viewport = json.loads(ev2)
step(action="popup_viewport", **(popup_viewport or {"note": "popup target not found"}))

# popup を 375 に戻して実写
r = ev(POP_SET % (PW, json.dumps({"width": 375, "left": 620, "top": 140, "height": 700})))
if r.get("ok"):
    step(action="popup_375_final", shot=shot("popup-375-final.png", r["after"]), after=r["after"])

# ---- E. type:'popup' の manifest 権限要件を確認（permissions 無しで作れたか） ----
perm = ev("window.vdPing()")
step(action="permissions_recheck", **perm)

log["summary"] = {"height_edge": h_edge, "width_edge": w_edge, "big": big,
                  "popup_created": pop, "popup_width_sweep": popup_sweep,
                  "popup_height_sweep": popup_h, "popup_viewport": popup_viewport,
                  "permissions": perm}
json.dump(log, open(os.path.join(OUT, "sweep2.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "sweep2.json"))
proc.terminate()
try: proc.wait(20)
except Exception: proc.kill()
print("DONE")
