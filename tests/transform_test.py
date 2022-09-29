import unittest
import asyncio
from collections import namedtuple

import numpy as np

from eventkit import Event

loop = asyncio.get_event_loop_policy().get_event_loop()
loop.set_debug(True)

array = list(range(20))


class TransformTest(unittest.TestCase):

    def test_constant(self):
        event = Event.sequence(array).constant(42)
        self.assertEqual(event.run(), [42] * len(array))

    def test_previous(self):
        event = Event.sequence(array).previous(2)
        self.assertEqual(event.run(), array[:-2])

    def test_iterate(self):
        event = Event.sequence(array).iterate([5, 4, 3, 2, 1])
        self.assertEqual(event.run(), [5, 4, 3, 2, 1])

    def test_count(self):
        s = 'abcdefghij'
        event = Event.sequence(s).count()
        self.assertEqual(event.run(), array[:len(s)])

    def test_enumerate(self):
        s = 'abcdefghij'
        event = Event.sequence(s).enumerate()
        self.assertEqual(event.run(), list(enumerate(s)))

    def test_timestamp(self):
        interval = 0.002
        event = Event.sequence(array, interval=interval).timestamp()
        times = event.pluck(0).run()
        std = np.std(np.diff(times) - interval)
        self.assertLess(std, interval)

    def test_partial(self):
        event = Event.sequence(array).partial(42)
        self.assertEqual(event.run(), [(42, i) for i in array])

    def test_partial_right(self):
        event = Event.sequence(array).partial_right(42)
        self.assertEqual(event.run(), [(i, 42) for i in array])

    def test_star(self):
        def f(i, j):
            r.append((i, j))

        r = []
        event = Event.sequence(array).map(lambda i: (i, i)).star().connect(f)
        self.assertEqual(event.run(), r)

    def test_pack(self):
        event = Event.sequence(array).pack()
        self.assertEqual(event.run(), [(i,) for i in array])

    def test_pluck(self):
        Person = namedtuple('Person', 'name address')
        Address = namedtuple('Address', 'city street number zipcode')
        data = [
            Person('Max', Address('Delft', 'Levelstreet', '3', '2333AS')),
            Person('Elena', Address('Leiden', 'Punt', '122', '2412DE')),
            Person('Fem', Address('Rotterdam', 'Burgundy', '12', '3001RT'))]

        def event():
            return Event.sequence(data)

        self.assertEqual(
            event().pluck('0.name', '.address.street').run(),
            [(d.name, d.address.street) for d in data])

    def test_sync_map(self):
        event = Event.sequence(array).map(lambda x: x * x)
        self.assertEqual(event.run(), [i * i for i in array])

    def test_sync_star_map(self):
        event = Event.sequence(array)
        event = event.map(lambda i: (i, i)).star().map(lambda x, y: x / 2 - y)
        self.assertEqual(
            event.run(),
            [x / 2 - y for x, y in zip(array, array)])

    def test_async_map(self):
        async def coro(x):
            await asyncio.sleep(0.1)
            return x * x

        event = Event.sequence(array).map(coro)
        self.assertEqual(event.run(), [i * i for i in array])

    def test_async_map_unordered(self):
        class A():

            def __init__(self):
                self.t = 0.1

            async def coro(self, x):
                self.t -= 0.01
                await asyncio.sleep(self.t)
                return x * x

        a = A()
        event = Event.range(10).map(a.coro, ordered=False)
        result = set(event.run())
        expected = set(i * i for i in reversed(range(10)))
        self.assertEqual(result, expected)

    def test_mergemap(self):
        marbles = [
            'A   B    C    D',
            '_1   2  3    4',
            '__K   L     M   N'
        ]
        event = Event.range(3) \
            .mergemap(lambda v: Event.marble(marbles[v]))
        self.assertEqual(event.run(), [
            'A', '1', 'K', 'B', '2', 'L', '3', 'C', 'M', '4', 'D', 'N'])

    def test_mergemap2(self):
        a = ['ABC', 'UVW', 'XYZ']
        event = Event.range(3, interval=0.01) \
            .mergemap(lambda v: Event.sequence(a[v], 0.05 * v))
        self.assertEqual(event.run(), [
            'A', 'B', 'C', 'U', 'X', 'V', 'W', 'Y', 'Z'])

    def test_concatmap(self):
        marbles = [
            'A    B    C    D',
            '_       1    2    3    4',
            '__                  K    L      M   N'
        ]
        event = Event.range(3) \
            .concatmap(lambda v: Event.marble(marbles[v]))
        self.assertEqual(event.run(), [
            'A', 'B', '1', '2', '3', 'K', 'L', 'M', 'N'])

    def test_chainmap(self):
        marbles = [
            'A    B    C    D           ',
            '_       1    2    3    4',
            '__                  K    L      M   N'
        ]
        event = Event.range(3) \
            .chainmap(lambda v: Event.marble(marbles[v]))
        self.assertEqual(event.run(), [
            'A', 'B', 'C', 'D', '1', '2', '3', '4', 'K', 'L', 'M', 'N'])

    def test_switchmap(self):
        marbles = [
            'A    B    C    D           ',
            '_                 K    L      M   N',
            '__      1    2      3    4'
        ]
        event = Event.range(3) \
            .switchmap(lambda v: Event.marble(marbles[v]))
        self.assertEqual(event.run(), [
            'A', 'B', '1', '2', 'K', 'L', 'M', 'N'])
