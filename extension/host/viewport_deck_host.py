#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""
VIEWPORT BREAK — native messaging host.

役割はひとつだけ: Chrome ウィンドウの幅を AppleScript の `set bounds` で変える。

なぜ native host が要るのか (docs/WINDOW_FLOOR_2026-08-30.md):
  通常のタブ付き Chrome ウィンドウには幅 500 DIP の下限がある。
  chrome.windows.update も CDP Browser.setWindowBounds も
  Widget::SetBounds() を通るため、この下限でクランプされる。
  AppleScript の `set bounds` だけは window_applescript.mm が値を
  NSWindow へ KVC 転送するため Widget::SetBounds() を通らず、下限に掛からない。
  よって 375 / 390px へは、この経路でしか到達できない。

2 つの使い方:
  1. native messaging host  — 引数なしで起動。Chrome が stdin/stdout で話す。
  2. CLI                    — `viewport_deck_host.py 375` のように引数を付ける。
                              拡張なしでも同じことができ、host の疎通確認にも使う。

依存: /usr/bin/python3 と /usr/bin/osascript のみ（どちらも macOS 標準）。
"""

import json
import re
import struct
import subprocess
import sys

HOST_VERSION = "1.0.0"
APP = "Google Chrome"
MIN_WIDTH, MAX_WIDTH = 1, 8000

# 幅を戻すときの既定値。--restore を引数なしで打ったときここへ戻す。
RESTORE_WIDTH = 1280

# 実測で下限を貫通した経路（この定数は説明用。処理には使わない）
ENGINE = "applescript:set-bounds"


class HostError(Exception):
    pass


def osascript(script):
    """osascript を実行して stdout を返す。失敗は HostError。"""
    try:
        p = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        raise HostError("osascript がタイムアウトした（15s）")
    if p.returncode != 0:
        err = (p.stderr or "").strip()
        # -1743 = Automation 権限が未許可
        if "-1743" in err or "Not authorized" in err:
            raise HostError(
                "Automation 権限がない。システム設定 → プライバシーとセキュリティ → "
                "オートメーション で Google Chrome から Google Chrome への許可を有効にする。 "
                + err
            )
        raise HostError("osascript 失敗: " + (err or "returncode=%d" % p.returncode))
    return (p.stdout or "").strip()


NOT_RUNNING = "__VD_NOT_RUNNING__"


def list_windows():
    """
    Chrome の全ウィンドウを [{id,left,top,width,height}] で返す。

    `is running` で先に確かめてから tell に入る。この判定は起動を伴わない。
    素の `tell application "Google Chrome"` は Chrome が終了していると
    **起動してしまう**ため、必ずこの guard を通す。
    """
    script = (
        'if application "%s" is running then\n'
        '  tell application "%s"\n'
        '    set out to ""\n'
        '    repeat with w in windows\n'
        '      set b to bounds of w\n'
        '      set out to out & (id of w as text) & "," & (item 1 of b as text) & ","'
        ' & (item 2 of b as text) & "," & (item 3 of b as text) & ","'
        ' & (item 4 of b as text) & "\\n"\n'
        '    end repeat\n'
        '    return out\n'
        '  end tell\n'
        'else\n'
        '  return "%s"\n'
        'end if' % (APP, APP, NOT_RUNNING)
    )
    out = osascript(script)
    if out.strip() == NOT_RUNNING:
        raise HostError("Chrome が起動していない")
    wins = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) != 5:
            continue
        try:
            wid, l, t, r, b = (int(x) for x in parts)
        except ValueError:
            continue
        wins.append({"id": wid, "left": l, "top": t, "width": r - l, "height": b - t})
    return wins


def pick_window(wins, match):
    """
    拡張が送ってきた chrome.windows の bounds に対応する AppleScript ウィンドウを選ぶ。
    AppleScript の bounds と chrome.windows の座標系・単位は一致する（実測済み）。
    """
    if not wins:
        raise HostError("Chrome のウィンドウが 1 つも無い")
    if not match:
        return wins[0]

    def g(k):
        v = match.get(k)
        return int(v) if isinstance(v, (int, float)) else None

    ml, mt, mw, mh = g("left"), g("top"), g("width"), g("height")

    # 1. 完全一致
    for w in wins:
        if (w["left"], w["top"], w["width"], w["height"]) == (ml, mt, mw, mh):
            return w
    # 2. 左上一致（直前に高さだけ変わっている等）
    for w in wins:
        if (w["left"], w["top"]) == (ml, mt):
            return w
    # 3. ウィンドウが 1 枚しか無いなら曖昧さは無い
    if len(wins) == 1:
        return wins[0]
    # 4. 左上への距離が最も近いもの。ただし遠すぎるなら諦める
    if ml is not None and mt is not None:
        best = min(wins, key=lambda w: abs(w["left"] - ml) + abs(w["top"] - mt))
        if abs(best["left"] - ml) + abs(best["top"] - mt) <= 40:
            return best
    raise HostError("対象ウィンドウを特定できなかった（候補 %d 枚）" % len(wins))


def set_width(width, height=None, match=None):
    """幅を width にする。height 未指定なら現在の高さを保つ。実測値を読み返して返す。"""
    width = int(width)
    if not (MIN_WIDTH <= width <= MAX_WIDTH):
        raise HostError("幅は %d〜%d の範囲で指定する: %d" % (MIN_WIDTH, MAX_WIDTH, width))

    win = pick_window(list_windows(), match)
    h = int(height) if height else win["height"]
    l, t = win["left"], win["top"]

    osascript(
        'if application "%s" is running then tell application "%s" to '
        'set bounds of window id %d to {%d, %d, %d, %d}'
        % (APP, APP, win["id"], l, t, l + width, t + h)
    )

    # 「設定した」ではなく「実際にそうなった」を返す。読み返しは必須。
    after = next((w for w in list_windows() if w["id"] == win["id"]), None)
    if after is None:
        raise HostError("設定後にウィンドウを読み返せなかった（id=%d）" % win["id"])
    return after


def get_bounds(match=None):
    return pick_window(list_windows(), match)


def restore_width(width=None):
    """
    「戻せなくなった」ときの復帰口。

    幅の下限を 1px まで開けた以上、ツールバーの拡張アイコンが押せず popup から戻せない
    状態が起こりうる（実測では 50px 未満で信号機ボタンも欠ける）。そこで
    **一番狭いウィンドウ**を対象に選び、既定 1280px へ広げる。

    「現在のウィンドウ」ではなく「一番狭いウィンドウ」を選ぶのは、この経路が呼ばれる
    のは常に「狭くしすぎて操作できない 1 枚がある」場面だから。ターミナルから打つ以上
    Chrome は前面ですらなく、`--get` の「先頭のウィンドウ」は当てにならない。
    """
    width = RESTORE_WIDTH if width is None else int(width)
    if not (MIN_WIDTH <= width <= MAX_WIDTH):
        raise HostError("幅は %d〜%d の範囲で指定する: %d" % (MIN_WIDTH, MAX_WIDTH, width))

    wins = list_windows()
    if not wins:
        raise HostError("Chrome のウィンドウが 1 つも無い")
    target = min(wins, key=lambda w: w["width"])
    before = dict(target)

    osascript(
        'if application "%s" is running then tell application "%s" to '
        'set bounds of window id %d to {%d, %d, %d, %d}'
        % (APP, APP, target["id"], target["left"], target["top"],
           target["left"] + width, target["top"] + target["height"])
    )

    after = next((w for w in list_windows() if w["id"] == target["id"]), None)
    if after is None:
        raise HostError("設定後にウィンドウを読み返せなかった（id=%d）" % target["id"])
    return {"before": before, "bounds": after}


def handle(req):
    cmd = (req or {}).get("cmd", "")
    if cmd == "ping":
        return {"ok": True, "host_version": HOST_VERSION, "engine": ENGINE}
    if cmd == "set":
        b = set_width(req.get("width"), req.get("height"), req.get("match"))
        return {"ok": True, "bounds": b, "engine": ENGINE}
    if cmd == "get":
        return {"ok": True, "bounds": get_bounds(req.get("match")), "engine": ENGINE}
    if cmd == "list":
        return {"ok": True, "windows": list_windows(), "engine": ENGINE}
    if cmd == "restore":
        r = restore_width(req.get("width"))
        return {"ok": True, "bounds": r["bounds"], "before": r["before"], "engine": ENGINE}
    raise HostError("未知のコマンド: %r" % (cmd,))


# ---------------- native messaging (stdin/stdout, 4-byte length prefix) ----------------

def nm_read(stream):
    raw = stream.read(4)
    if len(raw) < 4:
        return None  # Chrome がパイプを閉じた = 正常終了
    (n,) = struct.unpack("@I", raw)
    body = stream.read(n)
    if len(body) < n:
        return None
    return json.loads(body.decode("utf-8"))


def nm_write(stream, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("@I", len(data)))
    stream.write(data)
    stream.flush()


def serve():
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    while True:
        try:
            req = nm_read(stdin)
        except Exception as e:
            nm_write(stdout, {"ok": False, "error": "受信に失敗: %s" % e})
            return
        if req is None:
            return
        try:
            nm_write(stdout, handle(req))
        except HostError as e:
            nm_write(stdout, {"ok": False, "error": str(e)})
        except Exception as e:
            nm_write(stdout, {"ok": False, "error": "内部エラー: %s: %s" % (type(e).__name__, e)})


# ---------------- CLI ----------------

USAGE = """使い方:
  viewport_deck_host.py <幅>            現在のウィンドウを指定幅にする（高さは維持）
  viewport_deck_host.py <幅> <高さ>     幅と高さを指定
  viewport_deck_host.py --list          Chrome の全ウィンドウを表示
  viewport_deck_host.py --get           現在のウィンドウの bounds を表示
  viewport_deck_host.py --restore       一番狭いウィンドウを 1280px へ戻す（緊急復帰）
  viewport_deck_host.py --restore <幅>  戻す幅を指定する
  viewport_deck_host.py --json <幅>     結果を JSON で出す
