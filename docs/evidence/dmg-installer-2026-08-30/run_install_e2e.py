# -*- coding: utf-8 -*-
"""
第 3 パス: Gatekeeper を通した後の通し実測。
  DMG から入れた .app を起動 → セットアップ → Chrome へ拡張を読み込む
  → 拡張のボタン相当を叩く → **ウィンドウが実際に 375px になる** までを測る。

Gatekeeper の解除について（この計測の限界）:
  購入者は「システム設定 → プライバシーとセキュリティ →『このまま開く』」を押す。
  この操作は Touch ID / パスワード認証を伴い、worker からは実行できない。
  そこで等価な代替として quarantine 属性を落とす（`xattr -dr com.apple.quarantine`）。
  **システム設定の「このまま開く」そのものは未実測**であり、文書側にもそう書く。

オーナーの環境を壊さないための約束:
  * Chrome は使い捨て user-data-dir。native messaging manifest もその中へ入れる
    （インストーラの --chrome-dir で、製品と同じコードパスを使う）。
  * ウィンドウは画面右側の固定位置。スクリーンショットはその矩形だけを切る。
  * 幅を変えるのは使い捨て Chrome のウィンドウだけ。対象は bounds 一致で特定するので、
    一致しなければ host 側が失敗を返して終わる（オーナーのウィンドウは触らない）。
"""
import json, os, shutil, subprocess, sys, time, urllib.request
import websocket

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SHOTS = os.path.join(HERE, "shots"); os.makedirs(SHOTS, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/db538db5-132c-4282-b6de-7ecd20918185/scratchpad/vb-e2e"
PROFILE = os.path.join(SCRATCH, "e2e-profile")
APP = "/Applications/VIEWPORT BREAK.app"
HOST_BIN = os.path.join(APP, "Contents/MacOS/viewport-break")
EXT_DIR = os.path.expanduser("~/Library/Application Support/VIEWPORT BREAK/extension")
EXT_ID = "ejlimgikbnaihoigbcmelaadniiminfj"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9394
X, Y, W0, H0 = 900, 120, 1000, 760

log = {"meta": {}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:800], flush=True)

