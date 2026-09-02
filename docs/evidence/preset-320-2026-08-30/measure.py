# -*- coding: utf-8 -*-
"""
viewport-deck プリセット改訂 v1.3.0 の実証スクリプト。

2 つのことを 1 回の使い捨て Chrome でまとめて確認する。
  A. popup を実描画し、プリセット 12 個 / 最小幅チェック撤去 / 3 列 4 行を DOM で読む。
  B. 幅の「実際の下限」を、AppleScript 経路と拡張 API 経路の両方で下から掃く。

安全策: AppleScript は最後に起動した Chrome インスタンスを掴む（probe_instance.sh で確認）。
それでもオーナーの常用ウィンドウへ誤爆しないよう、起動直後に取得した window id 以外へは
一切 set bounds しない。id が一覧から消えたらその手順を skip する。
"""
import base64, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXT = os.path.join(REPO, "extension")
HOST = os.path.join(EXT, "host", "viewport_deck_host.py")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/c9e5f2cb-c90f-4d68-b0a4-9d54f0ca1736/scratchpad/vd-measure"
PROFILE = os.path.join(SCRATCH, "profile")
PORT = 9371
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAUNCH_W, LAUNCH_H, LAUNCH_X, LAUNCH_Y = 901, 901, 700, 120

log = {"meta": {}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:400])

def osa(script):
    p = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True, timeout=20)
    if p.returncode != 0:
        raise RuntimeError("osascript failed: " + (p.stderr or "").strip())
    return (p.stdout or "").strip()

def as_windows():
    """host と同じ AppleScript で Chrome の全ウィンドウを読む。"""
    out = subprocess.run([sys.executable if False else "/usr/bin/python3", HOST, "--list", "--json"],
                         capture_output=True, text=True, timeout=30).stdout
    return json.loads(out).get("windows", [])

# ---------------- 使い捨て Chrome 起動 ----------------
shutil.rmtree(SCRATCH, ignore_errors=True); os.makedirs(PROFILE)
# native messaging host をこの使い捨てプロファイルにも登録する（既定プロファイル側は触らない）
nm_dir = os.path.join(PROFILE, "NativeMessagingHosts"); os.makedirs(nm_dir, exist_ok=True)
shutil.copy(os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.nanago.viewport_deck.json"),
            os.path.join(nm_dir, "com.nanago.viewport_deck.json"))

before = as_windows()
step(action="owner_windows_before", windows=before)
OWNER_IDS = {w["id"] for w in before}

proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    f"--window-size={LAUNCH_W},{LAUNCH_H}", f"--window-position={LAUNCH_X},{LAUNCH_Y}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
step(action="launch_chrome", pid=proc.pid, profile=PROFILE, port=PORT)

ver = None
for _ in range(60):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: sys.exit("chrome did not expose CDP")
log["meta"]["chrome"] = ver.get("Browser")
step(action="cdp_ready", browser=ver.get("Browser"))
time.sleep(1.5)

# 使い捨てウィンドウの AppleScript id を確定する
wins = as_windows()
cands = [w for w in wins if w["id"] not in OWNER_IDS]
step(action="applescript_windows_after_launch", windows=wins, candidates=cands)
TARGET = None
for w in cands:
    if abs(w["width"] - LAUNCH_W) <= 4 and abs(w["left"] - LAUNCH_X) <= 4:
        TARGET = w; break
if TARGET is None:
    step(action="target_window_not_identified", note="AppleScript 経路の実測は skip する")
log["meta"]["target_window"] = TARGET

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=40, suppress_origin=True); self.i = 0
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
step(action="load_unpacked", extension_id=ext_id)
POPUP = f"chrome-extension://{ext_id}/popup.html"

