# -*- coding: utf-8 -*-
"""
第 2 パス: ダウンロード済み（quarantine 付き）DMG をマウントし、
**Finder でドラッグしたのと同じ経路**で /Applications へ入れ、初回起動で
Gatekeeper が実際に何を出すかを実写する。

quarantine の扱い（ここが実測の肝であり、同時にこの計測の限界）:
  Gatekeeper の初回起動チェックは com.apple.quarantine 拡張属性の有無で起きる。
  この属性を付けるのは LaunchServices を知っているアプリ（Finder / ブラウザ）で、
  ditto / cp / shutil では付かない。マウントした DMG の中の .app 自体にも属性は
  無い（quarantine はボリューム側に付いている。§実測 out/download_gatekeeper.json）。
  つまり「Finder でドラッグ」以外の経路でコピーすると Gatekeeper が働かない。

  Finder に AppleScript で duplicate させる方法は試したが、
  「"ターミナル.app" が "Finder.app" を制御するアクセスを要求しています」の TCC 許可が
  必要で、オーナーに無断で許可を与えないため中止した（許可しないで閉じた）。

  そこで **ditto でコピーしたうえで、ダウンロードした DMG に実際に付いていた
  quarantine 値をそのまま .app へ書く**。値は捏造ではなく実測値の転記である。
  「Finder のドラッグそのもの」は未実測であり、この点は文書側にも明記する。

このスクリプトが行う不可逆でない変更:
  * /Applications/VIEWPORT BREAK.app を作る（削除で元に戻る）
"""
import json, os, plistlib, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)
SHOTS = os.path.join(HERE, "shots"); os.makedirs(SHOTS, exist_ok=True)
SCRATCH = "/private/tmp/claude-501/-Users-macmini-Projects/db538db5-132c-4282-b6de-7ecd20918185/scratchpad/vb-e2e"
DOWNLOADED = os.path.join(SCRATCH, "Downloads", "VIEWPORT BREAK 1.0.0.dmg")
APP_DEST = "/Applications/VIEWPORT BREAK.app"
# ダイアログは画面中央に出る。オーナーの常用ウィンドウ（左端 x<420）を写さない矩形。
DLG_RECT = (560, 240, 800, 620)

