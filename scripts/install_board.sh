#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEPLOY_DIR=/opt/qwen3.5-2b
precision=${1:-fp16}
mode=${2:-}
if [[ $# -gt 2 || ( "$precision" != fp16 && "$precision" != w8a8 ) ||
      ( -n "$mode" && "$mode" != --reuse-runtime ) ]]; then
  printf 'Usage: %s [fp16|w8a8] [--reuse-runtime]\n' "$0" >&2
  exit 2
fi
language_model="qwen3.5-2b_${precision}_rk3588.rkllm"
vision_model=qwen3.5_vision_rk3588.rknn
context_length=${QWEN_CONTEXT_LENGTH:-2048}
if ! [[ "$context_length" =~ ^[1-9][0-9]{2,3}$ ]] || (( context_length < 512 || context_length > 4096 )); then
  printf 'QWEN_CONTEXT_LENGTH must be an integer from 512 to 4096\n' >&2
  exit 2
fi
test "$(id -u)" = 0
test "$(uname -m)" = aarch64
test -r /sys/kernel/debug/rknpu/version
cat /sys/kernel/debug/rknpu/version
(
  cd "$DEPLOY_DIR/models"
  for model in "$language_model" "$vision_model"; do
    if ! awk -v model="$model" '$2 == model { found = 1 } END { exit !found }' SHA256SUMS; then
      printf 'Missing checksum for %s\n' "$model" >&2
      exit 2
    fi
  done
  sha256sum --strict -c SHA256SUMS
)
if [[ "$mode" == --reuse-runtime ]]; then
  test -x "$DEPLOY_DIR/api-venv/bin/qwen3.5-2b"
  test -r "$DEPLOY_DIR/src/app/fastapi_server_vlm.py"
  test -r "$DEPLOY_DIR/runtime/lib/librkllmrt.so"
  test -r "$DEPLOY_DIR/runtime/lib/librknnrt.so"
fi
# Stop a previous deployment before allocating the replacement model.
if [[ "$mode" != --reuse-runtime ]]; then
  for unit in qwen3-vl-socket.socket qwen3-vl-socket.service qwen3-vl.service; do
    if systemctl cat "$unit" >/dev/null 2>&1; then systemctl disable --now "$unit"; fi
  done
fi
for unit in qwen3.5-2b-socket.socket qwen3.5-2b-socket.service qwen3.5-2b.service; do
  if systemctl cat "$unit" >/dev/null 2>&1; then systemctl stop "$unit"; fi
done
if ss -lntH 'sport = :18080' | grep -q .; then
  printf 'Port 18080 is occupied; stop its service before continuing\n' >&2
  exit 2
fi
cd "$DEPLOY_DIR"
install_runtime() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get --yes --no-install-recommends install curl ca-certificates libstdc++6 libgomp1
  mkdir -p "$DEPLOY_DIR"/{tools,python,cache,src/app,runtime/lib,evidence,bin,samples}
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
}
if [[ "$mode" != --reuse-runtime ]]; then install_runtime; fi
for unit in qwen3.5-2b.service qwen3.5-2b-socket.service qwen3.5-2b-socket.socket; do
  install -m 644 "$SCRIPT_DIR/$unit" "/etc/systemd/system/$unit"
done
if [[ "$mode" != --reuse-runtime ]]; then
  install -m 644 "$SCRIPT_DIR/verify_api.py" "$SCRIPT_DIR/verify_management.py" bin/
fi
model_env=$(mktemp "$DEPLOY_DIR/model.env.XXXXXX")
printf 'QWEN_RKLLM_MODEL=%s/models/%s\nQWEN_CONTEXT_LENGTH=%s\n' "$DEPLOY_DIR" "$language_model" "$context_length" > "$model_env"
chmod 644 "$model_env"
mv -fT "$model_env" "$DEPLOY_DIR/model.env"
systemd-analyze verify /etc/systemd/system/qwen3.5-2b.service /etc/systemd/system/qwen3.5-2b-socket.service /etc/systemd/system/qwen3.5-2b-socket.socket
systemctl daemon-reload
systemctl start qwen3.5-2b.service qwen3.5-2b-socket.socket
for attempt in $(seq 1 240); do
  if curl -fsS --max-time 2 http://127.0.0.1:18080/health 2>/dev/null; then
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