DOM_JS = """JSON.stringify({
  w: curW.textContent, h: curH.textContent, msg: msg.textContent,
  btnCount: grid.children.length,
  btns: [...grid.children].map(b => b.textContent.trim()),
  titles: [...grid.children].map(b => b.title),
  stressEls: document.querySelectorAll('.is-stress').length,
  pseudoBefore: [...grid.children].map(b => getComputedStyle(b, '::before').content).filter(c => c && c !== 'none'),
  bodyHasMinCheckText: document.body.innerText.includes('最小幅チェック'),
  gridCols: getComputedStyle(grid).gridTemplateColumns,
  gridRows: getComputedStyle(grid).gridTemplateRows,
  rowCount: getComputedStyle(grid).gridTemplateRows.split(' ').length,
  fullWidthBtns: [...grid.children].filter(b => Math.round(b.getBoundingClientRect().width) > 200).map(b => b.textContent.trim()),
  current: [...grid.children].filter(b => b.classList.contains('is-current')).map(b => b.textContent.trim()),
  customMin: customW.getAttribute('min'), customMax: customW.getAttribute('max'),
  appH: Math.ceil(document.getElementById('app').getBoundingClientRect().height)
})"""

def open_popup(dark=False):
    t = b.send("Target.createTarget", {"url": POPUP})["targetId"]
    sid = b.send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
    b.send("Page.enable", {}, sid); b.send("Runtime.enable", {}, sid)
    if dark:
        b.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "dark"}]}, sid)
    time.sleep(1.4)
    return t, sid

def dom(sid):
    return json.loads(b.send("Runtime.evaluate", {"expression": DOM_JS, "returnByValue": True}, sid)["result"]["value"])

def shot(sid, name, h):
    b.send("Emulation.setDeviceMetricsOverride", {"width": 292, "height": int(h) + 2,
                                                  "deviceScaleFactor": 2, "mobile": False}, sid)
    time.sleep(0.4)
    png = b.send("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True}, sid)["data"]
    p = os.path.join(OUT, name); open(p, "wb").write(base64.b64decode(png))
    b.send("Emulation.clearDeviceMetricsOverride", {}, sid)
    return p

def inner_width(sid):
    return b.send("Runtime.evaluate", {"expression": "window.outerWidth", "returnByValue": True}, sid)["result"]["value"]

# ---------------- A. popup 実描画 ----------------
t, sid = open_popup()
d = dom(sid)
step(action="popup_rest_light", dom=d, file=shot(sid, "01-rest-light.png", d["appH"]))
b.send("Target.closeTarget", {"targetId": t})

t, sid = open_popup(dark=True)
d = dom(sid)
step(action="popup_dark", dom=d, file=shot(sid, "02-dark.png", d["appH"]))
b.send("Target.closeTarget", {"targetId": t})

# 320 プリセットを実クリック（host 経路が生きていれば本当に 320 になる）
t, sid = open_popup()
b.send("Runtime.evaluate", {"expression":
    "[...grid.children].find(b=>b.textContent.trim()==='320').click()"}, sid)
time.sleep(2.5)
d = dom(sid)
d["outerWidth_after_click"] = inner_width(sid)
d["applescript_after_click"] = [w for w in as_windows() if TARGET and w["id"] == TARGET["id"]]
step(action="popup_click_320", dom=d, file=shot(sid, "03-click-320.png", d["appH"]))
b.send("Target.closeTarget", {"targetId": t})

# 任意幅の下限バリデーション境界（49 は弾かれる / 50 は通る）
t, sid = open_popup()
b.send("Runtime.evaluate", {"expression": "customW.value=49; customForm.requestSubmit()"}, sid)
time.sleep(1.2)
d49 = dom(sid); d49["outerWidth"] = inner_width(sid)
step(action="custom_49_rejected", dom=d49, file=shot(sid, "04-custom-49.png", d49["appH"]))
b.send("Runtime.evaluate", {"expression": "customW.value=50; customForm.requestSubmit()"}, sid)
time.sleep(2.5)
d50 = dom(sid); d50["outerWidth"] = inner_width(sid)
d50["applescript"] = [w for w in as_windows() if TARGET and w["id"] == TARGET["id"]]
step(action="custom_50_accepted", dom=d50, file=shot(sid, "05-custom-50.png", d50["appH"]))
b.send("Target.closeTarget", {"targetId": t})

# ---------------- B. 幅の実下限を掃く ----------------
def restore():
    if TARGET:
        osa('tell application "Google Chrome" to set bounds of window id %d to {%d,%d,%d,%d}'
            % (TARGET["id"], LAUNCH_X, LAUNCH_Y, LAUNCH_X + LAUNCH_W, LAUNCH_Y + LAUNCH_H))
        time.sleep(0.5)

restore()
page = b.send("Target.createTarget", {"url": "about:blank"})["targetId"]
psid = b.send("Target.attachToTarget", {"targetId": page, "flatten": True})["sessionId"]
b.send("Runtime.enable", {}, psid)

def cdp_win_width():
    wid = b.send("Browser.getWindowForTarget", {"targetId": page})["windowId"]
    return wid, b.send("Browser.getWindowBounds", {"windowId": wid})["bounds"]

def js_num(expr):
    return b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True}, psid)["result"]["value"]

