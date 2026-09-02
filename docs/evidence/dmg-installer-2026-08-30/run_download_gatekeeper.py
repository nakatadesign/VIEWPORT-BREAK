# -*- coding: utf-8 -*-
"""
第 1 パス: 「購入者がブラウザで DMG をダウンロードする」ところから Gatekeeper の
実挙動までを実測する。

なぜ curl ではなくブラウザで落とすのか:
  Gatekeeper が働くかどうかは com.apple.quarantine 拡張属性の有無で決まる。
  この属性を付けるのは LaunchServices 経由でファイルを保存したアプリ（＝ブラウザ）で、
  curl や cp では付かない。curl で落とした DMG を検証しても、購入者の環境とは別物になる。
  そこで DMG をループバックの HTTP サーバに置き、**使い捨てプロファイルの Chrome** で
  実際にダウンロードする。

オーナーの常用環境に触れないための約束:
  * Chrome は使い捨て user-data-dir。常用プロファイルは開かない。
  * ウィンドウは画面右側の固定矩形に置き、スクリーンショットはその矩形だけを切り出す。
  * /Applications への設置はこのパスでは行わない（第 2 パスで扱う）。
"""
import http.server, json, os, shutil, socketserver, subprocess, sys, threading, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BUILD = os.path.join(REPO, "build")
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SHOTS = os.path.join(HERE, "shots"); os.makedirs(SHOTS, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/db538db5-132c-4282-b6de-7ecd20918185/scratchpad/vb-e2e"
PROFILE = os.path.join(SCRATCH, "dl-profile")
DOWNLOADS = os.path.join(SCRATCH, "Downloads")
STAGE_APPS = os.path.join(SCRATCH, "Applications")   # /Applications の代役（第 1 パス用）
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HTTP_PORT = 8731
X, Y, W, H = 900, 120, 900, 700

DMG = None
for f in sorted(os.listdir(BUILD)):
    if f.endswith(".dmg"):
        DMG = os.path.join(BUILD, f)
if not DMG:
    sys.exit("build/ に DMG が無い。packaging/build_dmg.sh を先に実行する")

log = {"meta": {"dmg": DMG}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:600], flush=True)

def run(cmd, **kw):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                       timeout=kw.pop("timeout", 60), **kw)
    return {"cmd": cmd, "rc": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}

def xattrs(path):
    """拡張属性の名前一覧と、quarantine の値だけを返す。
       -l は値をそのまま出すためバイナリが混ざる。名前と quarantine 値に絞る。"""
    names = run(["/usr/bin/xattr", path])["out"].split()
    q = run(["/usr/bin/xattr", "-p", "com.apple.quarantine", path])
    return {"names": names,
            "com.apple.quarantine": q["out"] if q["rc"] == 0 else None}

def shot(name, rect=None):
    """rect=(x,y,w,h) の論理座標。省略時は指定矩形。画面全体は撮らない。"""
    x, y, w, h = rect or (X, Y, W, H)
    p = os.path.join(SHOTS, name)
    run(["/usr/sbin/screencapture", "-x", "-R", f"{x},{y},{w},{h}", p])
    step(action="screenshot", file=os.path.basename(p), rect=[x, y, w, h],
         bytes=os.path.getsize(p) if os.path.exists(p) else 0)
    return p

# ---------------------------------------------------------------- 準備
shutil.rmtree(SCRATCH, ignore_errors=True)
os.makedirs(PROFILE); os.makedirs(DOWNLOADS); os.makedirs(STAGE_APPS)

step(action="dmg_before_download", path=DMG, bytes=os.path.getsize(DMG),
     sha256=run(["/usr/bin/shasum", "-a", "256", DMG])["out"].split()[0],
     xattr=xattrs(DMG))

# ---------------------------------------------------------------- HTTP サーバ
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=BUILD, **k)
    def log_message(self, *a): pass

