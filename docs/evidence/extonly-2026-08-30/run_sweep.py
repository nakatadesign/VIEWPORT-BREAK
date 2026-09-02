# -*- coding: utf-8 -*-
"""
VIEWPORT BREAK — 拡張単体（ヘルパー無し）でどこまでウィンドウを縮められるかの実測。

方針:
  * 使い捨て user-data-dir。オーナーの常用 Chrome プロファイルには触れない。
  * native messaging host manifest はこのプロファイルへ *置かない*。
  * AppleScript は一切使わない（オーナーウィンドウ誤爆の経路を最初から作らない）。
  * ウィンドウ寸法の変更は 100% 拡張の service worker 内 chrome.windows.update。
    CDP は「拡張をロードする」「拡張ページの関数を呼ぶ」「結果を読む」だけに使う。
  * screencapture の範囲は計測したウィンドウ矩形ちょうど。画面全体は撮らない。
"""
import base64, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(HERE, "ext")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
PROFILE = os.path.join(HERE, "profile")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9391
X, Y, W0, H0 = 620, 140, 900, 760

log = {"meta": {}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:500], flush=True)

# --- 使い捨てプロファイル ---
shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
assert not os.path.exists(os.path.join(PROFILE, "NativeMessagingHosts")), "native host は置かない"

proc = subprocess.Popen(
    [CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
     "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
     f"--window-size={W0},{H0}", f"--window-position={X},{Y}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
step(action="launch_chrome", pid=proc.pid, profile=PROFILE, port=PORT,
     note="native messaging host manifest を置いていない使い捨てプロファイル")

ver = None
for _ in range(80):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver:
    proc.kill(); sys.exit("chrome did not expose CDP")
log["meta"]["chrome"] = ver.get("Browser")
log["meta"]["user_agent"] = ver.get("User-Agent")
step(action="cdp_ready", browser=ver.get("Browser"))
time.sleep(1.5)

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=60, suppress_origin=True); self.i = 0
    def send(self, method, params=None, sid=None):
        self.i += 1
        msg = {"id": self.i, "method": method, "params": params or {}}
        if sid: msg["sessionId"] = sid
        self.ws.send(json.dumps(msg))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == self.i:
                if "error" in r: raise RuntimeError(f"{method}: {r['error']}")
                return r.get("result", {})

b = C(ver["webSocketDebuggerUrl"])
ext_id = b.send("Extensions.loadUnpacked", {"path": EXT})["id"]
log["meta"]["extension_id"] = ext_id
step(action="load_unpacked", extension_id=ext_id, path=EXT)

PROBE = f"chrome-extension://{ext_id}/probe.html"
t = b.send("Target.createTarget", {"url": PROBE})["targetId"]
sid = b.send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
b.send("Page.enable", {}, sid); b.send("Runtime.enable", {}, sid)
time.sleep(2.0)

def ev(expr, await_promise=True):
    r = b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True,
                                    "awaitPromise": await_promise}, sid)
    if "exceptionDetails" in r:
        raise RuntimeError(json.dumps(r["exceptionDetails"])[:500])
    return r["result"].get("value")

ping = ev("window.vdPing()")
step(action="api_availability", ping=ping)
log["meta"]["api_availability"] = ping

base = ev("window.vdRead()")
step(action="baseline", **base)
log["meta"]["baseline"] = base

def shot(name, rect):
    """計測したウィンドウ矩形ちょうどを撮る。画面全体は撮らない。"""
    l, tp = int(rect["left"]), int(rect["top"])
    w, h = max(int(rect["width"]), 4), max(int(rect["height"]), 4)
    p = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{l},{tp},{w},{h}", p], timeout=40)
    px = None
    if os.path.exists(p):
        s = subprocess.run(["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", p],
                           capture_output=True, text=True).stdout
        px = " ".join(s.split()[-4:])
    return {"file": os.path.relpath(p, HERE), "bytes": os.path.getsize(p) if os.path.exists(p) else 0,
            "png_pixels": px}

def reset():
    ev(f"window.vdStep({{left:{X},top:{Y},width:{W0},height:{H0},state:'normal'}})")
    time.sleep(0.6)

def run(patch, tag, capture=True):
    r = ev(f"window.vdStep({json.dumps(patch)})")
    if capture and r["api"].get("ok"):
        r["shot"] = shot(f"{tag}.png", r["api"]["after"])
    step(action=tag, **r)
    return r

# ---------- 1. 幅スイープ（依頼の N=1,50,200,300,400,500,600） ----------
width_sweep = []
for n in [1, 50, 200, 300, 400, 500, 600]:
    reset()
    r = run({"width": n, "state": "normal"}, f"width-{n:04d}")
    width_sweep.append(r)

# ---------- 1b. 500 前後を 1px 刻みで詰める（下限を数値で確定する） ----------
width_edge = []
reset()
for n in [499, 500, 501, 498, 490]:
    r = run({"width": n, "state": "normal"}, f"edge-w-{n}", capture=False)
    width_edge.append(r)

# ---------- 2. 高さの下限 ----------
height_sweep = []
for n in [1, 50, 100, 200, 300, 400, 600]:
    reset()
    r = run({"height": n, "state": "normal"}, f"height-{n:04d}", capture=(n in (1, 50, 200, 600)))
    height_sweep.append(r)

height_edge = []
reset()
for n in [2, 3, 5, 10, 15, 20, 25, 30]:
    r = run({"height": n, "state": "normal"}, f"edge-h-{n}", capture=False)
    height_edge.append(r)

# ---------- 3. 画面幅を超える拡大 ----------
over = []
reset()
for n in [1900, 1920, 2000, 3000]:
    r = run({"width": n, "state": "normal"}, f"over-{n}", capture=(n == 3000))
    over.append(r)
reset()
over.append(run({"width": 3000, "height": 2000, "state": "normal"}, "over-3000x2000", capture=True))
reset()
over.append(run({"left": 0, "top": 0, "width": 3000, "height": 1000, "state": "normal"}, "over-3000-at-0", capture=True))

# ---------- 4. 参考: state の効き ----------
misc = []
reset()
misc.append(run({"state": "maximized"}, "state-maximized", capture=False))
misc.append(run({"width": 375, "state": "normal"}, "after-max-375", capture=False))
reset()

log["summary"] = {
    "width_sweep": [{"requested": r["requested"], "returned": r["api"].get("returned"),
                     "after": r["api"].get("after"), "page": r["page"], "shot": r.get("shot")}
                    for r in width_sweep],
    "width_edge": [{"requested": r["requested"], "after": r["api"].get("after"), "page": r["page"]} for r in width_edge],
    "height_sweep": [{"requested": r["requested"], "after": r["api"].get("after"), "page": r["page"], "shot": r.get("shot")}
                     for r in height_sweep],
    "height_edge": [{"requested": r["requested"], "after": r["api"].get("after"), "page": r["page"]} for r in height_edge],
    "over_screen": [{"requested": r["requested"], "after": r["api"].get("after"), "page": r["page"], "shot": r.get("shot")}
                    for r in over],
    "misc": [{"requested": r["requested"], "after": r["api"].get("after"), "page": r["page"]} for r in misc],
}

json.dump(log, open(os.path.join(OUT, "sweep.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "sweep.json"))

proc.terminate()
try: proc.wait(20)
except Exception: proc.kill()
time.sleep(1.5)
print("DONE")
