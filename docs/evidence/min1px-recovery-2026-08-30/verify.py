# -*- coding: utf-8 -*-
"""
任意幅入力の下限 50 → 1 の実証と、そこからの復帰手段の実測。

確かめることは 2 つだけ。
  A. popup の任意幅入力で 1 を入れると、ウィンドウが本当に 1px になる（0 は弾かれる）。
  B. その 1px から `viewport_deck_host.py --restore` / `bin/vw --restore` で戻せる。

B が通らないなら下限 1 は入れてはいけない、というのがこの dispatch の停止条件。

安全策: AppleScript は最後に起動した Chrome インスタンスを掴む
（preset-320-2026-08-30/probe_instance.sh で確認済み）。それでもオーナーの常用
ウィンドウへ誤爆しないよう、起動前の window id を退避し、対象 id 以外へは
set bounds も --restore も一切発行しない。--restore は「一番狭いウィンドウ」を
選ぶ実装なので、実行前に必ず「最狭 == 使い捨てウィンドウ」を検証してから呼ぶ。
"""
import base64, json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXT = os.path.join(REPO, "extension")
HOST = os.path.join(EXT, "host", "viewport_deck_host.py")
VW = os.path.join(EXT, "bin", "vw")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/397a2bb1-c477-42f3-8b82-252c81d3900f/scratchpad/vd-min1px"
PROFILE = os.path.join(SCRATCH, "profile")
PORT = 9391
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
LAUNCH_W, LAUNCH_H, X, Y = 900, 700, 700, 120

log = {"meta": {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:500], flush=True)

def run(argv, timeout=40):
    p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return {"argv": argv, "rc": p.returncode, "stdout": (p.stdout or "").strip(), "stderr": (p.stderr or "").strip()}

def osa(s):
    p = subprocess.run(["/usr/bin/osascript", "-e", s], capture_output=True, text=True, timeout=20)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()

def as_windows():
    return json.loads(run(["/usr/bin/python3", HOST, "--list", "--json"])["stdout"]).get("windows", [])

def shot(name, left, top, w, h):
    """デスクトップの実写。ウィンドウが物理的にどう見えるかはこれでしか示せない。"""
    f = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", "%d,%d,%d,%d" % (left, top, w, h), f], timeout=30)
    return {"file": os.path.relpath(f, REPO), "bytes": os.path.getsize(f) if os.path.exists(f) else 0}

# ---------------- 使い捨て Chrome ----------------
shutil.rmtree(SCRATCH, ignore_errors=True); os.makedirs(PROFILE)
nm_dir = os.path.join(PROFILE, "NativeMessagingHosts"); os.makedirs(nm_dir, exist_ok=True)
shutil.copy(os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.nanago.viewport_deck.json"),
            os.path.join(nm_dir, "com.nanago.viewport_deck.json"))

owner = as_windows()
OWNER_IDS = {w["id"] for w in owner}
step(action="owner_windows_before", windows=owner)

proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    f"--window-size={LAUNCH_W},{LAUNCH_H}", f"--window-position={X},{Y}", "https://example.com"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
step(action="launch_chrome", pid=proc.pid, port=PORT)

ver = None
for _ in range(60):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: sys.exit("chrome did not expose CDP")
log["meta"]["chrome"] = ver.get("Browser")
time.sleep(2.5)

wins = as_windows()
cands = [w for w in wins if w["id"] not in OWNER_IDS]
TARGET = next((w for w in cands if abs(w["width"] - LAUNCH_W) <= 6 and abs(w["left"] - X) <= 6), None)
step(action="identify_target", windows=wins, candidates=cands, target=TARGET)
if TARGET is None:
    json.dump(log, open(os.path.join(OUT, "verify.json"), "w"), ensure_ascii=False, indent=2)
    sys.exit("使い捨てウィンドウを特定できなかった。実測を中止する（オーナーのウィンドウは触っていない）")
TID = TARGET["id"]

def target_now():
    return next((w for w in as_windows() if w["id"] == TID), None)

def set_target(w):
    osa('tell application "Google Chrome" to set bounds of window id %d to {%d,%d,%d,%d}' % (TID, X, Y, X + w, Y + LAUNCH_H))
    time.sleep(1.0)

# ---------------- CDP ----------------
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
POPUP = f"chrome-extension://{ext_id}/popup.html"
step(action="load_unpacked", extension_id=ext_id)

