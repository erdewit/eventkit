import unittest

from eventkit import Event

array = list(range(10))


class SelectTest(unittest.TestCase):

    def test_select(self):
        event = Event.sequence(array).filter(lambda x: x % 2)
        self.assertEqual(event.run(), [x for x in array if x % 2])

    def test_skip(self):
        event = Event.sequence(array).skip(5)
        self.assertEqual(event.run(), array[5:])

    def test_take(self):
        event = Event.sequence(array).take(5)
        self.assertEqual(event.run(), array[:5])

    def test_takewhile(self):
        event = Event.sequence(array).takewhile(lambda x: x < 5)
        self.assertEqual(event.run(), array[:5])

    def test_dropwhile(self):
        event = Event.sequence(array).dropwhile(lambda x: x < 5)
        self.assertEqual(event.run(), array[5:])

    def test_changes(self):
        array = [1, 1, 2, 1, 2, 2, 2, 3, 1, 4, 4]
        event = Event.sequence(array).changes()
        self.assertEqual(event.run(), [1, 2, 1, 2, 3, 1, 4])

    def test_unique(self):
        array = [1, 1, 2, 1, 2, 2, 2, 3, 1, 4, 4]
        event = Event.sequence(array).unique()
        self.assertEqual(event.run(), [1, 2, 3, 4])

    def test_last(self):
        event = Event.sequence(array).last()
        self.assertEqual(event.run(), [9])
