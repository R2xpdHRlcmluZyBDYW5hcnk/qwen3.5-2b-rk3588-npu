import os
import hashlib
import json
from pathlib import Path
from rkllm.api import RKLLM

root = Path(os.environ.get('BUILD_DIR', '/var/tmp/qwen3.5-2b-build'))
model = root / 'models/Qwen3.5-2B'
assert (model / 'SOURCE_SHA256SUMS').is_file(), 'Official checkpoint download/verification is not complete'
target = root / 'outputs/qwen3.5-2b_fp16_rk3588.rkllm'
llm = RKLLM()
ret = llm.load_huggingface(model=str(model), device='cpu')
assert ret == 0, f'load_huggingface returned {ret}'
print('Building without quantization: do_quantization=False, target=rk3588, cores=3, max_context=4096', flush=True)
ret = llm.build(do_quantization=False, optimization_level=0, target_platform='rk3588', num_npu_core=3, max_context=4096)
print('Unquantized build return code:', ret, flush=True)
assert ret == 0, f'Unquantized build returned {ret}'
ret = llm.export_rkllm(str(target))
assert ret == 0, f'export_rkllm returned {ret}'
with target.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
record = {'source_repo': 'Qwen/Qwen3.5-2B', 'source_revision': '15852e8c16360a2fea060d615a32b45270f8a8fc',
          'toolkit': '1.3.1', 'do_quantization': False, 'optimization_level': 0,
          'target_platform': 'rk3588', 'num_npu_core': 3, 'max_context': 4096,
          'output_file': target.name, 'output_bytes': target.stat().st_size, 'sha256': digest}
(root / 'outputs/qwen35-conversion.json').write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2), flush=True)