引数なしで起動すると Chrome の native messaging host として動く。
"""


def cli(argv):
    as_json = False
    if "--json" in argv:
        as_json = True
        argv = [a for a in argv if a != "--json"]

    def emit(obj, human):
        print(json.dumps(obj, ensure_ascii=False) if as_json else human)

    try:
        if argv[0] in ("-h", "--help"):
            sys.stdout.write(USAGE)
            return 0
        if argv[0] == "--list":
            ws = list_windows()
            emit({"ok": True, "windows": ws},
                 "\n".join("id=%d  %dx%d  @(%d,%d)" % (w["id"], w["width"], w["height"], w["left"], w["top"])
                           for w in ws) or "(ウィンドウ無し)")
            return 0
        if argv[0] == "--restore":
            w = int(argv[1]) if len(argv) > 1 and re.fullmatch(r"\d+", argv[1]) else None
            r = restore_width(w)
            b, before = r["bounds"], r["before"]
            emit({"ok": True, "restored_to": b["width"], "before": before, "bounds": b},
                 "%dpx → %dpx に戻した（id=%d @(%d,%d)）"
                 % (before["width"], b["width"], b["id"], b["left"], b["top"]))
            return 0
        if argv[0] == "--get":
            b = get_bounds()
            emit({"ok": True, "bounds": b},
                 "%dx%d @(%d,%d)" % (b["width"], b["height"], b["left"], b["top"]))
            return 0
        if not re.fullmatch(r"\d+", argv[0]):
            sys.stderr.write(USAGE)
            return 2
        w = int(argv[0])
        h = int(argv[1]) if len(argv) > 1 and re.fullmatch(r"\d+", argv[1]) else None
        b = set_width(w, h)
        ok = b["width"] == w
        emit({"ok": ok, "requested": w, "bounds": b},
             "%dx%d @(%d,%d)%s" % (b["width"], b["height"], b["left"], b["top"],
                                   "" if ok else "  ← 要求 %d に到達せず" % w))
        return 0 if ok else 1
    except HostError as e:
        if as_json:
            print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        else:
            sys.stderr.write("エラー: %s\n" % e)
        return 1


def is_cli_invocation(argv):
    """
    Chrome は host を `<path> chrome-extension://<id>/ --parent-window=<n>` の形で起動する。
    つまり「引数があるか」では CLI と native messaging を区別できない。
    CLI として扱うのは、先頭引数が CLI トークンとして解釈できる場合だけにする。
    """
    if not argv:
        return False
    a = argv[0]
    if a.startswith("chrome-extension://") or a.startswith("--parent-window"):
        return False
    return bool(re.fullmatch(r"\d+", a)) or a in ("--list", "--get", "--restore", "--json", "-h", "--help")


if __name__ == "__main__":
    sys.exit(cli(sys.argv[1:]) if is_cli_invocation(sys.argv[1:]) else (serve() or 0))
