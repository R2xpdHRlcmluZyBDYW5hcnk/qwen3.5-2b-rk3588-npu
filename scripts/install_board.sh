#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_DIR=/opt/qwen3.5-2b
test "$(id -u)" = 0
test "$(uname -m)" = aarch64
test -r /sys/kernel/debug/rknpu/version
cat /sys/kernel/debug/rknpu/version
test -f "$DEPLOY_DIR/models/qwen3.5-2b_fp16_rk3588.rkllm"
test -f "$DEPLOY_DIR/models/qwen3.5_vision_rk3588.rknn"
(cd "$DEPLOY_DIR/models"; sha256sum -c SHA256SUMS)
# Stop a previous deployment before allocating the replacement model.
for unit in qwen3-vl-socket.socket qwen3-vl-socket.service qwen3-vl.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then systemctl disable --now "$unit"; fi
done
systemctl stop qwen3.5-2b-socket.socket qwen3.5-2b-socket.service qwen3.5-2b.service 2>/dev/null || true
if ss -lntH 'sport = :18080' | grep -q .; then
  printf 'Port 18080 is occupied; stop its service before continuing\n' >&2
  exit 2
fi
export DEBIAN_FRONTEND=noninteractive
apt-get --yes --no-install-recommends install curl ca-certificates libstdc++6 libgomp1
mkdir -p "$DEPLOY_DIR"/{tools,python,cache,src/app,runtime/lib,evidence,bin,samples}
cd "$DEPLOY_DIR"
curl -fLsS --retry 4 -o tools/uv.tar.gz https://github.com/astral-sh/uv/releases/download/0.13.7/uv-aarch64-unknown-linux-gnu.tar.gz
printf '%s\n' '71279f8d3c67241e807b9d8db872d1bf541579fb9f08b7d1eb1682196d1e57dc  tools/uv.tar.gz' | sha256sum -c -
tar -xzf tools/uv.tar.gz -C tools
export UV_CACHE_DIR="$DEPLOY_DIR/cache/uv" UV_PYTHON_INSTALL_DIR="$DEPLOY_DIR/python" UV_PYTHON_BIN_DIR="$DEPLOY_DIR/tools"
UV="$DEPLOY_DIR/tools/uv-aarch64-unknown-linux-gnu/uv"
"$UV" python install 3.12.16
test -x api-venv/bin/python || "$UV" venv --python 3.12.16 api-venv
"$UV" pip install --python api-venv/bin/python -r "$SCRIPT_DIR/api-requirements.freeze.txt"
test -e api-venv/bin/qwen3.5-2b || ln -s python api-venv/bin/qwen3.5-2b
server=src/app/fastapi_server_vlm.py
curl -fLsS --retry 4 -o "$server" https://raw.githubusercontent.com/Hanzo-Huang/rkllm-docker/ad016395d68e4fa789e139567b92c2320ba02249/app/fastapi_server_vlm.py
printf '%s\n' "df046479b373c59a194f21632585b3b6e4f1789e02db82199e743326553dc255  $server" | sha256sum -c -
api-venv/bin/python "$SCRIPT_DIR/apply_local_changes.py" "$server"
curl -fLsS --retry 4 -o runtime/lib/librkllmrt.so https://raw.githubusercontent.com/airockchip/rknn-llm/f7390530443bf84f0394255a449d7cbe81e69d1c/rkllm-runtime/Linux/librkllm_api/aarch64/librkllmrt.so
curl -fLsS --retry 4 -o runtime/lib/librknnrt.so https://raw.githubusercontent.com/airockchip/rknn-toolkit2/2c723177a94fac65cbc036d722907ddbc91980cf/rknpu2/runtime/Linux/librknn_api/aarch64/librknnrt.so
printf '%s\n' 'f25e9b099db08aaacd0a3ac62b4697d3951d6ae61ae41ea09f6702cfa89eb32c  runtime/lib/librkllmrt.so' '4b6cc575bedf8952b13db4b1190fa3b3d2ac213f00be774ff6ccd19d651970c0  runtime/lib/librknnrt.so' | sha256sum -c -
for library in librkllmrt.so librknnrt.so; do
  target="$DEPLOY_DIR/runtime/lib/$library"
  if test -e "/usr/lib/$library" || test -L "/usr/lib/$library"; then
    if test "$(readlink -f "/usr/lib/$library")" != "$target"; then
      printf 'Existing runtime must be reviewed: /usr/lib/%s\n' "$library" >&2
      exit 2
    fi
  else
    ln -s "$target" "/usr/lib/$library"
  fi
done
for unit in qwen3.5-2b.service qwen3.5-2b-socket.service qwen3.5-2b-socket.socket; do
  install -m 644 "$SCRIPT_DIR/$unit" "/etc/systemd/system/$unit"
done
install -m 644 "$SCRIPT_DIR/verify_api.py" "$SCRIPT_DIR/verify_management.py" bin/
systemd-analyze verify /etc/systemd/system/qwen3.5-2b.service /etc/systemd/system/qwen3.5-2b-socket.service /etc/systemd/system/qwen3.5-2b-socket.socket
systemctl daemon-reload
systemctl start qwen3.5-2b.service qwen3.5-2b-socket.socket
for attempt in $(seq 1 240); do
  if curl -fsS --max-time 2 http://127.0.0.1:18080/health; then
    printf '\n'
    curl -fsS --unix-socket /run/qwen3.5-2b/inference.sock http://localhost/v1/models
    printf '\n'
    exit 0
  fi
  if test "$(systemctl show qwen3.5-2b.service -p NRestarts --value)" -gt 0; then break; fi
  sleep 2
done
journalctl -u qwen3.5-2b.service --no-pager -n 80
exit 1
