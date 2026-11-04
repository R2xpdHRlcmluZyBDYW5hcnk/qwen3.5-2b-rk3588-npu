"""Print raw measurements, unit conversions, and observed request times."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'evidence'
api = json.loads((root / 'api-verification-summary.json').read_text())
final = json.loads((root / 'final-environment.json').read_text())
management = json.loads((root / 'management-verification.json').read_text())
source_weight_bytes = 4548144832
print('Raw source tensor bytes:', source_weight_bytes)
print('Raw service peak bytes:', final['service_memory_peak_bytes'])
print('Raw minimum MemAvailable KiB:', api['minimum_mem_available_kib'])
print('Raw service swap bytes:', final['service_swap_current_bytes'])
print(f'Source tensor data: {source_weight_bytes / 10**9:.4f} GB / {source_weight_bytes / 2**30:.4f} GiB')
print(f'Service cgroup peak: {final["service_memory_peak_bytes"] / 2**30:.3f} GiB')
print(f'Minimum system MemAvailable: {api["minimum_mem_available_kib"] / 2**20:.3f} GiB')
print(f'Service swap at final sample: {final["service_swap_current_bytes"] / 2**20:.3f} MiB')
print('Observed maximum NPU core loads (%):', api['observed_max_npu_core_load_percent'])
for test in api['tests']:
    print(f'{test["test"]}: {test["seconds"]:.3f} s; {test["answer"]}')
print(f'Abort to stream close: {management["abort"]["seconds_until_stream_closed"]:.3f} s')
print('OOM kills:', final['memory_events']['oom_kill'])
print('Automatic restarts:', final['systemd']['NRestarts'])