socketserver.TCPServer.allow_reuse_address = True
httpd = socketserver.TCPServer(("127.0.0.1", HTTP_PORT), Handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{HTTP_PORT}/" + urllib.request.quote(os.path.basename(DMG))
step(action="serve", url=url, root=BUILD)

# ---------------------------------------------------------------- Chrome でダウンロード
prefs_dir = os.path.join(PROFILE, "Default")
os.makedirs(prefs_dir, exist_ok=True)
with open(os.path.join(prefs_dir, "Preferences"), "w") as f:
    json.dump({"download": {"default_directory": DOWNLOADS, "prompt_for_download": False},
               "profile": {"exit_type": "Normal"}}, f)

proc = subprocess.Popen(
    [CHROME, f"--user-data-dir={PROFILE}", "--no-first-run", "--no-default-browser-check",
     "--disable-features=Translate", f"--window-size={W},{H}", f"--window-position={X},{Y}", url],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
step(action="launch_chrome_for_download", pid=proc.pid, profile=PROFILE)

downloaded = None
deadline = time.time() + 60
while time.time() < deadline:
    cands = [os.path.join(DOWNLOADS, f) for f in os.listdir(DOWNLOADS)
             if f.endswith(".dmg") and not f.endswith(".crdownload")]
    if cands and os.path.getsize(cands[0]) == os.path.getsize(DMG):
        downloaded = cands[0]; break
    time.sleep(1)

if downloaded:
    shot("01-chrome-download.png")
    step(action="downloaded", path=downloaded, bytes=os.path.getsize(downloaded),
         sha256_matches_build=run(["/usr/bin/shasum", "-a", "256", downloaded])["out"].split()[0]
                              == log["steps"][0]["sha256"],
         xattr=xattrs(downloaded))
else:
    step(action="download_failed", note="60 秒でダウンロードが完了しなかった",
         dir_listing=os.listdir(DOWNLOADS))

proc.terminate()
try: proc.wait(timeout=15)
except Exception: proc.kill()
# Chrome は SIGTERM だけでは落ちきらないことがある。残ると AppleScript の tell 先が
# そちらのインスタンスへ移り、以降の計測が別の Chrome を見てしまう（実測で踏んだ）。
subprocess.run(["/usr/bin/pkill", "-f", "--user-data-dir=" + PROFILE], capture_output=True)
time.sleep(2)
httpd.shutdown()

if not downloaded:
    json.dump(log, open(os.path.join(OUT, "download_gatekeeper.json"), "w"),
              ensure_ascii=False, indent=2)
    sys.exit("ダウンロードに失敗")

# ---------------------------------------------------------------- マウント
r = run(["/usr/bin/hdiutil", "attach", downloaded, "-nobrowse", "-plist"])
step(action="hdiutil_attach", rc=r["rc"], err=r["err"][:400])
mnt = None
for line in r["out"].splitlines():
    line = line.strip()
    if line.startswith("<string>/Volumes/"):
        mnt = line.replace("<string>", "").replace("</string>", "")
step(action="mounted", mount_point=mnt, contents=sorted(os.listdir(mnt)) if mnt else None)

app_in_dmg = os.path.join(mnt, "VIEWPORT BREAK.app")
step(action="app_in_dmg",
     xattr=xattrs(app_in_dmg),
     codesign=run(["/usr/bin/codesign", "-dv", app_in_dmg])["err"][:600],
     spctl=run(["/usr/sbin/spctl", "-a", "-vvv", "-t", "exec", app_in_dmg]))

# ---------------------------------------------------------------- /Applications 相当へコピー
installed = os.path.join(STAGE_APPS, "VIEWPORT BREAK.app")
shutil.copytree(app_in_dmg, installed, symlinks=True)
step(action="copied_to_applications_stand_in", path=installed,
     xattr=xattrs(installed),
     spctl=run(["/usr/sbin/spctl", "-a", "-vvv", "-t", "exec", installed]))

run(["/usr/bin/hdiutil", "detach", mnt, "-quiet"])
step(action="detached", mount_point=mnt)

json.dump(log, open(os.path.join(OUT, "download_gatekeeper.json"), "w"),
          ensure_ascii=False, indent=2)
print("\n書き出し:", os.path.join(OUT, "download_gatekeeper.json"))
print("コピー済み .app:", installed)
