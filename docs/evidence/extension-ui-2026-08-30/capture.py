import json, os, subprocess, time, base64, shutil, sys, urllib.request
import websocket

SCRATCH = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.expanduser("~/Projects/viewport-deck/extension")
OUT = os.path.join(SCRATCH, "out"); os.makedirs(OUT, exist_ok=True)
PROFILE = os.path.join(SCRATCH, "profile")
PORT = 9351
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

log = {"steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw); print(json.dumps(kw, ensure_ascii=False))

shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    "--window-size=900,900", "--window-position=60,60", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
step(action="launch_chrome", pid=proc.pid, profile=PROFILE, port=PORT)

ver = None
for _ in range(60):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: sys.exit("chrome did not expose CDP")
step(action="cdp_ready", browser=ver.get("Browser"))

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=30, suppress_origin=True); self.i = 0
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
ext = b.send("Extensions.loadUnpacked", {"path": EXT})
ext_id = ext["id"]
step(action="load_unpacked", extension_id=ext_id)

def shot(name, url, dark=False, clicks=(), wait=1.2):
    t = b.send("Target.createTarget", {"url": url})["targetId"]
    sid = b.send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
    b.send("Page.enable", {}, sid); b.send("Runtime.enable", {}, sid)
    if dark: b.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark"}]}, sid)
    time.sleep(wait)
    for js in clicks:
        b.send("Runtime.evaluate", {"expression": js, "awaitPromise": False}, sid); time.sleep(1.6)
    h = b.send("Runtime.evaluate", {"expression": "document.getElementById('app').getBoundingClientRect().height",
                                    "returnByValue": True}, sid)["result"].get("value", 400)
    b.send("Emulation.setDeviceMetricsOverride",
           {"width": 292, "height": int(h) + 2, "deviceScaleFactor": 2, "mobile": False}, sid)
    time.sleep(0.35)
    png = b.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True}, sid)["data"]
    p = os.path.join(OUT, name)
    open(p, "wb").write(base64.b64decode(png))
    text = b.send("Runtime.evaluate", {"expression":
        "JSON.stringify({w:curW.textContent,h:curH.textContent,msg:msg.textContent,"
        "hostEl:!!document.getElementById('host'),btns:[...grid.children].map(b=>b.textContent),"
        "current:[...grid.children].filter(b=>b.classList.contains('is-current')).map(b=>b.textContent),"
        "radius:getComputedStyle(grid.children[0]).borderRadius,"
        "bg:getComputedStyle(grid.children[0]).backgroundColor,"
        "border:getComputedStyle(grid.children[0]).borderColor,"
        "applyBorder:getComputedStyle(document.querySelector('.custom .btn')).border,"
        "applyRadius:getComputedStyle(document.querySelector('.custom .btn')).borderRadius,"
        "fieldBg:getComputedStyle(document.querySelector('.field')).backgroundColor,"
        "caret:getComputedStyle(grid.children[0],'::after').content})",
        "returnByValue": True}, sid)["result"]["value"]
    step(action="shot", file=p, dark=dark, clicks=list(clicks), dom=json.loads(text))
    b.send("Target.closeTarget", {"targetId": t})
    return json.loads(text)

POPUP = f"chrome-extension://{ext_id}/popup.html"
shot("01-rest-light.png", POPUP)
shot("02-dark.png", POPUP, dark=True)
shot("03-click-1024.png", POPUP, clicks=["[...grid.children].find(b=>b.textContent.includes('1024')).click()"])
shot("04-click-375-nohost.png", POPUP, clicks=["[...grid.children].find(b=>b.textContent.trim()==='375').click()"], wait=1.2)
shot("05-custom-900.png", POPUP, clicks=["customW.value=900; customForm.requestSubmit()"])

json.dump(log, open(os.path.join(OUT, "capture.json"), "w"), ensure_ascii=False, indent=2)
proc.terminate()
try: proc.wait(15)
except Exception: proc.kill()
print("DONE")