log = {"meta": {"dmg": DOWNLOADED}, "steps": []}
def step(**kw):
    kw["t"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    log["steps"].append(kw)
    print(json.dumps(kw, ensure_ascii=False)[:700], flush=True)

def run(cmd, timeout=60):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    return {"rc": p.returncode, "out": p.stdout.strip(), "err": p.stderr.strip()}

def osa(script, timeout=30):
    return run(["/usr/bin/osascript", "-e", script], timeout=timeout)

def xattrs(path):
    names = run(["/usr/bin/xattr", path])["out"].split()
    q = run(["/usr/bin/xattr", "-p", "com.apple.quarantine", path])
    return {"names": names, "com.apple.quarantine": q["out"] if q["rc"] == 0 else None}

def shot(name, rect=DLG_RECT):
    x, y, w, h = rect
    p = os.path.join(SHOTS, name)
    run(["/usr/sbin/screencapture", "-x", "-R", f"{x},{y},{w},{h}", p])
    step(action="screenshot", file=name, rect=list(rect),
         bytes=os.path.getsize(p) if os.path.exists(p) else 0)
    return p

def frontmost():
    return osa('tell application "System Events" to return name of first process whose frontmost is true')["out"]

def dialog_text():
    """最前面プロセスのウィンドウに出ている静的テキストを全部拾う。"""
    s = ('tell application "System Events"\n'
         '  set p to first process whose frontmost is true\n'
         '  set acc to ""\n'
         '  try\n'
         '    repeat with w in windows of p\n'
         '      repeat with e in entire contents of w\n'
         '        try\n'
         '          if class of e is static text then set acc to acc & (value of e as text) & linefeed\n'
         '        end try\n'
         '        try\n'
         '          if class of e is button then set acc to acc & "[BUTTON] " & (name of e as text) & linefeed\n'
         '        end try\n'
         '      end repeat\n'
         '    end repeat\n'
         '  end try\n'
         '  return (name of p) & linefeed & "----" & linefeed & acc\n'
         'end tell')
    return osa(s, timeout=40)["out"]

# 前の試行のプロセスやダイアログが画面に残っていると Gatekeeper の実写に混ざる。
# 実際に一度、前回の .app が出したままのダイアログを撮ってしまった。
run(["/usr/bin/pkill", "-f", "VIEWPORT BREAK.app/Contents/MacOS/viewport-break"])
time.sleep(2)
step(action="cleanup_previous_processes",
     still_running=run(["/usr/bin/pgrep", "-f", "MacOS/viewport-break"])["out"])

if not os.path.exists(DOWNLOADED):
    sys.exit("先に run_download_gatekeeper.py を実行する")
if os.path.exists(APP_DEST):
    shutil.rmtree(APP_DEST)
    step(action="removed_existing_app", path=APP_DEST)

# ---------------------------------------------------------------- マウント
r = run(["/usr/bin/hdiutil", "attach", DOWNLOADED, "-nobrowse", "-plist"])
mnt = None
for line in r["out"].splitlines():
    line = line.strip()
    if line.startswith("<string>/Volumes/"):
        mnt = line.replace("<string>", "").replace("</string>", "")
step(action="mounted", mount_point=mnt, rc=r["rc"],
     volume_xattr=xattrs(mnt) if mnt else None)

src = os.path.join(mnt, "VIEWPORT BREAK.app")

# ---------------------------------------------------------------- コピー + quarantine 転記
QVAL = xattrs(DOWNLOADED)["com.apple.quarantine"]
step(action="quarantine_value_on_downloaded_dmg", value=QVAL,
     note="Chrome がダウンロード時に書いた実測値。これを .app へ転記する")

r = run(["/usr/bin/ditto", src, APP_DEST])
step(action="ditto", rc=r["rc"], err=r["err"][:300],
     xattr_right_after_ditto=xattrs(APP_DEST))

r = run(["/usr/bin/xattr", "-w", "-r", "com.apple.quarantine", QVAL, APP_DEST])
step(action="apply_quarantine", rc=r["rc"], err=r["err"][:300],
     note="Finder のドラッグで LaunchServices が行う伝播を、実測値の転記で代替した")

step(action="installed_app", path=APP_DEST, xattr=xattrs(APP_DEST),
     exe_xattr=xattrs(os.path.join(APP_DEST, "Contents/MacOS/viewport-break")),
     spctl=run(["/usr/sbin/spctl", "-a", "-vvv", "-t", "exec", APP_DEST]),
     codesign_verify=run(["/usr/bin/codesign", "--verify", "--deep", "--strict", "-vv", APP_DEST]))

run(["/usr/bin/hdiutil", "detach", mnt, "-quiet"])
step(action="detached")

# ---------------------------------------------------------------- 初回起動（Gatekeeper）
step(action="launch_attempt_1", note="quarantine 付きの未公証 .app を open する")
r = run(["/usr/bin/open", APP_DEST])
step(action="open_rc", rc=r["rc"], err=r["err"][:200])
time.sleep(4)
# ダイアログだけを切り出す矩形。周囲にオーナーの画面が入らない大きさに詰めてある。
shot("10-gatekeeper-first-launch.png", rect=(826, 206, 272, 304))
step(action="frontmost_after_launch", process=frontmost(), ui=dialog_text()[:1500])

# 閉じるのは **Esc だけ**。このダイアログの既定ボタンは「ゴミ箱に入れる」なので、
# return を送ると .app がそのままゴミ箱へ移動する（実際に一度消えた）。
osa('tell application "System Events" to key code 53')
time.sleep(2)
step(action="after_dismiss", process=frontmost(),
     app_running=run(["/usr/bin/pgrep", "-f", "VIEWPORT BREAK.app/Contents/MacOS"])["out"])

json.dump(log, open(os.path.join(OUT, "gatekeeper_install.json"), "w"),
          ensure_ascii=False, indent=2)
print("\n書き出し:", os.path.join(OUT, "gatekeeper_install.json"))
