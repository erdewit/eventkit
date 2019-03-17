import unittest

from eventkit import Event

array = list(range(10))


class AggregateTest(unittest.TestCase):

    def test_min(self):
        event = Event.sequence(array).min()
        self.assertEqual(event.run(), [0] * 10)

    def test_max(self):
        event = Event.sequence(array).max()
        self.assertEqual(event.run(), array)

    def test_sum(self):
        event = Event.sequence(array).sum()
        self.assertEqual(event.run(), [
            0, 1, 3, 6, 10, 15, 21, 28, 36, 45])

    def test_product(self):
        event = Event.sequence(array[1:]).product()
        self.assertEqual(event.run(), [
            1, 2, 6, 24, 120, 720, 5040, 40320, 362880])

    def test_any(self):
        event = Event.sequence(array).any()
        self.assertEqual(event.run(), [
            False, True, True, True, True, True, True, True, True, True])

    def test_all(self):
        x = [True] * 10 + [False] * 10
        event = Event.sequence(x).all()
        self.assertEqual(event.run(), x)

    def test_pairwaise(self):
        event = Event.sequence(array).pairwise()
        self.assertEqual(event.run(), list(zip(array, array[1:])))

    def test_chunk(self):
        event = Event.sequence(array).chunk(3)
        self.assertEqual(event.run(), [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]])

    def test_chunkwith(self):
        timer = Event.timer(0.029, 10)
        event = Event.sequence(array, 0.01).chunkwith(timer)
        self.assertEqual(event.run(), [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]])

    def test_array(self):
        event = Event.sequence(array).array(5).last()
        self.assertEqual(list(event.run()[0]), array[-5:])
