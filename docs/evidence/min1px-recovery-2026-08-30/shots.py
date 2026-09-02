# -*- coding: utf-8 -*-
"""
1px まで縮めた Chrome ウィンドウと、復帰後のウィンドウの実写。

verify.py が「値としてそうなった」ことを示すのに対し、こちらは
「画面上でどう見えるか = 拡張アイコンに手が届くか」を示す。

背景に写り込むものを制御するため、同じ使い捨てプロファイルで
**白い背景ウィンドウを先に 1 枚**開き、その上に対象ウィンドウを重ねてから
その領域だけを切り出す。オーナーの常用画面はフレームに入らない。
"""
import json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXT = os.path.join(REPO, "extension")
HOST = os.path.join(EXT, "host", "viewport_deck_host.py")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/397a2bb1-c477-42f3-8b82-252c81d3900f/scratchpad/vd-min1px-shots"
PROFILE = os.path.join(SCRATCH, "profile")
PORT = 9393
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 背景ウィンドウ（白）と、その上に置く対象ウィンドウ
BX, BY, BW, BH = 560, 100, 900, 800          # backdrop
TX, TY, TH     = 640, 160, 620               # target（幅は可変）
CROP = (BX + 10, BY + 10, 700, 300)          # 切り出す領域（背景の内側だけ）

log = {"meta": {}, "shots": []}
def osa(s):
    p = subprocess.run(["/usr/bin/osascript", "-e", s], capture_output=True, text=True, timeout=20)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()
def as_windows():
    o = subprocess.run(["/usr/bin/python3", HOST, "--list", "--json"], capture_output=True, text=True, timeout=30).stdout
    return json.loads(o).get("windows", [])

shutil.rmtree(SCRATCH, ignore_errors=True); os.makedirs(PROFILE)
nm = os.path.join(PROFILE, "NativeMessagingHosts"); os.makedirs(nm)
shutil.copy(os.path.expanduser("~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.nanago.viewport_deck.json"),
            os.path.join(nm, "com.nanago.viewport_deck.json"))

OWNER_IDS = {w["id"] for w in as_windows()}
log["meta"]["owner_ids_before"] = sorted(OWNER_IDS)

# 1 枚目 = 背景（白紙）
proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
    f"--window-size={BW},{BH}", f"--window-position={BX},{BY}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(60):
    try: ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver: sys.exit("no CDP")
log["meta"]["chrome"] = ver.get("Browser")
time.sleep(2.5)
back = [w for w in as_windows() if w["id"] not in OWNER_IDS]
if len(back) != 1: sys.exit("backdrop window not identified: %r" % back)
BACK_ID = back[0]["id"]

class C:
    def __init__(self, url):
        self.ws = websocket.create_connection(url, timeout=40, suppress_origin=True); self.i = 0
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
b.send("Extensions.loadUnpacked", {"path": EXT})

# 2 枚目 = 対象。背景より後に作るので手前に来る
b.send("Target.createTarget", {"url": "https://example.com", "newWindow": True,
                               "left": TX, "top": TY, "width": 820, "height": TH})
time.sleep(3.0)
cands = [w for w in as_windows() if w["id"] not in OWNER_IDS and w["id"] != BACK_ID]
if len(cands) != 1: sys.exit("target window not identified: %r" % cands)
TID = cands[0]["id"]
log["meta"]["backdrop_id"], log["meta"]["target_id"] = BACK_ID, TID

def set_target(w):
    osa('tell application "Google Chrome" to set bounds of window id %d to {%d,%d,%d,%d}'
        % (TID, TX, TY, TX + w, TY + TH))
    time.sleep(1.2)
def shot(name):
    f = os.path.join(OUT, name)
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", "%d,%d,%d,%d" % CROP, f], timeout=30)
    return f

for w, name in [(820, "02-a-820px.png"), (320, "02-b-320px.png"), (50, "02-c-050px.png"), (1, "02-d-001px.png")]:
    set_target(w)
    f = shot(name)
    got = next((x for x in as_windows() if x["id"] == TID), None)
    log["shots"].append({"requested": w, "applescript_readback": got and got["width"],
                         "file": os.path.relpath(f, REPO), "bytes": os.path.getsize(f)})
    print(json.dumps(log["shots"][-1], ensure_ascii=False), flush=True)

# --restore で戻す（最狭が対象であることを確認してから）
allw = as_windows(); narrow = min(allw, key=lambda w: w["width"])
log["restore_guard"] = {"narrowest": narrow, "ok": narrow["id"] == TID}
if narrow["id"] != TID:
    set_target(820); sys.exit("guard failed")
p = subprocess.run(["/usr/bin/python3", HOST, "--restore", "800", "--json"], capture_output=True, text=True, timeout=40)
time.sleep(1.5)
f = shot("03-restored-800.png")
got = next((x for x in as_windows() if x["id"] == TID), None)
log["restore"] = {"rc": p.returncode, "stdout": p.stdout.strip(), "applescript_readback": got and got["width"],
                  "file": os.path.relpath(f, REPO), "bytes": os.path.getsize(f)}
print(json.dumps(log["restore"], ensure_ascii=False), flush=True)

proc.terminate()
try: proc.wait(15)
except Exception: proc.kill()
time.sleep(1.5)
log["meta"]["owner_ids_after"] = sorted(w["id"] for w in as_windows())
json.dump(log, open(os.path.join(OUT, "shots.json"), "w"), ensure_ascii=False, indent=2)
print("WROTE", os.path.join(OUT, "shots.json"))
