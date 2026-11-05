"""Exercise the deployed Unix-socket API, including real native cancellation."""
import http.client
import json
import os
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/qwen3.5-2b')
EVIDENCE_DIR = Path(os.environ.get('EVIDENCE_DIR', ROOT / 'evidence'))
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
SOCKET = '/run/qwen3.5-2b/inference.sock'

class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET)

def call(path, body=None):
    conn = Connection('localhost', timeout=60)
    try:
        payload = json.dumps(body).encode() if body is not None else None
        conn.request('POST' if body is not None else 'GET', path, payload,
                     {'Content-Type': 'application/json'})
        response = conn.getresponse()
        return response.status, json.loads(response.read())
    finally:
        conn.close()

def wait_idle():
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, health = call('/health')
        if status == 200 and health['active_requests'] == 0:
            assert health['last_cleared_kv_positions'] == 0, health
            return health
        time.sleep(.1)
    raise AssertionError('worker did not become idle')

body = {'model': 'Qwen3.5-2B', 'messages': [{'role': 'user', 'content':
        '请从1开始逐个数字数到500，每行一个数字，不要省略。'}],
        'max_tokens': 512, 'stream': True, 'enable_thinking': False}
result = {'checked_at_utc': datetime.now(timezone.utc).isoformat()}
conn = Connection('localhost', timeout=90)
conn.request('POST', '/v1/chat/completions', json.dumps(body).encode(),
             {'Content-Type': 'application/json'})
response = conn.getresponse()
assert response.status == 200, response.status
first_content = None
while first_content is None:
    line = response.readline().decode().strip()
    if line.startswith('data: {'):
        chunk = json.loads(line[6:])
        if chunk['choices'][0]['delta'].get('content'):
            first_content = chunk
status, busy = call('/v1/cache/clear', {})
assert status == 409, (status, busy)
start = time.monotonic()
status, aborted = call('/v1/abort', {})
assert status == 200, (status, aborted)
assert aborted['requests'] and aborted['requests'][0]['abort_code'] == 0, aborted
tail = response.read().decode()
conn.close()
assert 'data: [DONE]' in tail, tail
result['abort'] = {'response': aborted, 'seconds_until_stream_closed': time.monotonic()-start,
                   'first_chunk': first_content, 'busy_clear': busy,
                   'idle_after_abort': wait_idle()}
status, cleared = call('/v1/cache/clear', {})
assert status == 200 and cleared['kv_positions'] == 0, (status, cleared)
result['explicit_clear'] = cleared
status, answered = call('/v1/chat/completions', {
    'model': 'Qwen3.5-2B', 'messages': [{'role': 'user', 'content': '法国的首都是哪里？请简短回答。'}],
    'max_tokens': 32, 'enable_thinking': False})
assert status == 200 and '巴黎' in answered['choices'][0]['message']['content'], (status, answered)
result['question_after_abort'] = answered
result['idle_after_success'] = wait_idle()

# A disconnected stream must also stop its worker before freeing the slot.
conn = Connection('localhost', timeout=90)
conn.request('POST', '/v1/chat/completions', json.dumps(body).encode(),
             {'Content-Type': 'application/json'})
response = conn.getresponse()
while True:
    line = response.readline().decode().strip()
    if line.startswith('data: {') and json.loads(line[6:])['choices'][0]['delta'].get('content'):
        break
conn.sock.shutdown(socket.SHUT_RDWR)
response.close()
conn.close()
time.sleep(.3)
result['idle_after_disconnect'] = wait_idle()

# Preprocessing failure must release the worker without retaining history.
status, invalid = call('/v1/chat/completions', {
    'model': 'Qwen3.5-2B', 'messages': [{'role': 'user', 'content': [
        {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,bm90IGFuIGltYWdl'}}]}],
    'enable_thinking': False})
assert status == 500, (status, invalid)
result['invalid_image'] = {'status': status, 'response': invalid, 'idle': wait_idle()}
status, idle_abort = call('/v1/abort', {})
assert status == 200 and idle_abort['status'] == 'idle', (status, idle_abort)
result['idle_abort'] = idle_abort
(EVIDENCE_DIR / 'management-verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
