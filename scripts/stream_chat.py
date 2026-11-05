"""Small SSE text client. Private reasoning is discarded, never printed or saved."""
import argparse
import http.client
import json
import socket
import sys
import threading
import time


class UnixConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.host)
        self.transport=self.sock


def interrupt(connection):
    sock=getattr(connection,'transport',None)
    if sock is not None:
        try:sock.shutdown(socket.SHUT_RDWR)
        except OSError:pass


def content_events(response, deadline):
    """Read bounded OpenAI-style SSE records, including multiline data fields."""
    data=[];size=0;received=0
    while time.monotonic()<deadline:
        line=response.readline(32769)
        if len(line)>32768:raise ValueError('SSE line exceeds limit')
        if not line:raise ValueError('Incomplete SSE response')
        if line.strip():
            if line.startswith(b'data:'):
                size+=len(line)
                if size>65536:raise ValueError('SSE event exceeds limit')
                data.append(line[5:].strip())
            continue
        if not data:continue
        raw=b'\n'.join(data);data=[];size=0
        if raw==b'[DONE]':return
        message=json.loads(raw)
        if message.get('error'):raise ValueError('Model service returned an error')
        for choice in message.get('choices',[]):
            delta=choice.get('delta') or {}
            if any(value is not None and not isinstance(value,str) for value in
                   (delta.get('content'),delta.get('reasoning_content'))):
                raise ValueError('Invalid text delta')
            # Count private output for resource limits without retaining it.
            received+=len(delta.get('content') or '')+len(delta.get('reasoning_content') or '')
            if received>32768:raise ValueError('Generation exceeds limit')
            value=delta.get('content')
            if value:
                if not isinstance(value,str):raise ValueError('Invalid content delta')
                yield value
    raise TimeoutError('Generation deadline reached')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('prompt')
    parser.add_argument('--unix-socket',default='/run/qwen3.5-2b/inference.sock')
    parser.add_argument('--no-thinking',action='store_true')
    args=parser.parse_args()
    payload=dict(model='Qwen3.5-2B',messages=[dict(role='user',content=args.prompt)],
                 enable_thinking=not args.no_thinking,stream=True,max_tokens=256,
                 temperature=0.6,top_p=0.95,top_k=20,presence_penalty=0.0,repeat_penalty=1.0)
    connection=UnixConnection(args.unix_socket,timeout=180)
    response=None
    deadline=time.monotonic()+180
    watchdog=threading.Timer(180,interrupt,args=(connection,));watchdog.daemon=True;watchdog.start()
    try:
        connection.request('POST','/v1/chat/completions',json.dumps(payload).encode('utf-8'),{'Content-Type':'application/json'})
        response=connection.getresponse()
        if response.status!=200:raise RuntimeError('Model HTTP status '+str(response.status))
        for value in content_events(response,deadline):
            sys.stdout.write(value);sys.stdout.flush()
        print()
    finally:
        watchdog.cancel()
        if response is not None:response.close()
        connection.close()  # Interrupting this client cancels this stream only.


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:raise SystemExit(130)
    except (OSError,ValueError,RuntimeError,TimeoutError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(1)
