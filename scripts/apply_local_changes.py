"""Apply local stateless/management changes to the exact upstream version.

This file contains only local additions and edit coordinates. It does not
include or license the upstream server. Obtain it from its original author.
"""
import hashlib
import sys
from pathlib import Path

SOURCE_SHA256 = "df046479b373c59a194f21632585b3b6e4f1789e02db82199e743326553dc255"
LIFECYCLE_SHA256 = 'ef1e519fad3608d57415aefcb0f28914f5d3a08c1863a06945ad5db2e5ba84a2'
RESULT_SHA256 = 'f84c72587a9a5eaf969c951a6fb2215ca09579f0bd03c2bbad10efd4208799e5'
EDITS = [(881, 881, '        self.cancel_requested = threading.Event()\n'), (928, 928, '        self.control_lock = threading.Lock()\n        self.active_request_id = None\n        self.last_cache_positions = None\n'), (1009, 1009, '        self.lib.rkllm_abort.argtypes = [ctypes.c_void_p]\n        self.lib.rkllm_abort.restype = ctypes.c_int\n        self.lib.rkllm_is_running.argtypes = [ctypes.c_void_p]\n        self.lib.rkllm_is_running.restype = ctypes.c_int\n        self.lib.rkllm_get_kv_cache_size.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]\n        self.lib.rkllm_get_kv_cache_size.restype = ctypes.c_int\n'), (1024, 1025, ''), (1027, 1028, ''), (1112, 1115, '            try:\n                self.clear_cache()\n                if not state.cancel_requested.is_set():\n                    with self.control_lock:\n                        self.active_request_id = request_id\n                    ret = self.lib.rkllm_run(\n                        self.handle,\n                        ctypes.byref(input_data),\n                        ctypes.byref(infer_params),\n                        ctypes.cast(request_id_buffer, ctypes.c_void_p),\n                    )\n                    if state.cancel_requested.is_set():\n                        state.error = None\n                        state.finish_reason = "stop"\n                    elif ret != 0 and not state.error:\n                        state.error = f"rkllm_run failed with code {ret}"\n            finally:\n                with self.control_lock:\n                    self.active_request_id = None\n                # Clear after success, native error, or cancellation, before\n                # advertising completion or releasing the inference slot.\n                try:\n                    self.clear_cache()\n                except Exception as error:\n                    state.error = str(error)\n'), (1116, 1126, ''), (1127, 1127, '\n    def clear_cache(self) -> int:\n        ret = self.lib.rkllm_clear_kv_cache(self.handle, 0, None, None)\n        if ret != 0:\n            raise RuntimeError(f"rkllm_clear_kv_cache failed with code {ret}")\n        positions = ctypes.c_int(-1)  # This deployment uses one batch.\n        ret = self.lib.rkllm_get_kv_cache_size(self.handle, ctypes.byref(positions))\n        if ret != 0 or positions.value != 0:\n            raise RuntimeError(f"KV cache verification failed: ret={ret}, positions={positions.value}")\n        self.last_cache_positions = positions.value\n        return positions.value\n\n    def cancel(self, request_id: str, state: InferenceState) -> dict:\n        state.cancel_requested.set()\n        deadline = time.monotonic() + 10\n        abort_code = None\n        while not state.completed.is_set() and time.monotonic() < deadline:\n            with self.control_lock:\n                if self.active_request_id == request_id:\n                    abort_code = self.lib.rkllm_abort(self.handle)\n                    if abort_code != 0:\n                        raise RuntimeError(f"rkllm_abort failed with code {abort_code}")\n            # Also cover cancellation in the small interval between assigning\n            # the active request and entering the native rkllm_run call.\n            state.completed.wait(0.01)\n        return {"request_id": request_id, "abort_code": abort_code,\n                "status": "cancelled" if state.completed.is_set() else "cancelling"}\n'), (1371, 1371, 'def finish_request(request_id: str, future) -> None:\n    """Keep the slot and callback state alive until the worker has stopped."""\n    state = request_states.get(request_id)\n    if state and not state.completed.is_set():\n        state.cancel_requested.set()\n        executor.submit(runtime.llm.cancel, request_id, state)\n\n    def cleanup(_):\n        request_states.pop(request_id, None)\n        release_request_slot()\n\n    future.add_done_callback(cleanup)\n\n\n'), (1404, 1404, '    future = None\n'), (1414, 1415, '        future = executor.submit(\n'), (1478, 1480, '        if future is not None:\n            finish_request(request_id, future)\n        else:\n            request_states.pop(request_id, None)\n            release_request_slot()\n'), (1523, 1523, '        for request_id, state in list(request_states.items()):\n            await asyncio.to_thread(runtime.llm.cancel, request_id, state)\n        if executor:\n            await asyncio.to_thread(executor.shutdown, wait=True)\n'), (1524, 1526, ''), (1578, 1578, '        "conversation_history": "client_managed",\n        "kv_policy": "clear_before_and_after_each_request",\n        "last_cleared_kv_positions": runtime.llm.last_cache_positions if runtime else None,\n'), (1579, 1579, '\n\n@app.post("/v1/abort")\nasync def abort_generation():\n    if runtime is None:\n        raise HTTPException(status_code=503, detail="VLM runtime is not initialized")\n    targets = [(key, value) for key, value in list(request_states.items())\n               if not value.completed.is_set()]\n    for _, state in targets:\n        state.cancel_requested.set()\n    results = [await asyncio.to_thread(runtime.llm.cancel, key, state)\n               for key, state in targets]\n    return {"status": "idle" if not results else "abort_requested", "requests": results}\n\n\n@app.post("/v1/cache/clear")\nasync def clear_conversation_cache():\n    if runtime is None:\n        raise HTTPException(status_code=503, detail="VLM runtime is not initialized")\n    if active_requests or not runtime.llm.lock.acquire(blocking=False):\n        raise HTTPException(status_code=409, detail="Inference busy; abort and wait for idle first")\n    try:\n        return {"status": "cleared", "kv_positions": runtime.llm.clear_cache()}\n    finally:\n        runtime.llm.lock.release()\n'), (1649, 1652, '    future = executor.submit(\n'), (1669, 1670, '    )\n    try:\n        state = await asyncio.shield(asyncio.wrap_future(future))\n'), (1704, 1706, '        finish_request(request_id, future)\n')]

