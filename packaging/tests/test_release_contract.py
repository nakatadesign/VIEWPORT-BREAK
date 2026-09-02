#!/usr/bin/env python3
"""1.0.2 配布候補の契約と、隔離したインストールライフサイクルを検証する。"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
APP = REPO / "build" / "VIEWPORT BREAK.app"
EXE = APP / "Contents" / "MacOS" / "viewport-break"
DMG = REPO / "build" / "VIEWPORT BREAK 1.0.2.dmg"
CHECKSUM = REPO / "build" / "VIEWPORT BREAK 1.0.2.dmg.sha256"
PREFLIGHT = REPO / "build" / "VIEWPORT BREAK 1.0.2 - BEFORE OPENING.txt"
HOST_NAME = "com.nanago.viewport_deck"
EXT_ID = "ejlimgikbnaihoigbcmelaadniiminfj"


def run_json(args: list[str], env: dict[str, str] | None = None) -> dict:
    result = subprocess.run(args, check=False, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed rc={result.returncode}: {args}\nstdout={result.stdout}\nstderr={result.stderr}"
        )
    return json.loads(result.stdout)


def run(args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=False, capture_output=True, text=True, env=env)


class ReleaseContractTest(unittest.TestCase):
    def test_versions_and_fixed_extension_id(self) -> None:
        self.assertTrue(EXE.is_file(), "先に packaging/build_dmg.sh を実行する")
        with (APP / "Contents" / "Info.plist").open("rb") as f:
            plist = plistlib.load(f)
        self.assertEqual(plist["CFBundleShortVersionString"], "1.0.2")
        self.assertEqual(plist["CFBundleVersion"], "1.0.2")

        extension_manifest = json.loads((REPO / "extension" / "manifest.json").read_text())
        self.assertEqual(extension_manifest["version"], "1.4.1")
        self.assertEqual(extension_manifest["permissions"], ["nativeMessaging"])

        version = run_json([str(EXE), "--version", "--json"])
        self.assertEqual(version["version"], "2.0.1")
        self.assertEqual(version["extension_id"], EXT_ID)

        id_check = run_json(
            [str(REPO / "tools" / "extension_id.py"), str(REPO / "extension" / "manifest.json"), "--json"]
        )
        self.assertTrue(id_check["ok"])
        self.assertEqual(id_check["extension_id"], EXT_ID)

    def test_dmg_preflight_matches_artifact(self) -> None:
        for path in (DMG, CHECKSUM, PREFLIGHT):
            self.assertTrue(path.is_file(), f"生成物が無い: {path}")
        # CHECKSUM はビルド記録として残す内部用ダイジェスト。配布物へは載せない。
        digest = hashlib.sha256(DMG.read_bytes()).hexdigest()
        checksum_text = CHECKSUM.read_text().strip()
        self.assertEqual(checksum_text, f"{digest}  {DMG.name}")

        preflight = PREFLIGHT.read_text()
        self.assertIn("Finderからドラッグ", preflight)
        self.assertNotIn("~/Downloads/", preflight)
        # 購入者向けの SHA-256 照合は 2026-08-31 のオーナー決裁で廃止した。
        self.assertNotIn(digest, preflight)

    def test_buyer_facing_docs_have_no_checksum_verification(self) -> None:
        """購入者が読む配布物に SHA-256 照合の記述が復活していないこと。"""
        banned = ("SHA-256", "SHA256", "sha256", "shasum", "ハッシュ")
        targets = [PREFLIGHT, *sorted((REPO / "packaging" / "dmg").glob("*.txt*"))]
        for path in targets:
            self.assertTrue(path.is_file(), f"配布物が無い: {path}")
            text = path.read_text()
            for word in banned:
                self.assertNotIn(word, text, f"{path.name} に「{word}」が残っている")

    def test_isolated_install_reinstall_and_uninstall(self) -> None:
        self.assertTrue(EXE.is_file(), "先に packaging/build_dmg.sh を実行する")
        with tempfile.TemporaryDirectory(prefix="viewport-break-e2e-") as tmp:
            app_support = Path(tmp) / "Application Support"
            chrome = app_support / "Google" / "Chrome"
            chrome.mkdir(parents=True)

            # 1.0.0 が誤って置いた全ブラウザの manifest を再現する。
            legacy_roots = [
                "Google/Chrome Beta", "Google/Chrome Canary", "Chromium",
                "BraveSoftware/Brave-Browser", "Microsoft Edge", "Vivaldi", "Arc/User Data",
            ]
            legacy_manifests = []
            for root in legacy_roots:
                legacy_nm = app_support / root / "NativeMessagingHosts"
                legacy_nm.mkdir(parents=True)
                manifest_path = legacy_nm / f"{HOST_NAME}.json"
                manifest_path.write_text("{}")
                legacy_manifests.append(manifest_path)

            env = os.environ.copy()
            env["VIEWPORT_BREAK_TEST_APP_SUPPORT"] = str(app_support)

            installed = run_json([str(EXE), "--install", "--json"], env=env)
            self.assertTrue(installed["ok"])
            self.assertTrue(all(not path.exists() for path in legacy_manifests))

            chrome_manifest = chrome / "NativeMessagingHosts" / f"{HOST_NAME}.json"
            self.assertTrue(chrome_manifest.is_file())
            manifest = json.loads(chrome_manifest.read_text())
            self.assertEqual(manifest["path"], str(EXE))
            self.assertEqual(manifest["allowed_origins"], [f"chrome-extension://{EXT_ID}/"])
            all_manifests = list(app_support.glob(f"**/NativeMessagingHosts/{HOST_NAME}.json"))
            self.assertEqual(all_manifests, [chrome_manifest])

            extension_dir = app_support / "VIEWPORT BREAK" / "extension"
            self.assertTrue((extension_dir / "manifest.json").is_file())

            # 古い余剰ファイルは再インストールの原子的交換で残らない。
            stale = extension_dir / "stale-from-old-version.txt"
            stale.write_text("old")
            reinstalled = run_json([str(EXE), "--install", "--json"], env=env)
            self.assertTrue(reinstalled["ok"])
            self.assertFalse(stale.exists())
            leftovers = list((app_support / "VIEWPORT BREAK").glob(".extension.installing-*"))
            self.assertEqual(leftovers, [])

            removed = run_json([str(EXE), "--uninstall", "--json"], env=env)
            self.assertTrue(removed["ok"])
            self.assertFalse(chrome_manifest.exists())
            self.assertFalse((app_support / "VIEWPORT BREAK").exists())

    def test_install_without_chrome_and_uninstall_failure_are_reported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="viewport-break-errors-") as tmp:
            app_support = Path(tmp) / "Application Support"
            app_support.mkdir()
            env = os.environ.copy()
            env["VIEWPORT_BREAK_TEST_APP_SUPPORT"] = str(app_support)

            missing_chrome = run([str(EXE), "--install", "--json"], env=env)
            self.assertEqual(missing_chrome.returncode, 1)
            self.assertFalse(json.loads(missing_chrome.stdout)["ok"])

            # 親を読み取り専用にして、展開済みディレクトリの削除失敗を再現する。
            app_support.chmod(0o555)
            try:
                failed_remove = run([str(EXE), "--uninstall", "--json"], env=env)
            finally:
                app_support.chmod(0o755)
            self.assertEqual(failed_remove.returncode, 1)
            failure = json.loads(failed_remove.stdout)
            self.assertFalse(failure["ok"])
            self.assertTrue(failure["failures"])

            removed = run_json([str(EXE), "--uninstall", "--json"], env=env)
            self.assertTrue(removed["ok"])


if __name__ == "__main__":
    unittest.main()
