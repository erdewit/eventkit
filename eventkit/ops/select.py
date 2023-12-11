from .op import Op
from ..util import NO_VALUE


class Filter(Op):
    __slots__ = ('_predicate',)

    def __init__(self, predicate=bool, source=None):
        Op.__init__(self, source)
        self._predicate = predicate

    def on_source(self, *args):
        if self._predicate(*args):
            self.emit(*args)


class Skip(Op):
    __slots__ = ('_count', '_n')

    def __init__(self, count=1, source=None):
        Op.__init__(self, source)
        self._count = count
        self._n = 0

    def on_source(self, *args):
        self._n += 1
        if self._n == self._count:
            self._source -= self.on_source
            self._source += self.emit


class Take(Op):
    __slots__ = ('_count', '_n')

    def __init__(self, count=1, source=None):
        Op.__init__(self, source)
        self._count = count
        self._n = 0

    def on_source(self, *args):
        self._n += 1
        if self._n <= self._count:
            self.emit(*args)
        if self._n == self._count:
            self._disconnect_from(self._source)
            self.set_done()


class TakeWhile(Op):
    __slots__ = ('_predicate',)

    def __init__(self, predicate=bool, source=None):
        Op.__init__(self, source)
        self._predicate = predicate

    def on_source(self, *args):
        if self._predicate(*args):
            self.emit(*args)
        else:
            self.set_done()
            self._disconnect_from(self._source)


class DropWhile(Op):
    __slots__ = ('_predicate', '_drop')

    def __init__(self, predicate=lambda x: not x, source=None):
        Op.__init__(self, source)
        self._predicate = predicate
        self._drop = True

    def on_source(self, *args):
        if self._drop:
            self._drop = self._predicate(*args)
        if not self._drop:
            self.emit(*args)


class TakeUntil(Op):
    __slots__ = ('_notifier',)

    def __init__(self, notifier, source=None):
        Op.__init__(self, source)
        self._notifier = notifier
        notifier.connect(
            self._on_notifier,
            self.on_source_error,
            self.on_source_done)

    def _on_notifier(self, *args):
        self.on_source_done(self._source)

    def on_source_done(self, source):
        Op.on_source_done(self, self._source)
        self._notifier.disconnect(
            self._on_notifier,
            self.on_source_error,
            self.on_source_done)
        self._notifier = None


class Changes(Op):
    __slots__ = ('_prev',)

    def __init__(self, source=None):
        Op.__init__(self, source)
        self._prev = NO_VALUE

    def on_source(self, *args):
        if args != self._prev:
            self.emit(*args)
        self._prev = args


class Unique(Op):
    __slots__ = ('_key', '_seen')

    def __init__(self, key, source=None):
        Op.__init__(self, source)
        self._key = key
        self._seen = set()

    def on_source(self, *args):
        if self._key is None:
            new = args not in self._seen
        else:
            new = self._key(*args) not in self._seen
        self._seen.add(args)
        if new:
            self.emit(*args)


class Last(Op):
    __slots__ = ('_last',)

    def __init__(self, source=None):
        Op.__init__(self, source)
        self._last = NO_VALUE

    def on_source(self, *args):
        self._last = args

    def on_source_done(self, source):
        self.emit(*self._last)
        Op.on_source_done(self, source)