def open_popup():
    t = b.send("Target.createTarget", {"url": POPUP})["targetId"]
    sid = b.send("Target.attachToTarget", {"targetId": t, "flatten": True})["sessionId"]
    b.send("Page.enable", {}, sid); b.send("Runtime.enable", {}, sid)
    time.sleep(1.5)
    return t, sid

def ev(sid, expr):
    return b.send("Runtime.evaluate", {"expression": expr, "returnByValue": True}, sid)["result"].get("value")

DOM_JS = """JSON.stringify({
  min: customW.getAttribute('min'), max: customW.getAttribute('max'),
  msg: msg.textContent, curW: curW.textContent,
  validityValid: customW.validity.valid, rangeUnderflow: customW.validity.rangeUnderflow,
  outerWidth: window.outerWidth
})"""
def dom(sid): return json.loads(ev(sid, DOM_JS))

# ---------------- A. popup で 1px まで縮める ----------------
tp, sid = open_popup()
step(action="popup_initial", dom=dom(sid))

ev(sid, "customW.value=0; customForm.requestSubmit()")
time.sleep(1.5)
d0 = dom(sid); d0["applescript"] = target_now()
step(action="custom_0_rejected", dom=d0,
     note="min=1 の制約検証で submit 自体が止まり、ウィンドウ幅は変わらないのが期待値")

ev(sid, "customW.value=1; customForm.requestSubmit()")
time.sleep(3.0)
d1 = dom(sid); d1["applescript"] = target_now()
step(action="custom_1_applied", dom=d1, note="host 経路でウィンドウが実際に 1px になるのが期待値")

step(action="screenshot_at_1px", exact=shot("01-window-1px-exact.png", X, Y, 1, LAUNCH_H),
     applescript=target_now(),
     note="ウィンドウ自身の 1px 幅の実写。周囲を含む見た目の実写は shots.py 側で撮る"
          "（背景を白ウィンドウで制御し、オーナーの画面が写り込まないようにするため）")

# ---------------- B. 復帰手段 ----------------
# --restore は「一番狭いウィンドウ」を選ぶ。呼ぶ前に最狭が使い捨てであることを必ず検証する。
all_now = as_windows()
narrowest = min(all_now, key=lambda w: w["width"]) if all_now else None
guard_ok = bool(narrowest and narrowest["id"] == TID)
step(action="restore_guard", windows=all_now, narrowest=narrowest, guard_ok=guard_ok)
if not guard_ok:
    set_target(LAUNCH_W)
    json.dump(log, open(os.path.join(OUT, "verify.json"), "w"), ensure_ascii=False, indent=2)
    sys.exit("最狭ウィンドウが使い捨てでない。--restore は実行しない")

r1 = run(["/usr/bin/python3", HOST, "--restore", "--json"])
time.sleep(1.5)
step(action="restore_via_host_cli", result=r1, applescript=target_now(),
     note="既定 1280px へ戻るのが期待値")

# 2 回目: 出荷している bin/vw ラッパ + 幅指定
set_target(1)
step(action="shrink_again_to_1px", applescript=target_now())
all_now = as_windows(); narrowest = min(all_now, key=lambda w: w["width"])
if narrowest["id"] != TID:
    set_target(LAUNCH_W); json.dump(log, open(os.path.join(OUT, "verify.json"), "w"), ensure_ascii=False, indent=2)
    sys.exit("guard 失敗（2 回目）")
r2 = run([VW, "--restore", "900", "--json"])
time.sleep(1.5)
step(action="restore_via_vw_wrapper", result=r2, applescript=target_now(),
     note="bin/vw --restore 900 で 900px へ戻るのが期待値")

# ---------------- C. host CLI の下限境界 ----------------
step(action="host_cli_boundary",
     w0=run(["/usr/bin/python3", HOST, "--json", "0"]),
     w1=run(["/usr/bin/python3", HOST, "--json", "1"]),
     applescript_after=target_now())
set_target(LAUNCH_W)
step(action="restore_for_cleanup", applescript=target_now())

# ---------------- 後始末 ----------------
try: b.send("Target.closeTarget", {"targetId": tp})
except Exception: pass
proc.terminate()
try: proc.wait(15)
except Exception: proc.kill()
time.sleep(1.5)
step(action="owner_windows_after", windows=as_windows())
log["meta"]["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
json.dump(log, open(os.path.join(OUT, "verify.json"), "w"), ensure_ascii=False, indent=2)
print("\nWROTE", os.path.join(OUT, "verify.json"))
