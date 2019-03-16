import asyncio
import unittest

from eventkit import Event

array1 = list(range(10))
array2 = list(range(100, 110))

loop = asyncio.get_event_loop()


class CreateTest(unittest.TestCase):

    def test_wait(self):
        fut = asyncio.Future()
        loop.call_later(0.001, fut.set_result, 42)
        event = Event.wait(fut)
        self.assertEqual(event.run(), [42])

    def test_aiterate(self):
        async def ait():
            await asyncio.sleep(0)
            for i in array1:
                yield i
        event = Event.aiterate(ait())
        self.assertEqual(event.run(), array1)

    def test_marble(self):
        s = '   a b c   d e f'
        event = Event.marble(s, interval=0.001)
        self.assertEqual(event.run(), [c for c in 'abcdef'])
