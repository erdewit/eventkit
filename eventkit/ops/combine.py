import functools
from collections import defaultdict, deque
from typing import Deque, Optional

from .op import Op
from ..event import Event
from ..util import NO_VALUE


class Fork(list):
    __slots__ = ()

    def __init__(self):
        list.__init__(self)

    def join(self, joiner: "JoinOp"):
        joiner._set_sources(*self)
        self.clear()
        return joiner

    def concat(self) -> "Concat":
        return self.join(Concat())

    def merge(self) -> "Merge":
        return self.join(Merge())

    def switch(self) -> "Switch":
        return self.join(Switch())

    def zip(self) -> "Zip":
        return self.join(Zip())

    def ziplatest(self) -> "Ziplatest":
        return self.join(Ziplatest())

    def chain(self) -> "Chain":
        return self.join(Chain())


class JoinOp(Op):
    """
    Base class for join operators that combine the emits
    from multiple source events.
    """

    __slots__ = ('_sources',)

    _sources: Deque[Event]

    def _set_sources(self, sources):
        raise NotImplementedError


class AddableJoinOp(JoinOp):
    """
    Base class for join operators where new sources, produced by a
    parent higher-order event, can be added dynamically.
    """

    __slots__ = ('_parent',)

    _parent: Optional[Event]

    def __init__(self, *sources: Event):
        JoinOp.__init__(self)
        self._sources = deque()
        self._parent = None
        self._set_sources(*sources)

    def _set_sources(self, *sources):
        for source in sources:
            source = Event.create(source)
            self.add_source(source)

    def add_source(self, source):
        # note: the same source can be added multiple times
        raise NotImplementedError

    def set_parent(self, parent: Event):
        self._parent = parent
        if parent.done_event:
            parent.done_event += self._on_parent_done

    def on_source_done(self, source):
        self._disconnect_from(source)
        self._sources.remove(source)
        if not self._sources and self._parent is None:
            self.set_done()

    def _on_parent_done(self, parent):
        parent -= self._on_parent_done
        self._parent = None
        if not self._sources:
            self.set_done()


class Merge(AddableJoinOp):
    __slots__ = ()

    def add_source(self, source):
        self._sources.append(source)
        self._connect_from(source)


class Switch(AddableJoinOp):
    __slots__ = ('_source2cb', '_active_source')

    def __init__(self, *sources):
        AddableJoinOp.__init__(self)
        self._source2cb = {}  # map from source to callback
        self._active_source = None
        self._set_sources(*sources)

    def add_source(self, source):
        self._sources.append(source)
        cb = self._source2cb.get(source)
        if not cb:
            cb = functools.partial(self.on_source_s, source)
            self._source2cb[source] = cb
            source.connect(cb, done=self.on_source_done)

    def _remove_source(self, source):
        if source in self._sources:
            self._sources.remove(source)
            cb = self._source2cb.pop(source, None)
            if cb:
                source -= cb

    def on_source_s(self, source, *args):
        if source is not self._active_source:
            self._remove_source(self._active_source)
            self._active_source = source
        self.emit(*args)

    def on_source_done(self, source):
        self._remove_source(source)
        if not self._sources and self._parent is None:
            self._active_source = None
            self.set_done()


class Concat(AddableJoinOp):
    __slots__ = ('_source2cb',)

    def __init__(self, *sources):
        AddableJoinOp.__init__(self)
        self._source2cb = {}  # map from source to callback
        self._set_sources(*sources)

    def add_source(self, source):
        if source in self._sources:
            return
        self._sources.append(source)
        cb = self._source2cb.get(source)
        if not cb:
            cb = functools.partial(self._on_source_s, source)
            self._source2cb[source] = cb
            source.connect(cb, done=self.on_source_done)

    def _on_source_s(self, source, *args):
        while self._sources and self._sources[0] is not source:
            s = self._sources.popleft()
            cb = self._source2cb.pop(s, None)
            if cb:
                s.disconnect(cb, done=self.on_source_done)
        self.emit(*args)

    def on_source_done(self, source):
        cb = self._source2cb.pop(source)
        source.disconnect(cb, done=self.on_source_done)
        while source in self._sources:
            self._sources.remove(source)
        if not self._sources and self._parent is None:
            self.set_done()


