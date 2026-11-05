import io
import json
import time
import socket
from types import SimpleNamespace
import unittest
from stream_chat import content_events,interrupt


def event(delta):
    return b'data: '+json.dumps({'choices':[{'delta':delta}]},ensure_ascii=False).encode()+b'\n\n'


class StreamTests(unittest.TestCase):
    def test_public_content_is_incremental_and_private_channel_is_omitted(self):
        source=io.BytesIO(event({'reasoning_content':'PRIVATE_SENTINEL'})+event({'content':'正'})+event({'content':'文'})+b'data: [DONE]\n\n')
        chunks=content_events(source,time.monotonic()+1)
        self.assertEqual(next(chunks),'正');self.assertEqual(next(chunks),'文')
        self.assertEqual(list(chunks),[])

    def test_truncation_and_unbounded_records_fail(self):
        for data in (event({'content':'partial'}),b'data: '+b'x'*32769+b'\n\n',event({'reasoning_content':'x'*32769})):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):
                list(content_events(io.BytesIO(data),time.monotonic()+1))

    def test_deadline_is_enforced(self):
        with self.assertRaises(TimeoutError):list(content_events(io.BytesIO(),time.monotonic()-1))

    def test_interrupt_shuts_down_transport_even_after_http_detaches_socket(self):
        left,right=socket.socketpair()
        try:
            interrupt(SimpleNamespace(sock=None,transport=left))
            right.settimeout(.1);self.assertEqual(right.recv(1),b'')
        finally:left.close();right.close()


if __name__=='__main__':unittest.main()
