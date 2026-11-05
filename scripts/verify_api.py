import base64
import http.client
import json
import os
import re
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/qwen3.5-2b')
EVIDENCE_DIR = Path(os.environ.get('EVIDENCE_DIR', ROOT / 'evidence'))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SOCKET_PATH = '/run/qwen3.5-2b/inference.sock'

class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET_PATH)

def request(path, body=None):
    conn = UnixConnection('localhost', timeout=300)
    try:
        payload = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        conn.request('GET' if payload is None else 'POST', path, body=payload,
                     headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        data = response.read().decode('utf-8')
        assert response.status == 200, (response.status, data)
        return json.loads(data)
    finally:
        conn.close()

samples = []
stop = threading.Event()

def monitor():
    while not stop.is_set():
        raw = Path('/sys/kernel/debug/rknpu/load').read_text().strip()
        meminfo = dict(re.findall(r'^(\w+):\s*(\d+)', Path('/proc/meminfo').read_text(), flags=re.M))
        cg = Path('/sys/fs/cgroup/system.slice/qwen3.5-2b.service/memory.current')
        samples.append({'monotonic': time.monotonic(), 'npu_load': raw,
                        'mem_available_kib': int(meminfo['MemAvailable']),
                        'swap_free_kib': int(meminfo['SwapFree']),
                        'service_memory_bytes': int(cg.read_text()) if cg.exists() else None})
        stop.wait(0.25)

print('Health:', json.dumps(request('/health'), ensure_ascii=False), flush=True)
thread = threading.Thread(target=monitor, daemon=True)
thread.start()
tests = [
    ('text', None, '请用一句话说明什么是太阳系。'),
    ('image_a', ROOT / 'samples/demo.jpg', '请用一句话描述图片中的主体。'),
    ('image_b', ROOT / 'samples/buffalo.jpg', '图中主要是什么动物？请用中文简短回答。'),
    ('image_a_again', ROOT / 'samples/demo.jpg', '宇航员手中拿着什么？请用中文简短回答。'),
]
results = []
try:
    for name, image, prompt in tests:
        content = [{'type': 'text', 'text': prompt}]
        if image:
            content.append({'type': 'image_url', 'image_url': {
                'url': 'data:image/jpeg;base64,' + base64.b64encode(image.read_bytes()).decode('ascii')}})
        body = {'model': 'Qwen3.5-2B', 'messages': [{'role': 'user', 'content': content}],
                'stream': False, 'max_tokens': 128, 'temperature': 0.1, 'enable_thinking': False}
        start = time.monotonic()
        response = request('/v1/chat/completions', body)
        elapsed = time.monotonic() - start
        answer = response['choices'][0]['message']['content']
        assert answer and answer.strip(), response
        health = request('/health')
        assert health['last_cleared_kv_positions'] == 0, health
        result = {'test': name, 'prompt': prompt, 'seconds': elapsed, 'response': response,
                  'health_after_request': health}
        results.append(result)
        (EVIDENCE_DIR / f'{name}-response.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
finally:
    stop.set()
    thread.join()
    (EVIDENCE_DIR / 'api-load-samples.json').write_text(json.dumps(samples, ensure_ascii=False, indent=2))

max_load = [0, 0, 0]
for sample in samples:
    for core, value in re.findall(r'Core(\d+):\s*(\d+)%', sample['npu_load']):
        max_load[int(core)] = max(max_load[int(core)], int(value))
peak_file = Path('/sys/fs/cgroup/system.slice/qwen3.5-2b.service/memory.peak')
summary = {
    'checked_at_utc': datetime.now(timezone.utc).isoformat(),
    'tests': [{'test': item['test'], 'seconds': item['seconds'],
               'answer': item['response']['choices'][0]['message']['content']} for item in results],
    'observed_max_npu_core_load_percent': max_load,
    'minimum_mem_available_kib': min(item['mem_available_kib'] for item in samples),
    'minimum_swap_free_kib': min(item['swap_free_kib'] for item in samples),
    'service_cgroup_peak_memory_bytes': int(peak_file.read_text()) if peak_file.exists() else None,
}
(EVIDENCE_DIR / 'api-verification-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
print('SUMMARY', json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
assert all(value > 0 for value in max_load), max_load