class Chain(AddableJoinOp):
    __slots__ = ('_qq', '_source2cbs')

    def __init__(self, *sources):
        AddableJoinOp.__init__(self)
        self._qq = deque()
        self._source2cbs = defaultdict(list)  # map from source to callbacks
        self._set_sources(*sources)

    def add_source(self, source):
        if not self._sources:
            self._connect_from(source)
        else:
            def cb(*args):
                q.append(args)
            q = deque()
            self._qq.append(q)
            source += cb
            self._source2cbs[source].append(cb)
        self._sources.append(source)

    def on_source_done(self, source):
        if source is not self._sources[0]:
            return
        self._disconnect_from(source)
        self._sources.popleft()
        while self._sources:
            source = self._sources[0]
            q = self._qq.popleft()
            for args in q:
                self.emit(*args)
            for cb in self._source2cbs.pop(source, []):
                source -= cb
            if source.done():
                self._sources.popleft()
                continue
            self._connect_from(source)
            return
        if not self._sources and self._parent is None:
            self.set_done()


class Zip(JoinOp):
    __slots__ = ('_results', '_source2cbs', '_num_ready')

    def __init__(self, *sources):
        JoinOp.__init__(self)
        self._num_ready = 0  # number of sources with a pending result
        self._source2cbs = defaultdict(list)  # map from source to callbacks
        if sources:
            self._set_sources(*sources)

    def _set_sources(self, *sources):
        self._sources = deque(Event.create(s) for s in sources)
        if any(s.done() for s in self._sources):
            self.set_done()
            return
        self._results = [deque() for _ in self._sources]
        for i, source in enumerate(self._sources):
            cb = functools.partial(self._on_source_i, i)
            source.connect(cb, self.on_source_error, self.on_source_done)
            self._source2cbs[source].append(cb)

    def _on_source_i(self, i, *args):
        q = self._results[i]
        if not q:
            self._num_ready += 1
            ready = self._num_ready == len(self._results)
        else:
            ready = False
        q.append(args[0] if len(args) == 1 else args if args else NO_VALUE)
        if ready:
            tup = tuple(q.popleft() for q in self._results)
            self._num_ready = sum(bool(q) for q in self._results)
            self.emit(*tup)

    def on_source_done(self, source):
        self._sources.remove(source)
        if not self._sources:
            for source, cbs in self._source2cbs.items():
                for cb in cbs:
                    source.disconnect(
                        cb, self.on_source_error, self.on_source_done)
            self._source2cbs = None
            self.set_done()


class Ziplatest(JoinOp):
    __slots__ = ('_values', '_is_primed', '_source2cbs')

    def __init__(self, *sources, partial=True):
        JoinOp.__init__(self)
        self._is_primed = partial
        self._source2cbs = defaultdict(list)  # map from source to callbacks
        if sources:
            self._set_sources(*sources)

    def _set_sources(self, *sources):
        sources = [Event.create(s) for s in sources]
        self._sources = deque(s for s in sources if not s.done())
        if not self._sources:
            self.set_done()
            return
        self._values = [s.value() for s in sources]
        for i, source in enumerate(self._sources):
            cb = functools.partial(self._on_source_i, i)
            source.connect(cb, self.on_source_error, self.on_source_done)
            self._source2cbs[source].append(cb)

    def _on_source_i(self, i, *args):
        self._values[i] = \
            args[0] if len(args) == 1 else args if args else NO_VALUE
        if not self._is_primed:
            self._is_primed = not any(r is NO_VALUE for r in self._values)
        if self._is_primed:
            self.emit(*self._values)

    def on_source_done(self, source):
        self._sources.remove(source)
        if not self._sources:
            for source, cbs in self._source2cbs.items():
                for cb in cbs:
                    source.disconnect(
                        cb, self.on_source_error, self.on_source_done)
            self._source2cbs = None
            self.set_done()
