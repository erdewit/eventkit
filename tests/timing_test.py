import unittest
import time

from eventkit import Event

array1 = list(range(10))
array2 = list(range(100, 110))
array3 = list(range(200, 210))


class TimingTest(unittest.TestCase):

    def test_delay(self):
        delay = 0.01
        src = Event.sequence(array1, interval=0.01)
        e1 = src.timestamp().pluck(0)
        e2 = src.delay(delay).timestamp().pluck(0)
        r = e1.zip(e2).map(lambda a, b: b - a).mean().run()
        self.assertLess(abs(r[-1]), delay + 0.002)

    def test_sample(self):
        timer = Event.timer(0.021, 4)
        event = Event.range(10, interval=0.01).sample(timer)
        self.assertEqual(event.run(), [2, 4, 6, 8])

    def test_timeout(self):
        timer = Event.timer(10, count=1)
        event = timer.timeout(0.01)
        self.assertEqual(event.run(), [Event.NO_VALUE])

    def test_debounce(self):
        event = Event.range(10, interval=0.05) \
            .mergemap(lambda t: Event.sequence(array2, 0.001)) \
            .debounce(0.01)
        self.assertEqual(event.run(), [109] * 10)

    def test_debounce_on_first(self):
        event = Event.range(10, interval=0.05) \
            .mergemap(lambda t: Event.sequence(array2, 0.001)) \
            .debounce(0.02, on_first=True)
        self.assertEqual(event.run(), [100] * 10)

    def test_throttle(self):
        t0 = time.time()
        a = list(range(500))
        event = Event.sequence(a) \
            .throttle(1000, 0.1, cost_func=lambda i: 10)
        result = event.run()
        self.assertEqual(result, a)
        dt = time.time() - t0
        self.assertLess(abs(dt - 0.5), 0.05)
