# -*- coding: utf-8 -*-
"""極小幅での Chrome ウィンドウ実写。技術的到達下限と「実用下限」を分けて示すための証拠。"""
import json, os, shutil, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
HOST = os.path.join(REPO, "extension", "host", "viewport_deck_host.py")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/c9e5f2cb-c90f-4d68-b0a4-9d54f0ca1736/scratchpad/vd-shots"
PROFILE = os.path.join(SCRATCH, "profile")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
X, Y, H = 700, 120, 700
PORT = 9381

def as_windows():
    return json.loads(subprocess.run(["/usr/bin/python3", HOST, "--list", "--json"],
                                     capture_output=True, text=True, timeout=30).stdout).get("windows", [])
def osa(s):
    p = subprocess.run(["/usr/bin/osascript", "-e", s], capture_output=True, text=True, timeout=20)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()

shutil.rmtree(SCRATCH, ignore_errors=True); os.makedirs(PROFILE)
before = {w["id"] for w in as_windows()}
proc = subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
    "--no-first-run", "--no-default-browser-check", f"--window-size=900,{H}", f"--window-position={X},{Y}",
    "https://example.com"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
for _ in range(60):
    try: urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1); break
    except Exception: time.sleep(0.5)
time.sleep(3)
cand = [w for w in as_windows() if w["id"] not in before]
if not cand: sys.exit("target window not identified")
T = cand[0]
res = []
for w in [320, 200, 100, 50, 20]:
    osa('tell application "Google Chrome" to set bounds of window id %d to {%d,%d,%d,%d}' % (T["id"], X, Y, X + w, Y + H))
    time.sleep(1.2)
    back = next((x for x in as_windows() if x["id"] == T["id"]), None)
    f = os.path.join(OUT, f"win-{w:04d}px.png")
    subprocess.run(["/usr/sbin/screencapture", "-x", "-R", f"{X},{Y},{max(w,8)},{H}", f], timeout=30)
    res.append({"requested": w, "applescript_readback": back["width"] if back else None,
                "shot": f, "bytes": os.path.getsize(f) if os.path.exists(f) else 0})
    print(json.dumps(res[-1], ensure_ascii=False))
json.dump(res, open(os.path.join(OUT, "shots_floor.json"), "w"), ensure_ascii=False, indent=2)
proc.terminate()
try: proc.wait(15)
except Exception: proc.kill()
time.sleep(1)
print("AFTER-owner:", json.dumps(as_windows(), ensure_ascii=False))
