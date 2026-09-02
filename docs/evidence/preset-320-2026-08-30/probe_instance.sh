#!/bin/bash
# 使い捨て Chrome を別 user-data-dir で起動し、AppleScript がどちらの
# インスタンスを掴むかを --list の結果で判定する（読み取りのみ）。
set -u
SCRATCH="/private/tmp/claude-501/-Users-macmini-Projects/c9e5f2cb-c90f-4d68-b0a4-9d54f0ca1736/scratchpad/vd-probe"
rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
echo "--- before ---"
/usr/bin/python3 /Users/macmini/Projects/viewport-deck/extension/host/viewport_deck_host.py --list --json
"$CHROME" --user-data-dir="$SCRATCH/profile" --remote-debugging-port=9361 \
  --no-first-run --no-default-browser-check --window-size=901,901 --window-position=700,120 \
  about:blank >/dev/null 2>&1 &
CHILD=$!
for i in $(seq 1 60); do
  curl -s --max-time 1 http://127.0.0.1:9361/json/version >/dev/null 2>&1 && break
  sleep 0.5
done
echo "--- after (disposable pid=$CHILD) ---"
/usr/bin/python3 /Users/macmini/Projects/viewport-deck/extension/host/viewport_deck_host.py --list --json
echo "--- cdp bounds of disposable ---"
curl -s http://127.0.0.1:9361/json/version
echo
kill "$CHILD" 2>/dev/null
sleep 2
pkill -f "user-data-dir=$SCRATCH/profile" 2>/dev/null
echo "--- cleaned ---"