# B-1 AppleScript 経路（native host と同じ）で下から掃く
sweep_as = []
if TARGET:
    for want in [500, 400, 320, 200, 100, 50, 40, 30, 20, 10, 5, 1]:
        live = {w["id"] for w in as_windows()}
        if TARGET["id"] not in live:
            sweep_as.append({"requested": want, "skipped": "target window gone"}); break
        try:
            osa('tell application "Google Chrome" to set bounds of window id %d to {%d,%d,%d,%d}'
                % (TARGET["id"], LAUNCH_X, LAUNCH_Y, LAUNCH_X + want, LAUNCH_Y + LAUNCH_H))
        except Exception as e:
            sweep_as.append({"requested": want, "error": str(e)}); continue
        time.sleep(0.7)
        back = next((w for w in as_windows() if w["id"] == TARGET["id"]), None)
        _, cb = cdp_win_width()
        sweep_as.append({"requested": want,
                         "applescript_readback": back["width"] if back else None,
                         "cdp_width": cb["width"],
                         "outerWidth": js_num("window.outerWidth"),
                         "innerWidth": js_num("window.innerWidth"),
                         "match": (back or {}).get("width") == want})
        step(action="sweep_applescript", **sweep_as[-1])
restore()

# B-2 拡張 API と同じ経路（CDP Browser.setWindowBounds）で下から掃く
sweep_api = []
wid, _ = cdp_win_width()
for want in [640, 520, 500, 480, 430, 375, 320, 200, 100, 50]:
    b.send("Browser.setWindowBounds", {"windowId": wid, "bounds": {"width": want, "height": LAUNCH_H}})
    time.sleep(0.5)
    _, cb = cdp_win_width()
    sweep_api.append({"requested": want, "cdp_width": cb["width"],
                      "outerWidth": js_num("window.outerWidth"), "clamped": cb["width"] != want})
    step(action="sweep_cdp_api", **sweep_api[-1])
restore()

# B-3 host CLI 自身のバリデーション境界
cli = {}
for want in ["49", "50", "8001"]:
    p = subprocess.run(["/usr/bin/python3", HOST, "--json", want], capture_output=True, text=True, timeout=40)
    cli[want] = {"rc": p.returncode, "stdout": p.stdout.strip()[:300], "stderr": p.stderr.strip()[:300]}
    time.sleep(0.4)
    restore()
step(action="host_cli_validation", results=cli)

log["summary"] = {"sweep_applescript": sweep_as, "sweep_cdp_api": sweep_api, "host_cli": cli}
restore()
json.dump(log, open(os.path.join(OUT, "measure.json"), "w"), ensure_ascii=False, indent=2)
proc.terminate()
try: proc.wait(15)
except Exception: proc.kill()
time.sleep(1.5)
print("AFTER-owner-windows:", json.dumps(as_windows(), ensure_ascii=False))
print("DONE")
