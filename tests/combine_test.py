import unittest

from eventkit import Event

array1 = list(range(10))
array2 = list(range(100, 110))
array3 = list(range(200, 210))


class CombineTest(unittest.TestCase):

    def test_merge(self):
        e1 = Event.sequence(array1, interval=0.01)
        e2 = Event.sequence(array2, interval=0.01).delay(0.001)
        event = e1.merge(e2)
        self.assertEqual(event.run(), [
            i for j in zip(array1, array2) for i in j])

    def test_switch(self):
        e1 = Event.sequence(array1, interval=0.01)
        e2 = Event.sequence(array2, interval=0.01).delay(0.001)
        e3 = Event.sequence(array3, interval=0.01).delay(0.002)
        event = e1.switch(e2, e3, e2)
        self.assertEqual(event.run(), [0, 100] + array3)

    def test_concat(self):
        e1 = Event.sequence(array1, interval=0.02)
        e2 = Event.sequence(array2, interval=0.02).delay(0.07)
        event = e1.concat(e2)
        self.assertEqual(event.run(), [
            0, 1, 2, 3, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109])

    def test_chain(self):
        e1 = Event.sequence(array1, interval=0.01)
        e2 = Event.sequence(array2, interval=0.01).delay(0.001)
        event = e1.chain(e2, e1)
        self.assertEqual(event.run(), array1 + array2 + array1)

    def test_zip(self):
        e1 = Event.sequence(array1)
        e2 = Event.sequence(array2).delay(0.001)
        event = e1.zip(e2)
        self.assertEqual(event.run(), list(zip(array1, array2)))

    def test_zip_self(self):
        e1 = Event.sequence(array1)
        event = e1.zip(e1)
        self.assertEqual(event.run(), list(zip(array1, array1)))

    def test_ziplatest(self):
        e1 = Event.sequence([0, 1], interval=0.01)
        e2 = Event.sequence([2, 3], interval=0.01).delay(0.001)
        event = e1.ziplatest(e2)
        self.assertEqual(
            event.run(), [(0, Event.NO_VALUE), (0, 2), (1, 2), (1, 3)])