def apply(path):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest == RESULT_SHA256:
        print('Local changes already applied')
        return
    if digest == SOURCE_SHA256:
        lines = data.decode('utf-8').splitlines(keepends=True)
        for start, stop, addition in reversed(EDITS):
            lines[start:stop] = [addition]
        data = ''.join(lines).encode('utf-8')
    if hashlib.sha256(data).hexdigest() != LIFECYCLE_SHA256:
        raise SystemExit('Unexpected upstream version; refusing to change it')
    lines = data.decode('utf-8').splitlines(keepends=True)
    # A zero inference timeout leaves the SSE stream open until completion,
    # upstream failure or disconnect. Idle HTTP keep-alive remains bounded.
    line = lines[1528]
    index = line.index('if ') + len('if ')
    lines[1528] = line[:index] + 'config.timeout_seconds > 0 and ' + line[index:]
    line = lines[1900]
    index = line.index(',')
    lines[1900] = line[:index] + ' or 300' + line[index:]
    result = ''.join(lines).encode('utf-8')
    if hashlib.sha256(result).hexdigest() != RESULT_SHA256:
        raise ValueError('Local patch result checksum differs')
    compile(result, str(path), 'exec')
    path.write_bytes(result)
    print('Applied stateless lifecycle and management APIs:', RESULT_SHA256)

if __name__ == '__main__':
    apply(Path(sys.argv[1]))
