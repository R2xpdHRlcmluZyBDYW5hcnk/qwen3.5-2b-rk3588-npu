import argparse
import hashlib
import json
import os
from pathlib import Path

from rkllm.api import RKLLM


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("precision", nargs="?", choices=("fp16", "w8a8"), default="fp16")
    precision = parser.parse_args().precision
    root = Path(os.environ.get("BUILD_DIR", "/var/tmp/qwen3.5-2b-build"))
    model = root / "models/Qwen3.5-2B"
    if not (model / "SOURCE_SHA256SUMS").is_file():
        raise SystemExit("Official checkpoint download/verification is not complete")

    output_dir = root / "outputs"
    if precision == "w8a8":
        output_dir /= "w8a8"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"qwen3.5-2b_{precision}_rk3588.rkllm"
    settings = {
        "do_quantization": precision == "w8a8",
        "optimization_level": 1 if precision == "w8a8" else 0,
        "target_platform": "rk3588",
        "num_npu_core": 3,
        "max_context": 4096,
    }
    quantization = {}
    if precision == "w8a8":
        calibration = Path(__file__).with_name("w8a8_calibration.json")
        quantization = {
            "quantized_dtype": "w8a8",
            "quantized_algorithm": "normal",
            "dataset": str(calibration),
        }

    llm = RKLLM()
    ret = llm.load_huggingface(model=str(model), device="cpu")
    if ret != 0:
        raise SystemExit(f"load_huggingface returned {ret}")
    print(f"Building {precision} with {settings}", flush=True)
    ret = llm.build(**settings, **quantization)
    if ret != 0:
        raise SystemExit(f"build returned {ret}")
    ret = llm.export_rkllm(str(target))
    if ret != 0:
        raise SystemExit(f"export_rkllm returned {ret}")

    with target.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    record = {
        "source_repo": "Qwen/Qwen3.5-2B",
        "source_revision": "15852e8c16360a2fea060d615a32b45270f8a8fc",
        "toolkit": "1.3.1",
        **settings,
        "output_file": target.name,
        "output_bytes": target.stat().st_size,
        "sha256": digest,
    }
    if precision == "w8a8":
        record.update(
            quantized_dtype=quantization["quantized_dtype"],
            quantized_algorithm=quantization["quantized_algorithm"],
            calibration_file=calibration.name,
            calibration_sha256=hashlib.sha256(calibration.read_bytes()).hexdigest(),
        )
    (output_dir / "qwen35-conversion.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2), flush=True)


if __name__ == "__main__":
    main()
