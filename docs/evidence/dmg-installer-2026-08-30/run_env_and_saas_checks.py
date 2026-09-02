# -*- coding: utf-8 -*-
"""
第 0 パス: 文書の前提になる 2 点を機械的に固定する。
  1. 配布物が /usr/bin/python3 に依存できない理由（Command Line Tools 同梱である証拠）
  2. 拡張に SaaS 連携が「実装されていない」ことの確認（無いことの確認なので網羅的に列挙する）
"""
import json, os, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "out"); os.makedirs(OUT, exist_ok=True)

def run(cmd, shell=False):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                       timeout=60, shell=shell)
    return {"cmd": cmd if isinstance(cmd, str) else " ".join(cmd),
            "rc": p.returncode, "out": p.stdout.strip()[:2000], "err": p.stderr.strip()[:800]}

man = json.load(open(os.path.join(REPO, "extension", "manifest.json")))
dmg = [f for f in os.listdir(os.path.join(REPO, "build")) if f.endswith(".dmg")]
dmg_path = os.path.join(REPO, "build", dmg[0]) if dmg else None

report = {
    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "env": {
        "sw_vers": run(["/usr/bin/sw_vers"])["out"],
        "chrome": run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                       "--version"])["out"],
        "swiftc": run(["/usr/bin/swiftc", "--version"])["out"].splitlines()[:1],
    },
    "python3_is_from_command_line_tools": {
        "otool_L": run(["/usr/bin/otool", "-L", "/usr/bin/python3"])["out"],
        "sys_executable": run(["/usr/bin/python3", "-c",
                               "import sys;print(sys.executable)"])["out"],
        "xcode_select_p": run(["/usr/bin/xcode-select", "-p"])["out"],
        "結論": "/usr/bin/python3 は libxcselect 経由の shim で、実体は "
                "/Library/Developer/CommandLineTools 配下にある。CLT が入っていない Mac では"
                "実行できないので、配布するヘルパーは Python に依存できない",
    },
    "extension_saas_surface": {
        "permissions": man.get("permissions"),
        "optional_permissions": man.get("optional_permissions"),
        "host_permissions": man.get("host_permissions"),
        "content_scripts": man.get("content_scripts"),
        "externally_connectable": man.get("externally_connectable"),
        "web_accessible_resources": man.get("web_accessible_resources"),
        "grep_network_apis": run(
            "grep -nE 'fetch\\(|XMLHttpRequest|WebSocket|externally_connectable|"
            "host_permissions|content_scripts|postMessage' "
            + os.path.join(REPO, "extension") + "/*.js "
            + os.path.join(REPO, "extension") + "/manifest.json || echo '(該当なし)'",
            shell=True)["out"],
        "結論": "ウェブページへ到達する経路（host_permissions / content_scripts / "
                "externally_connectable）も、ネットワーク API の呼び出しも 1 つも無い。"
                "SaaS 連携は設計途中ではなく未着手",
    },
    "extension_id_fixed": json.loads(run([os.path.join(REPO, "tools", "extension_id.py"),
                                          os.path.join(REPO, "extension", "manifest.json"),
                                          "--json"])["out"]),
    "artifact": {
        "dmg": dmg_path,
        "bytes": os.path.getsize(dmg_path) if dmg_path else None,
        "sha256": run(["/usr/bin/shasum", "-a", "256", dmg_path])["out"].split()[0] if dmg_path else None,
        "app_codesign": run(["/usr/bin/codesign", "-dvv",
                             os.path.join(REPO, "build", "VIEWPORT BREAK.app")])["err"],
        "app_archs": run(["/usr/bin/lipo", "-archs",
                          os.path.join(REPO, "build", "VIEWPORT BREAK.app",
                                       "Contents", "MacOS", "viewport-break")])["out"],
    },
    "guard_run_from_dmg": "docs/DMG_DISTRIBUTION_2026-08-30.md §6.2 に実行結果を転記",
}

json.dump(report, open(os.path.join(OUT, "env_and_saas.json"), "w"),
          ensure_ascii=False, indent=2)
print(json.dumps(report, ensure_ascii=False, indent=2)[:1800])
