#!/usr/bin/env bash
# Runs the complete ForgeSentry demo locally, start to finish.
# Usage: bash demo/run_full_demo.sh   (run from the repo root)
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH=.

echo "############################################"
echo "# STAGE 0: build the fixture packages"
echo "############################################"
timeout 30 python3 demo/make_fixtures.py

STAGE_DIR=$(mktemp -d)
cp package.json index.js "$STAGE_DIR/"
cp -r vendor demo "$STAGE_DIR/"
sed -i.bak 's/left-padz-1.0.0/left-padz-1.0.1/' "$STAGE_DIR/package.json" && rm -f "$STAGE_DIR/package.json.bak"

echo
echo "############################################"
echo "# STAGE 1: the attack, with NO protection"
echo "############################################"
pushd "$STAGE_DIR" >/dev/null
setsid nohup python3 demo/listener.py >listener_stdout.log 2>&1 < /dev/null &
echo $! > listener.pid
popd >/dev/null
sleep 1
( cd "$STAGE_DIR" && timeout 30 env FAKE_SECRET=demo-not-a-real-key-123 npm install --no-audit --no-fund --offline >/dev/null 2>&1 )
sleep 1
echo "Attacker listener received:"
cat "$STAGE_DIR/listener.log" 2>/dev/null || echo "  (nothing)"
kill "$(cat "$STAGE_DIR/listener.pid")" 2>/dev/null || true

echo
echo "############################################"
echo "# STAGE 2: ForgeSentry scans the PR"
echo "############################################"
set +e
timeout 30 python3 -m forgesentry.main . vendor/left-padz-1.0.0.tgz vendor/left-padz-1.0.1.tgz
CHECK_EXIT=$?
set -e
echo
echo "GitHub check would be: $([ $CHECK_EXIT -ne 0 ] && echo FAILING || echo PASSING)"

echo
echo "############################################"
echo "# STAGE 3: maintainer runs /shield fix"
echo "############################################"
python3 -c "
from forgesentry.patcher import make_patch, validate_patch
orig = open('.github/workflows/ci.yml').read()
patched = make_patch('.github/workflows/ci.yml', 'build')
ok, reason = validate_patch(orig, patched)
print('Generated patch is valid:', ok, '--', reason)
open('/tmp/forgesentry_fixed_ci.yml', 'w').write(patched)
print('Fixed workflow written to /tmp/forgesentry_fixed_ci.yml')
"

echo
echo "############################################"
echo "# STAGE 4: replay the attack against the fix"
echo "############################################"
rm -rf "$STAGE_DIR/node_modules" "$STAGE_DIR/listener.log" "$STAGE_DIR/package-lock.json"
pushd "$STAGE_DIR" >/dev/null
setsid nohup python3 demo/listener.py >listener_stdout.log 2>&1 < /dev/null &
echo $! > listener.pid
popd >/dev/null
sleep 1
( cd "$STAGE_DIR" && timeout 30 env FAKE_SECRET=demo-not-a-real-key-123 npm install --ignore-scripts --no-audit --no-fund --offline >/dev/null 2>&1 )
sleep 1
echo "Attacker listener received:"
cat "$STAGE_DIR/listener.log" 2>/dev/null || echo "  (nothing -- attack blocked)"
kill "$(cat "$STAGE_DIR/listener.pid")" 2>/dev/null || true

rm -rf "$STAGE_DIR"
echo
echo "############################################"
echo "# DEMO COMPLETE"
echo "############################################"
