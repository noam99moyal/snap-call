#!/bin/bash
# Runs the Hard computer code from full-cards/game.html through simulated games (macOS: uses osascript's JavaScript).
# Its numbers should match memory.py's for the same players.
cd "$(dirname "$0")"
awk '/\/\/ ---------- Hard computer ----------/{on=1} /\/\/ ---------- Rules ----------/{on=0} on' ../../full-cards/game.html > /tmp/snap-call-hard-block.js
cat harness-head.js /tmp/snap-call-hard-block.js harness-tail.js > /tmp/snap-call-harness.js
osascript -l JavaScript /tmp/snap-call-harness.js
