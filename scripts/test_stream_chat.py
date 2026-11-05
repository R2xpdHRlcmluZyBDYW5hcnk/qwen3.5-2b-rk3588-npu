import io
import json
import unittest
from stream_chat import content_events


def event(delta):
    return b'data: '+json.dumps({'choices':[{'delta':delta}]},ensure_ascii=False).encode()+b'\n\n'


class StreamTests(unittest.TestCase):
    def test_public_content_is_incremental_and_private_channel_is_omitted(self):
        source=io.BytesIO(event({'reasoning_content':'PRIVATE_SENTINEL'})+event({'content':'正'})+event({'content':'文'})+b'data: [DONE]\n\n')
        chunks=content_events(source)
        self.assertEqual(next(chunks),'正');self.assertEqual(next(chunks),'文')
        self.assertEqual(list(chunks),[])

    def test_truncation_and_unbounded_records_fail(self):
        for data in (event({'content':'partial'}),b'data: '+b'x'*32769+b'\n\n',event({'reasoning_content':'x'*32769})):
            with self.subTest(size=len(data)),self.assertRaises(ValueError):
                list(content_events(io.BytesIO(data)))


if __name__=='__main__':unittest.main()
