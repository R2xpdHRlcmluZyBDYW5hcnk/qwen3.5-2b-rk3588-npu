#!/usr/bin/env bash
set -eu
build=${BUILD_DIR:-/var/tmp/qwen3.5-2b-build}
model="$build/models/Qwen3.5-2B"
mkdir -p "$model"
cd "$model"
base=https://huggingface.co/Qwen/Qwen3.5-2B/resolve/15852e8c16360a2fea060d615a32b45270f8a8fc
for name in config.json preprocessor_config.json video_preprocessor_config.json chat_template.jinja tokenizer.json tokenizer_config.json merges.txt vocab.json README.md LICENSE model.safetensors.index.json; do
  curl --fail --silent --show-error --location --retry 4 --connect-timeout 20 --max-time 180 --output "$name" "$base/$name"
  printf 'Fetched official Qwen3.5 file: %s\n' "$name"
done
for attempt in $(seq 1 12); do
  printf 'Qwen3.5 checkpoint download attempt %s\n' "$attempt"
  if curl --fail --silent --show-error --location --connect-timeout 20 --max-time 1200 --continue-at - --output model.safetensors-00001-of-00001.safetensors "$base/model.safetensors-00001-of-00001.safetensors"; then
    printf '%s\n' 'aa33250c4fc64891ddfaba3a314fd9542ea371843c387178b425fbcc5ed680b1  model.safetensors-00001-of-00001.safetensors' | sha256sum -c -
    sha256sum *.json *.txt *.jinja *.safetensors > SOURCE_SHA256SUMS
    exit 0
  fi
  sleep 3
done
exit 1
