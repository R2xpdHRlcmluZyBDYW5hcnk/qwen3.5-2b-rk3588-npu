#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
precision=${1:-fp16}
if [[ $# -gt 1 || ( "$precision" != fp16 && "$precision" != w8a8 ) ]]; then
  printf 'Usage: %s [fp16|w8a8]\n' "$0" >&2
  exit 2
fi
export BUILD_DIR=${BUILD_DIR:-/var/tmp/qwen3.5-2b-build}
mkdir -p "$BUILD_DIR"/{tools,models,outputs,logs,cache}
cd "$BUILD_DIR"
export BUILD_DIR=$PWD
output_dir="$BUILD_DIR/outputs"
if [[ "$precision" == w8a8 ]]; then output_dir="$output_dir/w8a8"; fi
export UV_CACHE_DIR="$BUILD_DIR/cache/uv"
export UV_PYTHON_INSTALL_DIR="$BUILD_DIR/python"
export UV_PYTHON_BIN_DIR="$BUILD_DIR/tools"
export UV_HTTP_TIMEOUT=180 BUILD_CUDA_EXT=0 CUDA_VISIBLE_DEVICES=''
export OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 PYTHONUNBUFFERED=1
curl -fLsS --retry 4 -o tools/uv.tar.gz https://github.com/astral-sh/uv/releases/download/0.13.7/uv-x86_64-unknown-linux-gnu.tar.gz
printf '%s\n' 'c5221ff41b7892bfc223543883600125f6a47fe845093e0f5bdff4f359196d83  tools/uv.tar.gz' | sha256sum -c -
tar -xzf tools/uv.tar.gz -C tools
UV="$BUILD_DIR/tools/uv-x86_64-unknown-linux-gnu/uv"
"$UV" python install 3.12.16
for name in llm-venv vision-venv; do
  test -x "$BUILD_DIR/$name/bin/python" || "$UV" venv --python 3.12.16 "$BUILD_DIR/$name"
done
if ! test -d sdk/.git; then
  git clone --depth 1 --filter=blob:none --sparse --branch release-v1.3.1 https://github.com/airockchip/rknn-llm.git sdk
fi
test "$(git -C sdk rev-parse HEAD)" = f7390530443bf84f0394255a449d7cbe81e69d1c
git -C sdk sparse-checkout set --no-cone '/examples/multimodal_model_demo/export/' '/rkllm-toolkit/packages/rkllm_toolkit-1.3.1-cp312-cp312-linux_x86_64.whl'
"$UV" pip install --python llm-venv/bin/python torch==2.6.0+cpu torchvision==0.21.0+cpu --index-url https://download.pytorch.org/whl/cpu
"$UV" pip install --python llm-venv/bin/python -c "$SCRIPT_DIR/llm-constraints.txt" ./sdk/rkllm-toolkit/packages/rkllm_toolkit-1.3.1-cp312-cp312-linux_x86_64.whl onnx==1.18.0 transformers==5.8.0
"$UV" pip install --python vision-venv/bin/python torch==2.4.0+cpu torchvision==0.19.0+cpu --index-url https://download.pytorch.org/whl/cpu
"$UV" pip install --python vision-venv/bin/python -c "$SCRIPT_DIR/vision-requirements.freeze.txt" rknn-toolkit2==2.5.0 transformers==4.57.0 accelerate==1.5.2 onnx==1.18.0
bash "$SCRIPT_DIR/download_official.sh"
export HF_HOME="$BUILD_DIR/cache/huggingface" HF_HUB_OFFLINE=1
language_log=logs/language-conversion.log
if [[ "$precision" == w8a8 ]]; then language_log=logs/language-conversion-w8a8.log; fi
"$BUILD_DIR/llm-venv/bin/python" "$SCRIPT_DIR/convert_language.py" "$precision" 2>&1 | tee "$language_log"
cd "$BUILD_DIR/sdk/examples/multimodal_model_demo"
"$BUILD_DIR/llm-venv/bin/python" export/export_vision.py --path "$BUILD_DIR/models/Qwen3.5-2B" --model_name qwen3.5 --height 448 --width 448 --device cpu 2>&1 | tee "$BUILD_DIR/logs/vision-export.log"
"$BUILD_DIR/vision-venv/bin/python" export/export_vision_rknn.py --path ./onnx/qwen3.5_vision.onnx --model_name qwen3.5 --height 448 --width 448 --target-platform rk3588 2>&1 | tee "$BUILD_DIR/logs/vision-conversion.log"
cp rknn/qwen3.5_vision_rk3588.rknn "$output_dir/"
cd "$output_dir"
sha256sum "qwen3.5-2b_${precision}_rk3588.rkllm" qwen3.5_vision_rk3588.rknn > SHA256SUMS
cat SHA256SUMS
