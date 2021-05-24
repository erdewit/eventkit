from asyncio import get_event_loop
from collections import deque

from ..event import Event
from ..util import NO_VALUE
from .op import Op


class Delay(Op):
    __slots__ = ('_delay',)

    def __init__(self, delay, source=None):
        Op.__init__(self, source)
        self._delay = delay

    def on_source(self, *args):
        loop = get_event_loop()
        loop.call_later(self._delay, self.emit, *args)

    def on_source_error(self, error):
        loop = get_event_loop()
        loop.call_later(self._delay, self.error_event.emit, error)

    def on_source_done(self, source):
        loop = get_event_loop()
        loop.call_later(self._delay, self.set_done)


class Timeout(Op):
    __slots__ = ('_timeout', '_handle', '_last_time')

    def __init__(self, timeout, source=None):
        Op.__init__(self, source)
        if source.done():
            return
        self._timeout = timeout
        loop = get_event_loop()
        self._last_time = loop.time()
        self._handle = None
        self._schedule()

    def on_source(self, *args):
        loop = get_event_loop()
        self._last_time = loop.time()

    def on_source_done(self, source):
        self._disconnect_from(self._source)
        self._handle.cancel()
        del self._handle
        self.set_done()

    def _schedule(self):
        loop = get_event_loop()
        self._handle = loop.call_at(
            self._last_time + self._timeout, self._on_timer)

    def _on_timer(self):
        loop = get_event_loop()
        if loop.time() - self._last_time > self._timeout:
            self.emit()
            self.set_done()
        else:
            self._schedule()


class Debounce(Op):
    __slots__ = ('_interval', '_on_first', '_handle', '_last_time')

    def __init__(self, interval, on_first=False, source=None):
        Op.__init__(self, source)
        self._interval = interval
        self._on_first = on_first
        self._last_time = -float('inf')
        self._handle = None

    def on_source(self, *args):
        loop = get_event_loop()
        time = loop.time()
        delta = time - self._last_time
        self._last_time = time
        if self._on_first:
            if delta >= self._interval:
                self.emit(*args)
        else:
            if self._handle:
                self._handle.cancel()
            self._handle = loop.call_at(
                time + self._interval, self._delayed_emit, *args)

    def _delayed_emit(self, *args):
        self._handle = None
        self.emit(*args)
        if self._source is None:
            self.set_done()

    def on_source_done(self, source):
        self._disconnect_from(source)
        self._source = None
        if not self._handle:
            self.set_done()


class Throttle(Op):
    __slots__ = (
        'status_event', '_maximum', '_interval', '_cost_func',
        '_q', '_time_q', '_cost_q', '_is_throttling')

    def __init__(self, maximum, interval, cost_func=None, source=None):
        Op.__init__(self, source)
        self.status_event = Event('throttle_status')
        """
        Sub event that emits ``True`` when throttling starts and ``False``
        when throttling ends.
        """
        self._maximum = maximum
        self._interval = interval
        self._cost_func = cost_func
        self._q = deque()        # deque of (args, cost) tuples
        self._time_q = deque()   # deque of previous emit times
        self._cost_q = deque()   # deque of costs of previous emits
        self._is_throttling = False

    def set_limit(self, maximum, interval):
        """
        Dynamically update the ``maximum`` per ``interval`` limit.
        """
        self._maximum = maximum
        self._interval = interval

    def on_source(self, *args):
        cost = self._cost_func
        if cost is not None:
            cost = cost(*args)
        self._q.append((args, cost))
        self._try_emit()

    def on_source_done(self, source):
        self._disconnect_from(source)
        self._source = None
        if not self._q:
            self.set_done()
            self.status_event.set_done()

    def _try_emit(self):
        loop = get_event_loop()
        t = loop.time()
        q = self._q
        times = self._time_q
        costs = self._cost_q

        # forget old emit times
        while times and t - times[0] > self._interval:
            times.popleft()
            costs.popleft()

        # emit values while not exceeding the limit
        while q:
            args, cost = q[0]
            if self._cost_func:
                cost = self._cost_func(*args)
                total_cost = cost + sum(costs)
            else:
                cost = None
                total_cost = 1 + len(costs)
            if self._maximum and total_cost >= self._maximum:
                break
            args, cost = q.popleft()
            times.append(t)
            costs.append(cost)
            self.emit(*args)

        # update status and schedule new emits
        if q:
            if not self._is_throttling:
                self.status_event.emit(True)
            loop.call_at(times[0] + self._interval, self._try_emit)
        elif self._is_throttling:
            self.status_event.emit(False)
        self._is_throttling = bool(q)

        if not q and self._source is None:
            self.set_done()
            self.status_event.set_done()


class Sample(Op):
    __slots__ = ('_timer',)

    def __init__(self, timer, source=None):
        Op.__init__(self, source)
        self._timer = timer
        timer.connect(
            self._on_timer,
            self.on_source_error,
            self.on_source_done)

    def on_source(self, *args):
        self._value = args

    def _on_timer(self, *args):
        if self._value is not NO_VALUE:
            self.emit(*self._value)

    def on_source_done(self, source):
        Op.on_source_done(self, self)
        self._timer.disconnect(
            self._on_timer,
            self.on_source_error,
            self.on_source_done)
        self._timer = None
