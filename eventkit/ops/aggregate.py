import itertools
import operator
from collections import deque

from .op import Op
from .transform import Iterate
from ..util import NO_VALUE


class Count(Iterate):
    __slots__ = ()

    def __init__(self, start=0, step=1, source=None):
        it = itertools.count(start, step)
        Iterate.__init__(self, it, source)


class Reduce(Op):
    __slots__ = ('_func', '_initializer', '_prev')

    def __init__(self, func, initializer=NO_VALUE, source=None):
        Op.__init__(self, source)
        self._func = func
        self._initializer = initializer
        self._prev = NO_VALUE

    def on_source(self, arg):
        if self._prev is NO_VALUE:
            if self._initializer is NO_VALUE:
                self._prev = arg
            else:
                self._prev = self._func(self._initializer, arg)
                self.emit(self._prev)
        else:
            self._prev = self._func(self._prev, arg)
            self.emit(self._prev)


class Min(Reduce):
    __slots__ = ()

    def __init__(self, source=None):
        Reduce.__init__(self, min, float('inf'), source)


class Max(Reduce):
    __slots__ = ()

    def __init__(self, source=None):
        Reduce.__init__(self, max, -float('inf'), source)


class Sum(Reduce):
    __slots__ = ()

    def __init__(self, start=0, source=None):
        Reduce.__init__(self, operator.add, start, source)


class Product(Reduce):
    __slots__ = ()

    def __init__(self, start=1, source=None):
        Reduce.__init__(self, operator.mul, start, source)


class Mean(Op):
    __slots__ = ('_count', '_sum')

    def __init__(self, source=None):
        Op.__init__(self, source)
        self._count = 0
        self._sum = 0

    def on_source(self, arg):
        self._count += 1
        self._sum += arg
        self.emit(self._sum / self._count)


class Any(Reduce):
    __slots__ = ()

    def __init__(self, source=None):
        Reduce.__init__(self, lambda prev, v: prev or bool(v), False, source)


class All(Reduce):
    __slots__ = ()

    def __init__(self, source=None):
        Reduce.__init__(self, lambda prev, v: prev and bool(v), True, source)


class Ema(Op):
    __slots__ = ('_f1', '_f2', '_prev')

    def __init__(self, n=None, weight=None, source=None):
        Op.__init__(self, source)
        self._f1 = weight or 2.0 / (n + 1)
        self._f2 = 1 - self._f1
        self._prev = NO_VALUE

    def on_source(self, *args):
        if self._prev is NO_VALUE:
            value = args
        else:
            value = [
                self._f2 * p + self._f1 * a for p, a in zip(self._prev, args)]
        self._prev = value
        self.emit(*value)


class Pairwise(Op):
    __slots__ = ('_prev', '_has_prev')

    def __init__(self, source=None):
        Op.__init__(self, source)
        self._has_prev = False

    def on_source(self, *args):
        value = args[0] if len(args) == 1 else args if args else NO_VALUE
        if self._has_prev:
            self.emit(self._prev, value)
        else:
            self._has_prev = True
        self._prev = value


class List(Op):
    __slots__ = ('_values')

    def __init__(self, source=None):
        Op.__init__(self, source)
        self._values = []

    def on_source(self, *args):
        self._values.append(
            args[0] if len(args) == 1 else args if args else NO_VALUE)

    def on_source_done(self, source):
        self.emit(self._values)
        Op.on_source_done(self, source)


class Deque(Op):
    __slots__ = ('_count', '_q')

    def __init__(self, count, source=None):
        Op.__init__(self, source)
        self._count = count
        self._q = deque()

    def on_source(self, *args):
        self._q.append(
            args[0] if len(args) == 1 else args if args else NO_VALUE)
        if self._count and len(self._q) > self._count:
            self._q.popleft()
        self.emit(self._q)
