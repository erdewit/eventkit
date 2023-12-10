import asyncio
import unittest

from eventkit import Event
import eventkit as ev

loop = asyncio.get_event_loop_policy().get_event_loop()
run = loop.run_until_complete


class Object:

    def __init__(self):
        self.value = 0

    def method(self, x, y):
        self.value += x - y

    def __call__(self, x, y):
        self.value += x - y


async def ait(it):
    for x in it:
        await asyncio.sleep(0)
        yield x


class EventTest(unittest.TestCase):

    def test_functor(self):
        obj1 = Object()
        obj2 = Object()
        event = Event('test')
        event += obj1
        event.emit(9, 4)
        self.assertEqual(obj1.value, 5)
        event += obj2
        event.emit(5, 6)
        self.assertEqual(obj1.value, 4)
        self.assertEqual(obj2.value, -1)

        del obj2
        self.assertEqual(len(event), 1)
        event -= obj1
        self.assertNotIn(obj1, event)
        self.assertEqual(len(event), 0)

    def test_method(self):
        obj1 = Object()
        obj2 = Object()
        event = Event('test')
        event += obj1.method
        event.emit(9, 4)
        self.assertEqual(obj1.value, 5)
        event += obj2.method
        event.emit(5, 6)
        self.assertEqual(obj1.value, 4)
        self.assertEqual(obj2.value, -1)

        del obj2
        self.assertEqual(len(event), 1)
        event -= obj1.method
        self.assertNotIn(obj1.method, event)
        self.assertEqual(len(event), 0)

        event += obj1.method
        event += obj1.method
        self.assertEqual(len(event), 2)
        event.disconnect_obj(obj1)
        self.assertEqual(len(event), 0)

    def test_function(self):
        def f1(x, y):
            nonlocal value1
            value1 += x - y

        def f2(x, y):
            nonlocal value2
            value2 += x - y
        value1 = 0
        value2 = 0
        event = Event('test')
        event += f1
        event.emit(9, 4)
        self.assertEqual(value1, 5)
        event += f2
        event.emit(5, 6)
        self.assertEqual(value1, 4)
        self.assertEqual(value2, -1)
        event -= f1
        self.assertNotIn(f1, event)
        event -= f2
        self.assertNotIn(f2, event)
        self.assertEqual(len(event), 0)

    def test_cmethod(self):
        import math
        event = Event('test')
        event += math.pow
        event.emit(2, 8)

    def test_keep_ref(self):
        import weakref
        obj = Object()
        event = Event('test')
        event.connect(obj.method, keep_ref=True)
        wr = weakref.ref(obj)
        del obj
        event.emit(9, 4)
        self.assertEqual(wr().value, 5)
        obj = wr()
        event.emit(5, 6)
        self.assertEqual(obj.value, 4)
        self.assertIn(obj.method, event)
        event -= obj.method
        self.assertNotIn(obj.method, event)

    def test_coro_func(self):
        async def coro(d):
            result.append(d)
            await asyncio.sleep(0)

        result = []
        event = Event('test')
        event += coro

        event.emit(4)
        event.emit(2)
        run(asyncio.sleep(0))
        self.assertEqual(result, [4, 2])

        result.clear()
        event -= coro
        event.emit(8)
        run(asyncio.sleep(0))
        self.assertEqual(result, [])

    def test_aiter(self):
        async def coro():
            return [v async for v in event]

        a = list(range(0, 10))
        event = Event.sequence(a)
        result = run(coro())
        self.assertEqual(result, a)

    def test_fork(self):
        event = Event.range(4, 10)[ev.Min, ev.Max, ev.Op().sum()].zip()
        self.assertEqual(event.run(), [
            (4, 4, 4), (4, 5, 9), (4, 6, 15), (4, 7, 22),
            (4, 8, 30), (4, 9, 39)])

    def test_operator_connect(self):
        result = []
        ev1 = Event()
        ev2 = ev.Map(lambda x: x + 10)
        ev2 += result.append
        ev1 += ev2
        for i in range(10):
            ev1.emit(i)
        self.assertEqual(result, list(range(10, 20)))


if __name__ == "__main__":
    unittest.main()