def run(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    return {"rc": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}

def osa(script, timeout=30):
    return run(["/usr/bin/osascript", "-e", script], timeout=timeout)

def shot(name, rect):
    x, y, w, h = rect
    p = os.path.join(SHOTS, name)
    run(["/usr/sbin/screencapture", "-x", "-R", f"{x},{y},{w},{h}", p])
    step(action="screenshot", file=name, rect=list(rect),
         bytes=os.path.getsize(p) if os.path.exists(p) else 0)
    return p

def host_windows():
    r = run([HOST_BIN, "--list", "--json"])
    try:
        return json.loads(r["out"]).get("windows", [])
    except Exception:
        return []

class CDP:
    def __init__(self, url):
        # Origin ヘッダを付けると Chrome 151 に 403 で弾かれる
        self.ws = websocket.create_connection(url, timeout=120, suppress_origin=True)
        self.i = 0
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
    def close(self):
        try: self.ws.close()
        except Exception: pass

# ---------------------------------------------------------------- 0. 前提
if not os.path.exists(HOST_BIN):
    sys.exit("先に run_gatekeeper_install.py を実行して /Applications へ入れる")

step(action="before_unquarantine",
     quarantine=run(["/usr/bin/xattr", "-p", "com.apple.quarantine", APP])["out"] or None,
     spctl=run(["/usr/sbin/spctl", "-a", "-vvv", "-t", "exec", APP])["err"])

# 直前パスで出た Gatekeeper のダイアログ（CoreServicesUIAgent 所有）が残っていると、
# それが modal なせいで以降の AppleScript や App 起動が丸ごと止まる。実測で
# `--doctor` が 60 秒タイムアウトした原因がこれだった。まず「完了」で閉じる。
d = osa('tell application "System Events" to tell process "CoreServicesUIAgent" to '
        'click button "完了" of window 1')
step(action="dismiss_leftover_gatekeeper_dialog", rc=d["rc"], out=d["out"][:200], err=d["err"][:200])
# 前パスで起動しかけたプロセスも落とす
run(["/usr/bin/pkill", "-f", "VIEWPORT BREAK.app/Contents/MacOS/viewport-break"])
# 前回試行の使い捨て Chrome が残っていると、同じデバッグポートを掴んだまま
# 別の（フラグの違う）インスタンスへ繋ぎに行ってしまう
run(["/usr/bin/pkill", "-f", "--user-data-dir=" + PROFILE])
time.sleep(3)

# ---------------------------------------------------------------- 1. Gatekeeper 解除（代替手段）
r = run(["/usr/bin/xattr", "-dr", "com.apple.quarantine", APP])
step(action="unquarantine", rc=r["rc"],
     note="システム設定の「このまま開く」の代替。その操作自体は未実測",
     quarantine_after=run(["/usr/bin/xattr", "-p", "com.apple.quarantine", APP])["out"] or None)

# ---------------------------------------------------------------- 2. GUI セットアップ
run(["/usr/bin/open", APP])
time.sleep(5)
pos = osa('tell application "System Events" to tell process "viewport-break" to '
          'return (position of window 1) & (size of window 1)')
step(action="setup_dialog_geometry", raw=pos["out"], err=pos["err"][:200])
if pos["rc"] == 0 and pos["out"]:
    x, y, w, h = [int(v.strip()) for v in pos["out"].split(",")][:4]
    shot("20-setup-dialog.png", (x, y, w, h))
osa('tell application "System Events" to key code 53')   # 既定ボタンは Finder を開くので Esc
time.sleep(2)

manifest_path = os.path.expanduser(
    "~/Library/Application Support/Google/Chrome/NativeMessagingHosts/com.nanago.viewport_deck.json")
step(action="default_profile_manifest",
     content=json.load(open(manifest_path)) if os.path.exists(manifest_path) else None)
step(action="extension_deployed", dir=EXT_DIR,
     files=sorted(os.listdir(EXT_DIR)) if os.path.isdir(EXT_DIR) else None,
     id_check=json.loads(run([os.path.join(HERE, "..", "..", "..", "tools", "extension_id.py"),
                              os.path.join(EXT_DIR, "manifest.json"), "--json"])["out"]))
doc = run([HOST_BIN, "--doctor", "--json"], timeout=45)
step(action="doctor_after_setup", rc=doc["rc"],
     report=json.loads(doc["out"]) if doc["out"] else None, err=doc["err"][:300])

# ---------------------------------------------------------------- 3. 使い捨てプロファイルへ登録
shutil.rmtree(PROFILE, ignore_errors=True); os.makedirs(PROFILE)
r = run([HOST_BIN, "--install", "--chrome-dir", PROFILE, "--json"])
step(action="install_into_disposable_profile", rc=r["rc"],
     result=json.loads(r["out"]) if r["out"] else None, err=r["err"][:300])

nm = os.path.join(PROFILE, "NativeMessagingHosts", "com.nanago.viewport_deck.json")
step(action="disposable_manifest", exists=os.path.exists(nm),
     content=json.load(open(nm)) if os.path.exists(nm) else None)

# ---------------------------------------------------------------- 4. Chrome 起動
owner_ids = {w["id"] for w in host_windows()}
step(action="owner_windows_before", ids=sorted(owner_ids))

proc = subprocess.Popen(
    [CHROME, f"--user-data-dir={PROFILE}", f"--remote-debugging-port={PORT}",
     "--no-first-run", "--no-default-browser-check", "--disable-features=Translate",
     # Chrome 151 は Origin 付きの CDP WebSocket 接続を既定で拒否する
     "--remote-allow-origins=*",
     f"--window-size={W0},{H0}", f"--window-position={X},{Y}", "about:blank"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ver = None
for _ in range(80):
    try:
        ver = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1)); break
    except Exception: time.sleep(0.5)
if not ver:
    sys.exit("CDP に繋がらない")
step(action="chrome_launched", browser=ver.get("Browser"), pid=proc.pid, profile=PROFILE)
time.sleep(3)

new = [w for w in host_windows() if w["id"] not in owner_ids]
step(action="applescript_sees_disposable_window", windows=new,
     note="AppleScript から使い捨て Chrome のウィンドウが見えるかの確認")
if len(new) != 1:
    step(action="abort", reason="使い捨てウィンドウを一意に特定できない。誤爆を避けて中止する")
    proc.terminate(); json.dump(log, open(os.path.join(OUT, "install_e2e.json"), "w"),
                                ensure_ascii=False, indent=2)
    sys.exit(1)
target = new[0]

# ---------------------------------------------------------------- 5. 拡張を読み込む
b = CDP(ver["webSocketDebuggerUrl"])
loaded = b.send("Extensions.loadUnpacked", {"path": EXT_DIR})
step(action="load_unpacked", path=EXT_DIR, returned_id=loaded.get("id"),
     matches_fixed_id=loaded.get("id") == EXT_ID,
     note="chrome://extensions の「パッケージ化されていない拡張機能を読み込む」と同じ結果になる CDP 経路")
time.sleep(3)

targets = b.send("Target.getTargets")["targetInfos"]
sw = [t for t in targets if t["type"] == "service_worker" and EXT_ID in t["url"]]
step(action="service_worker", found=len(sw), url=sw[0]["url"] if sw else None)
if not sw:
    step(action="abort", reason="service worker が見つからない")
    b.close(); proc.terminate()
    json.dump(log, open(os.path.join(OUT, "install_e2e.json"), "w"), ensure_ascii=False, indent=2)
    sys.exit(1)

sid = b.send("Target.attachToTarget", {"targetId": sw[0]["targetId"], "flatten": True})["sessionId"]

# host 疎通（AppleScript を触らない ping）。service worker では動的 import() が使えないので
# core.js は経由せず、native messaging だけを直接叩いて到達性を見る。
ping = b.send("Runtime.evaluate", {
    "expression": "chrome.runtime.sendNativeMessage('com.nanago.viewport_deck', {cmd:'ping'})"
                  ".then(r=>JSON.stringify(r), e=>'ERR:'+e.message)",
    "awaitPromise": True, "returnByValue": True}, sid=sid)
step(action="host_ping_from_extension", result=ping.get("result", {}).get("value"))

# chrome://extensions を開いて、固定 ID で載っていることを画面で残す
ext_tab = b.send("Target.createTarget", {"url": "chrome://extensions/"})
time.sleep(3)
shot("25-chrome-extensions.png", (X, Y, W0, min(H0, 700)))
b.send("Target.closeTarget", {"targetId": ext_tab["targetId"]})
time.sleep(1)

# ------------------------------------------------------------ popup を実際に開いて押す
# ツールバーの popup そのものは自動操作できないので、同じ popup.html をタブで開き、
# 同じ popup.js の click ハンドラを起動する。経路は popup.js → core.js →
# sendNativeMessage → .app の host、と製品と同一になる。
tgt = b.send("Target.createTarget", {"url": f"chrome-extension://{EXT_ID}/popup.html"})
psid = b.send("Target.attachToTarget", {"targetId": tgt["targetId"], "flatten": True})["sessionId"]
time.sleep(2)
b.send("Runtime.enable", {}, sid=psid)

grid = b.send("Runtime.evaluate", {
    "expression": "JSON.stringify({buttons:[...document.querySelectorAll('#grid .btn')]"
                  ".map(b=>b.dataset.w), current:document.getElementById('curW').textContent})",
    "returnByValue": True}, sid=psid)
step(action="popup_opened", state=grid.get("result", {}).get("value"))

shot("30-before-375.png", (X, Y, W0, min(H0, 700)))

# ---------------------------------------------------------------- 6. 375px にする
t0 = time.time()
click = b.send("Runtime.evaluate", {
    "expression": "(async()=>{const b=[...document.querySelectorAll('#grid .btn')]"
                  ".find(x=>x.dataset.w==='375'); b.click(); "
                  "await new Promise(r=>setTimeout(r,2500)); "
                  "return JSON.stringify({msg:document.getElementById('msg').textContent,"
                  "curW:document.getElementById('curW').textContent});})()",
    "awaitPromise": True, "returnByValue": True}, sid=psid)
elapsed = round(time.time() - t0, 2)
step(action="popup_click_375", seconds=elapsed, result=click.get("result", {}).get("value"),
     note="popup.js の click ハンドラ = ツールバーから押したときと同じ経路")

time.sleep(1.5)
after = [w for w in host_windows() if w["id"] == target["id"]]
step(action="applescript_readback", before=target, after=after[0] if after else None,
     reached_375=bool(after) and after[0]["width"] == 375)

if after:
    a = after[0]
    shot("31-after-375.png", (a["left"], a["top"], a["width"], min(a["height"], 700)))

meas = b.send("Runtime.evaluate", {
    "expression": "chrome.windows.getCurrent().then(w=>JSON.stringify("
                  "{id:w.id,left:w.left,top:w.top,width:w.width,height:w.height}))",
    "awaitPromise": True, "returnByValue": True}, sid=psid)
step(action="chrome_windows_api_readback", value=meas.get("result", {}).get("value"))

# ---------------------------------------------------------------- 7. 後始末
b.close()
proc.terminate()
try: proc.wait(timeout=20)
except Exception: proc.kill()
step(action="chrome_terminated")

json.dump(log, open(os.path.join(OUT, "install_e2e.json"), "w"), ensure_ascii=False, indent=2)
print("\n書き出し:", os.path.join(OUT, "install_e2e.json"))
