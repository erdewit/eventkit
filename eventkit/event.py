import types
import weakref
import asyncio
import logging
from typing import List, Union, Iterable, Awaitable, AsyncIterable

from .util import NO_VALUE, main_event_loop


class Event:
    """
    Enable event passing between loosely coupled components.
    The event emits values to connected listeners and has
    a selection of operators to create general data flow pipelines.

    Args:
        name: Name to use for this event.
    """
    __slots__ = (
        'error_event', 'done_event', '_name', '_value',
        '_slots', '_done', '_source', '__weakref__')

    NO_VALUE = NO_VALUE
    logger = logging.getLogger(__name__)

    def __init__(self, name: str = '', _with_error_done_events: bool = True):
        self.error_event = None
        """
        Sub event that emits errors from this event as
        ``emit(source, exception)``.
        """
        self.done_event = None
        """
        Sub event that emits when this event is done as
        ``emit(source)``.
        """
        if _with_error_done_events:
            self.error_event = Event('error', False)
            self.done_event = Event('done', False)
        self._slots = []  # list of [obj, weakref, func] sublists
        self._name = name or self.__class__.__qualname__
        self._value = NO_VALUE
        self._done = False
        self._source = None

    def name(self) -> str:
        """
        This event's name.
        """
        return self._name

    def done(self) -> bool:
        """
        ``True`` if event has ended with no more emits coming,
        ``False`` otherwise.
        """
        return self._done

    def set_done(self):
        """
        Set this event to be ended. The event should not emit anything
        after that.
        """
        if not self._done:
            self._done = True
            self.done_event.emit(self)

    def value(self):
        """
        This event's last emitted value.
        """
        v = self._value
        return NO_VALUE if v is NO_VALUE else \
            v[0] if len(v) == 1 else v if v else NO_VALUE

    def connect(self, listener, error=None, done=None, keep_ref: bool = False):
        """
        Connect a listener to this event. If the listener is added multiple
        times then it is invoked just as many times on emit.

        The ``+=`` operator can be used as a synonym for this method::

            import eventkit as ev

            def f(a, b):
                print(a * b)

            def g(a, b):
                print(a / b)

            event = ev.Event()
            event += f
            event += g
            event.emit(10, 5)

        Args:
            listener: The callback to invoke on emit of this event.
                It gets the ``*args`` from an emit as arguments.
                If the listener is a coroutine function, or a function that
                returns an awaitable, the awaitable is run in the
                asyncio event loop.
            error: The callback to invoke on error of this event.
                It gets (this event, exception) as two arguments.
            done: The callback to invoke on ending of this event.
                It gets this event as single argument.
            keep_ref:
                * ``True``: A strong reference to the callable is kept
                * ``False``: If the callable allows weak refs and it is
                  garbage collected, then it is automatically disconnected
                  from this event.
        """
        obj, func = self._split(listener)
        if not keep_ref and hasattr(obj, '__weakref__'):
            ref = weakref.ref(obj, self._onFinalize)
            obj = None
        else:
            ref = None
        slot = [obj, ref, func]
        self._slots.append(slot)
        if done is not None:
            self.done_event.connect(done)
        if error is not None:
            self.error_event.connect(error)
        return self

    def disconnect(self, listener, error=None, done=None):
        """
        Disconnect a listener from this event.

        The ``-=`` operator can be used as a synonym for this method.

        Args:
            listener: The callback to disconnect. The callback is removed at
                most once. It is valid if the callback is already
                not connected.
            error: The error callback to disconnect.
            done: The done callback to disconnect.
        """
        obj, func = self._split(listener)
        for slot in self._slots:
            if (slot[0] is obj or slot[1] and slot[1]() is obj) \
                    and slot[2] is func:
                slot[0] = slot[1] = slot[2] = None
                break
        self._slots = [s for s in self._slots if s != [None, None, None]]
        if error is not None:
            self.error_event.disconnect(error)
        if done is not None:
            self.done_event.disconnect(done)
        return self

    def disconnect_obj(self, obj):
        """
        Disconnect all listeners on the given object.
        (also the error and done listeners).

        Args:
            obj: The target object that is to be completely removed from
              this event.
        """
        for slot in self._slots:
            if slot[0] is obj or slot[1] and slot[1]() is obj:
                slot[0] = slot[1] = slot[2] = None
        self._slots = [s for s in self._slots if s != [None, None, None]]
        if self.error_event is not None:
            self.error_event.disconnect_obj(obj)
        if self.done_event is not None:
            self.done_event.disconnect_obj(obj)

    def emit(self, *args):
        """
        Emit a new value to all connected listeners.

        Args:
            args: Argument values to emit to listeners.
        """
        self._value = args
        for obj, ref, func in self._slots:
            try:
                if ref:
                    obj = ref()

                result = None
                if obj is None:
                    if func:
                        result = func(*args)
                else:
                    if func:
                        result = func(obj, *args)
                    else:
                        result = obj(*args)

                if result and hasattr(result, '__await__'):
                    asyncio.ensure_future(result)

            except Exception as error:
                if len(self.error_event):
                    self.error_event.emit(self, error)
                else:
                    Event.logger.exception(
                        f'Value {args} caused exception for event {self}')

    def emit_threadsafe(self, *args):
        """
        Threadsafe version of :meth:`emit` that doesn't invoke the
        listeners directly but via the event loop of the main thread.
        """
        main_event_loop.call_soon_threadsafe(self.emit, *args)

    def clear(self):
        """
        Disconnect all listeners.
        """
        for slot in self._slots:
            slot[0] = slot[1] = slot[2] = None
        self._slots = []

    def run(self) -> List:
        """
        Start the asyncio event loop, run this event to completion and
        return all values as a list::

            import eventkit as ev

            ev.Timer(0.25, count=10).run()
            ->
            [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5]

        .. note::

            When running inside a Jupyter notebook this will give an error
            that the asyncio event loop is already running. This can be
            remedied by applying
            `nest_asyncio <https://github.com/erdewit/nest_asyncio>`_
            or by using the top-level ``await`` statement of Jupyter::

                await event.list()
        """
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.list())

    def pipe(self, *targets: "Event"):
        """
        Form several events into a pipe::

            import eventkit as ev

            e1 = ev.Sequence('abcde')
            e2 = ev.Enumerate().map(lambda i, c: (i, i + ord(c)))
            e3 = ev.Star().pluck(1).map(chr)

            e1.pipe(e2, e3)     # or: ev.Event.Pipe(e1, e2, e3)
            ->
            ['a', 'c', 'e', 'g', 'i']

        Args:
            targets: One or more Events that have no source yet,
                or ``Event`` constructors that needs no arguments.
        """
        source = self
        for t in targets:
            t = Event.create(t)
            t.set_source(source)
            source = t
        return source

    def fork(self, *targets: "Event") -> "Fork":
        """
        Fork this event into one or more target events.
        Square brackets can be used as a synonym::

            import eventkit as ev

            ev.Range(2, 5)[ev.Min, ev.Max, ev.Sum].zip()
            ->
            [(2, 2, 2), (2, 3, 5), (2, 4, 9)]

        The events in the fork can be combined by one of the join
        methods of ``Fork``.

        Args:
            targets: One or more events that have no source yet,
                or ``Event`` constructors that need no arguments.
        """
        fork = Fork()
        for t in targets:
            t = Event.create(t)
            t.set_source(self)
            fork.append(t)
        return fork

    def set_source(self, source):
        self._source = source

    def _onFinalize(self, ref):
        for slot in self._slots:
            if slot[1] is ref:
                slot[0] = slot[1] = slot[2] = None
        self._slots = [s for s in self._slots if s != [None, None, None]]

    @staticmethod
    def _split(c):
        """
        Split given callable in (object, function) tuple.
        """
        if isinstance(c, types.FunctionType):
            return (None, c)
        elif isinstance(c, types.MethodType):
            return (c.__self__, c.__func__)
        elif isinstance(c, types.BuiltinMethodType):
            if type(c.__self__) is type:
                # built-in method
                return (c.__self__, c)
            else:
                # built-in function
                return (None, c)
        elif hasattr(c, '__call__'):
            return (c, None)
        else:
            raise ValueError(f'Invalid callable: {c}')

    async def aiter(self, skip_to_last: bool = False, tuples: bool = False):
        """
        Create an asynchronous iterator that yields the emitted values
        from this event::

            async def coro():
                async for args in event.aiter():
                    ...

        :meth:`__aiter__` is a synonym for :meth:`aiter` with
        default arguments,

        Args:
            skip_to_last:
                * ``True``: Backlogged source values are skipped over to
                  yield only the latest value. Can be used as a
                  slipper clutch between a source that produces too fast
                  and the handling that can't keep up.
                * ``False``: All events are yielded.
            tuples:
                * ``True``: Always yield arguments as a tuple.
                * ``False``: Unpack single argument tuples.
        """
        def on_event(*args):
            q.put_nowait((None, args))

        def on_error(source, error):
            q.put_nowait(('ERROR', error))

        def on_done(source):
            q.put_nowait(('DONE', None))

        if self.done():
            return
        q = asyncio.Queue()
        self.connect(on_event, on_error, on_done)
        try:
            while True:
                what, args = await q.get()
                if skip_to_last:
                    while q.qsize():
                        what, args = q.get_nowait()
                if what is None:
                    yield args if tuples else args[0] if len(args) == 1 \
                        else args if args else NO_VALUE
                elif what == 'ERROR':
                    raise args
                else:
                    break
        finally:
            self.disconnect(on_event, on_error, on_done)

    __iadd__ = connect
    __isub__ = disconnect
    __call__ = emit
    __or__ = pipe

    def __repr__(self):
        return f'Event<{self.name()}, {self._slots}>'

    def __len__(self):
        return len(self._slots)

    def __bool__(self):
        return True

    def __getitem__(self, fork_targets) -> "Fork":
        if not hasattr(fork_targets, '__iter__'):
            fork_targets = (fork_targets,)
        return self.fork(*fork_targets)

    def __await__(self):
        """
        Asynchronously await the next emit of an event::

            async def coro():
                args = await event
                ...

        If the event does an empty ``emit()``, then the value
        of ``args`` is set to ``util.NO_VALUE``.

        :meth:`wait` and :meth:`__await__` are each other's inverse.
        """
        def on_event(*args):
            if not fut.done():
                fut.set_result(
                    args[0] if len(args) == 1 else args if args else NO_VALUE)

        def on_error(source, error):
            if not fut.done():
                fut.set_exception(error)

        def on_future_done(f):
            self.disconnect(on_event, on_error)

        if self.done():
            raise ValueError('Event already done')
        fut = asyncio.Future()
        self.connect(on_event, on_error)
        fut.add_done_callback(on_future_done)
        return fut.__await__()

    __aiter__ = aiter
    """
    Synonym for :meth:`aiter` with default arguments::

        async def coro():
            async for args in event:
                ...

    :meth:`aiterate` and :meth:`__aiter__` are each other's inverse.
    """

    def __contains__(self, c):
        """
        See if callable is already connected.
        """
        obj, func = self._split(c)
        return any(
            (s[0] is obj or s[1] and s[1]() is obj) and s[2] is func
            for s in self._slots)

    def __reduce__(self):
        """
        Don't pickle slots.
        """
        with_error_done_event = (
            self.error_event is not None or self.done_event is not None)
        return self.__class__, (self._name, with_error_done_event)

    @staticmethod
    def init(obj, event_names: Iterable):
        """
        Convenience function for initializing multiple events as members
        of the given object.

        Args:
            event_names: Names to use for the created events.
        """
        for name in event_names:
            setattr(obj, name, Event(name))

    # dot access to constructors

    @staticmethod
    def create(obj):
        """
        Create an event from a async iterator, awaitable, or event
        constructor without arguments.

        Args:
            obj: The source object. If it's already an event then it
              is passed as-is.
        """
        if isinstance(obj, Event):
            return obj
        if hasattr(obj, '__call__'):
            obj = obj()

        if isinstance(obj, Event):
            return obj
        elif hasattr(obj, '__aiter__'):
            return Event.aiterate(obj)
        elif hasattr(obj, '__await__'):
            return Event.wait(obj)
        else:
            raise ValueError(f'Invalid type: {obj}')

    @staticmethod
    def wait(future: Awaitable) -> "Wait":
        """
        Create a new event that emits the value of the
        awaitable when it becomes available and then set this event done.

        :meth:`wait` and :meth:`__await__` are each other's inverse.

        Args:
            future: Future to wait on.
        """
        return Wait(future)

    @staticmethod
    def aiterate(ait: AsyncIterable) -> "Aiterate":
        """
        Create a new event that emits the yielded values from the
        asynchronous iterator.

        The asynchronous iterator serves as a source for both the time
        and value of emits.

        :meth:`aiterate` and :meth:`__aiter__` are each other's inverse.

        Args:
            ait: The asynchronous source iterator. It must ``await``
                at least once; If necessary use::

                    await asyncio.sleep(0)
        """
        return Aiterate(ait)

    @staticmethod
    def sequence(
            values: Iterable, interval: float = 0,
            times: Iterable[float] = None) -> "Sequence":
        """
        Create a new event that emits the given values.
        Supply at most one ``interval`` or ``times``.

        Args:
            values: The source values.
            interval: Time interval in seconds between values.
            times: Relative times for individual values, in seconds since
                start of event. The sequence should match ``values``.
        """
        return Sequence(values, interval, times)

    @staticmethod
    def repeat(
            value=NO_VALUE, count=1, interval: float = 0,
            times: Iterable[float] = None) -> "Repeat":
        """
        Create a new event that repeats ``value`` a number of ``count`` times.

        Args:
            value: The value to emit.
            count: Number of times to emit.
            interval: Time interval in seconds between values.
            times: Relative times for individual values, in seconds since
                start of event. The sequence should match ``values``.
        """
        return Repeat(interval, value, count)

    @staticmethod
    def range(
            *args, interval: float = 0,
            times: Iterable[float] = None) -> "Range":
        """
        Create a new event that emits the values from a range.

        Args:
            args: Same as for built-in ``range``.
            interval: Time interval in seconds between values.
            times: Relative times for individual values, in seconds since
                start of event. The sequence should match the range.
        """
        return Range(*args, interval=interval, times=times)

    @staticmethod
    def timerange(start=0, end=None, step=1) -> "Timerange":
        """
        Create a new event that emits the datetime value, at that datetime,
        from a range of datetimes.

        Args:
            start: Start time, can be specified as:

                * ``datetime.datetime``.
                * ``datetime.time``: Today is used as date.
                * ``int`` or ``float``: Number of seconds relative to now.
                  Values will be quantized to the given step.
            end: End time, can be specified as:

                * ``datetime.datetime``.
                * ``datetime.time``: Today is used as date.
                * ``None``: No end limit.
            step: Number of seconds, or ``datetime.timedelta``,
                to space between values.
        """
        return Timerange(start, end, step)

    @staticmethod
    def timer(interval: float, count: int = None) -> "Timer":
        """
        Create a new timer event that emits at regularly paced intervals
        the number of seconds since starting it.

        Args:
            interval: Time interval in seconds between emits.
            count: Number of times to emit, or ``None`` for no limit.
        """
        return Timer(interval, count)

    @staticmethod
    def marble(
            s: str, interval: float = 0,
            times: Iterable[float] = None) -> "Marble":
        """
        Create a new event that emits the values from a Rx-type marble string.

        Args:
            s: The string with characters that are emitted.
            interval: Time interval in seconds between values.
            times: Relative times for individual values, in seconds since
                start of event. The sequence should match the marble string.

        """
        return Marble(s, interval, times)

    # dot access to operators

    def filter(self, predicate=bool) -> "Filter":
        """
        For every source value, apply predicate and re-emit when True.

        Args:
            predicate: The function to test every source value with.
                The default is to test the general truthiness with ``bool()``.
        """
        return Filter(predicate, self)

    def skip(self, count: int = 1) -> "Skip":
        """
        Drop the first ``count`` values from source and follow the source
        after that.

        Args:
            count: Number of source values to drop.
        """
        return Skip(count, self)

    def take(self, count: int = 1) -> "Take":
        """
        Re-emit first ``count`` values from the source and then end.

        Args:
            count: Number of source values to re-emit.
        """
        return Take(count, self)

    def takewhile(self, predicate=bool) -> "TakeWhile":
        """
        Re-emit values from the source until the predicate becomes False
        and then end.

        Args:
            predicate: The function to test every source value with.
                The default is to test the general truthiness with ``bool()``.
        """
        return TakeWhile(predicate, self)

    def dropwhile(self, predicate=lambda x: not(x)) -> "DropWhile":
        """
        Drop source values until the predicate becomes False and after that
        re-emit everything from the source.

        Args:
            predicate: The function to test every source value with.
                The default is to test the inverted general truthiness.
        """
        return DropWhile(predicate, self)

    def takeuntil(self, notifier: "Event") -> "TakeUntil":
        """
        Re-emit values from the source until the ``notifier`` emits
        and then end. If the notifier ends without any emit then
        keep passing source values.

        Args:
            notifier: Event that signals to end this event.
        """
        return TakeUntil(notifier, self)

    def constant(self, constant) -> "Constant":
        """
        On emit of the source emit a constant value::

            emit(value) -> emit(constant)

        Args:
            constant: The constant value to emit.
        """
        return Constant(constant, self)

    def iterate(self, it) -> "Iterate":
        """
        On emit of the source, emit the next value from an iterator::

            emit(a, b, ...) -> emit(next(it))

        The time of events follows the source and the values follow
        the iterator.

        Args:
            it: The source iterator to use for generating values. When the
                iterator is exhausted the event is set to be done.
        """
        return Iterate(it, self)

    def count(self, start=0, step=1) -> "Count":
        """
        Count and emit the number of source emits::

            emit(a, b, ...) -> emit(count)

        Args:
            start: Start count.
            step: Add count by this amount for every new source value.
        """
        return Count(start, step, self)

    def enumerate(self, start=0, step=1) -> "Enumerate":
        """
        Add a count to every source value::

            emit(a, b, ...) -> emit(count, a, b, ...)

        Args:
            start: Start count.
            step: Increase by this amount for every new source value.
        """
        return Enumerate(start, step, self)

    def timestamp(self) -> "Timestamp":
        """
        Add a timestamp (from time.time()) to every source value::

            emit(a, b, ...) -> emit(timestamp, a, b, ...)

        The timestamp is the float number in seconds since the
        midnight Jan 1, 1970 epoch.
        """
        return Timestamp(self)

    def partial(self, *left_args) -> "Partial":
        """
        Pad source values with extra arguments on the left::

            emit(a, b, ...) -> emit(*left_args, a, b, ...)

        Args:
            left_args: Arguments to inject.
        """
        return Partial(*left_args, source=self)

    def partial_right(self, *right_args) -> "PartialRight":
        """
        Pad source values with extra arguments on the right::

            emit(a, b, ...) -> emit(a, b, ..., *right_args)

        Args:
            right_args: Arguments to inject.
        """
        return PartialRight(*right_args, source=self)

    def star(self) -> "Star":
        """
        Unpack a source tuple into positional arguments, similar to the
        star operator::

            emit((a, b, ...)) -> emit(a, b, ...)

        :meth:`star` and :meth:`pack` are each other's inverse.
        """
        return Star(self)

    def pack(self) -> "Pack":
        """
        Pack positional arguments into a tuple::

            emit(a, b, ...) -> emit((a, b, ...))

        :meth:`star` and :meth:`pack` are each other's inverse.
        """
        return Pack(self)

    def pluck(self, *selections: Union[int, str]) -> "Pluck":
        """
        Extract arguments or nested properties from the source values.

        Select which argument positions to keep::

            emit(a, b, c, d).pluck(1, 2) -> emit(b, c)

        Re-order arguments::

            emit(a, b, c).pluck(2, 1, 0) -> emit(c, b, a)

        To do an empty emit leave ``selections`` empty::

            emit(a, b).pluck() -> emit()

        Select nested properties from positional arguments::

            emit(person, account).pluck(
                '1.number', '0.address.street') ->

            emit(account.number, person.address.street)

        If no value can be extracted then ``NO_VALUE`` is emitted in its place.

        Args:
            selections: The values to extract.
        """
        return Pluck(*selections, source=self)

    def map(
            self, func, timeout=None, ordered=True,
            task_limit=None) -> "Map":
        """
        Apply a sync or async function to source values using
        positional arguments::

            emit(a, b, ...) -> emit(func(a, b, ...))

        or if ``func`` returns an awaitable then it will be awaited::

            emit(a, b, ...) -> emit(await func(a, b, ...))

        In case of timeout or other failure, ``NO_VALUE`` is emitted.

        Args:
            func: The function or coroutine constructor to apply.
            timeout: Timeout in seconds since coroutine is started
            ordered:
                * ``True``: The order of emitted results preserves the
                  order of the source values.
                * ``False``: Results are in order of completion.
            task_limit: Max number of concurrent tasks, or None for no limit.

        ``timeout``, ``ordered`` and ``task_limit`` apply to
        async functions only.
        """
        return Map(func, timeout, ordered, task_limit, self)

    def emap(self, constr, joiner: "AddableJoinOp") -> "Emap":
        """
        Higher-order event map that creates a new ``Event`` instance
        for every source value::

            emit(a, b, ...) -> new Event constr(a, b, ...)

        Args:
            constr: Constructor function for creating a new event.
                Apart from returning  an ``Event``, the constructor may also
                return an awaitable or an asynchronous iterator, in which
                case an ``Event`` will be created.
            joiner: Join operator to combine the emits of nested events.
        """
        return Emap(constr, joiner, self)

    def mergemap(self, constr) -> "Mergemap":
        """
        :meth:`emap` that uses :meth:`merge` to combine the nested events::

            marbles = [
                'A   B    C    D',
                '_1   2  3    4',
                '__K   L     M   N']

            ev.Range(3).mergemap(lambda v: ev.Marble(marbles[v]))
            ->
            ['A', '1', 'K', 'B', '2', 'L', '3', 'C', 'M', '4', 'D', 'N']
        """
        return Mergemap(constr, self)

    def concatmap(self, constr) -> "Concatmap":
        """
        :meth:`emap` that uses :meth:`concat` to combine the nested events::

            marbles = [
                'A    B    C    D',
                '_       1    2    3    4',
                '__                  K    L      M   N']

            ev.Range(3).concatmap(lambda v: ev.Marble(marbles[v]))
            ->
            ['A', 'B', '1', '2', '3', 'K', 'L', 'M', 'N']
        """
        return Concatmap(constr, self)

    def chainmap(self, constr) -> "Chainmap":
        """
        :meth:`emap` that uses :meth:`chain` to combine the nested events::

            marbles = [
                'A    B    C    D           ',
                '_       1    2    3    4',
                '__                  K    L      M   N']

            ev.Range(3).chainmap(lambda v: ev.Marble(marbles[v]))
            ->
            ['A', 'B', 'C', 'D', '1', '2', '3', '4', 'K', 'L', 'M', 'N']
        """
        return Chainmap(constr, self)

    def switchmap(self, constr) -> "Switchmap":
        """
        :meth:`emap` that uses :meth:`switch` to combine the nested events::

            marbles = [
                'A    B    C    D           ',
                '_                 K    L      M   N',
                '__      1    2      3    4'
            ]
            ev.Range(3).switchmap(lambda v: Event.marble(marbles[v]))
            ->
            ['A', 'B', '1', '2', 'K', 'L', 'M', 'N'])
        """
        return Switchmap(constr, self)

    def reduce(self, func, initializer=NO_VALUE) -> "Reduce":
        """
        Apply a two-argument reduction function to the previous reduction
        result and the current value and emit the new reduction result.

        Args:
            func: Reduction function::

                emit(args) -> emit(func(prev_args, args))

            initializer: First argument of first reduction::

                    first_result = func(initializer, first_value)

                If no initializer is given, then the first result is
                emitted on the second source emit.
        """
        return Reduce(func, initializer, self)

    def min(self) -> "Min":
        """
        Minimum value.
        """
        return Min(self)

    def max(self) -> "Max":
        """
        Maximum value.
        """
        return Max(self)

    def sum(self, start=0) -> "Sum":
        """
        Total sum.

        Args:
            start: Value added to total sum.
        """
        return Sum(start, self)

    def product(self, start=1) -> "Product":
        """
        Total product.

        Args:
            start: Initial start value.
        """
        return Product(start, self)

    def mean(self) -> "Mean":
        """
        Total average.
        """
        return Mean(self)

    def any(self) -> "Any":
        """
        Test if predicate holds for at least one source value.
        """
        return Any(self)

    def all(self) -> "All":
        """
        Test if predicate holds for all source values.
        """
        return All(self)

    def ema(self, n: int = None, weight: float = None) -> "Ema":
        """
        Exponential moving average.

        Args:
            n: Number of periods.
            weight: Weight of new value.

        Give either ``n`` or ``weight``.
        The relation is ``weight = 2 / (n + 1)``.
        """
        return Ema(n, weight, self)

    def previous(self, count: int = 1) -> "Previous":
        """
        For every source value, emit the ``count``-th previous value::

            source:  -ab---c--d-e-
            output:  --a---b--c-d-

        Starts emitting on the ``count + 1``-th source emit.

        Args:
            count: Number of periods to go back.
        """
        return Previous(count, self)

    def pairwise(self) -> "Pairwise":
        """
        Emit ``(previous_source_value, current_source_value)`` tuples.
        Starts emitting on the second source emit::

            source:  -a----b------c--------d-----
            output:  ------(a,b)--(b,c)----(c,d)-
        """
        return Pairwise(self)

    def changes(self) -> "Changes":
        """
        Emit only source values that have changed from the previous value.
        """
        return Changes(self)

    def unique(self, key=None) -> "Unique":
        """
        Emit only unique values, dropping values that have already
        been emitted.

        Args:
            key: `The callable `'key(value)`` is used to group values.
                The default of ``None`` groups values by equality.
                The resulting group must be hashable.
        """
        return Unique(key, self)

    def last(self) -> "Last":
        """
        Wait until source has ended and re-emit its last value.
        """
        return Last(self)

    def list(self) -> "ListOp":
        """
        Collect all source values and emit as list when the source ends.
        """
        return ListOp(self)

    def deque(self, count=0) -> "Deque":
        """
        Emit a ``deque`` with the last ``count`` values from the source
        (or less in the lead-in phase).

        Args:
            count: Number of last periods to use, or 0 to use all.
        """
        return Deque(count, self)

    def array(self, count=0) -> "Array":
        """
        Emit a numpy array with the last ``count`` values from the source
        (or less in the lead-in phase).

        Args:
            count: Number of last periods to use, or 0 to use all.
        """
        return Array(count, self)

    def chunk(self, size: int) -> "Chunk":
        """
        Chunk values up in lists of equal size. The last chunk can be shorter.

        Args:
            size: Chunk size.
        """
        return Chunk(size, self)

    def chunkwith(
            self, timer: "Event", emit_empty: bool = True) -> "ChunkWith":
        """
        Emit a chunked list of values when the timer emits.

        Args:
            timer: Event to use for timing the chunks.
            emit_empty: Emit empty list if no values present since last emit.
        """
        return ChunkWith(timer, emit_empty, self)

    def chain(self, *sources: "Event") -> "Chain":
        """
        Re-emit from a source until it ends, then move to the next source,
        Repeat until all sources have ended, ending the chain.
        Emits from pending sources are queued up::

            source 1:  -a----b---c|
            source 2:        --2-----3--4|
            source 3:  ------------x---------y--|
            output:    -a----b---c2--3--4x---y--|


        Args:
            sources: Source events.
        """
        return Chain(self, *sources)

    def merge(self, *sources) -> "Merge":
        """
        Re-emit everything from the source events::

            source 1:  -a----b-------------c------d-|
            source 2:     ------1-----2------3--4-|
            source 3:      --------x----y--|
            output:    -a----b--1--x--2-y--c-3--4-d-|

        Args:
            sources: Source events.
        """
        return Merge(self, *sources)

    def concat(self, *sources) -> "Concat":
        """
        Re-emit everything from one source until it ends and then move
        to the next source::

            source 1:  -a----b-----|
            source 2:    --1-----2-----3----4--|
            source 3:                 -----------x--y--|
            output:    -a----b---------3----4----x--y--|

        Args:
            sources: Source events.
        """
        return Concat(self, *sources)

    def switch(self, *sources) -> "Switch":
        """
        Re-emit everything from one source and move to another source as soon
        as that other source starts to emit::

            source 1:  -a----b---c-----d---|
            source 2:        -----------x---y-|
            source 3:  ---------1----2----3-----|
            output:    -a----b--1----2--x---y---|

        Args:
            sources: Source events.
        """
        return Switch(self, *sources)

    def zip(self, *sources) -> "Zip":
        """
        Zip sources together: The i-th emit has the i-th value from
        each source as positional arguments. Only emits when each source has
        emtted its i-th value and ends when any source ends::

            source 1:    -a----b------------------c------d---e--f---|
            source 2:    --------1-------2-------3---------4-----|
            output emit: --------(a,1)---(b,2)----(c,3)----(d,4)-|


        Args:
            sources: Source events.
        """
        return Zip(self, *sources)

    def ziplatest(self, *sources, partial: bool = True) -> "Ziplatest":
        """
        Emit zipped values with the latest value from each of the
        source events. Emits every time when a source emits::

            source 1:   -a-------------------b-------c---|
            source 2:   ---------------1--------------------2------|
            output emit: (a,NoValue)---(a,1)-(b,1)---(c,1)--(c,2)--|

        Args:
            sources: Source events.
            partial:
                * True: Use ``NoValue`` for sources that have not emitted yet.
                * False: Wait until all sources have emitted.
        """
        return Ziplatest(self, *sources, partial=partial)

    def delay(self, delay) -> "Delay":
        """
        Time-shift all source events by a delay::

            source:  -abc-d-e---f---|
            output:  ---abc-d-e---f---|

        This applies to the source errors and the source done event as well.

        Args:
            delay: Time delay of all events (in seconds).
        """
        return Delay(delay, self)

    def timeout(self, timeout) -> "Timeout":
        """
        When the source doesn't emit for longer than the timeout period,
        do an empty emit and set this event as done.

        Args:
            timeout: Timeout value.
        """
        return Timeout(timeout, self)

    def throttle(
            self, maximum, interval, cost_func=None) -> "Throttle":
        """
        Limit number of emits per time without dropping values.
        Values that come in too fast are queued and re-emitted as soon
        as allowed by the limits.

        A nested ``status_event`` emits ``True`` when throttling starts
        and ``False`` when throttling ends.

        The limit can be dynamically changed with ``set_limit``.

        Args:
            maximum: Maximum payload per interval.
            interval: Time interval (in seconds).
            cost_func: The sum of ``cost_func(value)`` for every
                source value inside the ``interval`` that is to remain
                under the ``maximum``. The default is to count every
                source value as 1.
        """
        return Throttle(maximum, interval, cost_func, self)

    def debounce(self, delay, on_first: bool = False) -> "Debounce":
        """
        Filter out values from the source that happen in rapid succession.

        Args:
            delay: Maximal time difference (in seconds) between
                successive values before debouncing kicks in.
            on_first:
                * True: First value is send immediately and following values
                  in the rapid succession are dropped::

                    source: -abcd----efg-
                    output: -a-------e---

                * False: Last value of a rapid succession is send after
                  the delay and the values before that are dropped::

                    source:  -abcd----efg--
                    output:   ----d------g-
        """
        return Debounce(delay, on_first, self)

    def copy(self) -> "Copy":
        """
        Create a shallow copy of the source values.
        """
        return Copy(self)

    def deepcopy(self) -> "Deepcopy":
        """
        Create a deep copy of the source values.
        """
        return Deepcopy(self)

    def sample(self, timer: "Event") -> "Sample":
        """
        At the times that the timer emits, sample the value from this
        event and emit the sample.

        Args:
            timer: Event used to time the samples.
        """
        return Sample(timer, self)

    def errors(self) -> "Errors":
        """
        Emit errors from the source.
        """
        return Errors(self)

    def end_on_error(self) -> "EndOnError":
        """
        End on any error from the source.
        """
        return EndOnError(self)


from .ops.op import Op  # noqa
from .ops.create import (
    Wait, Aiterate, Sequence, Repeat, Range, Timerange, Timer, Marble)  # noqa
from .ops.combine import (Fork, AddableJoinOp, Chain, Merge, Concat, Switch,
    Zip, Ziplatest)  # noqa
from .ops.select import (
    Filter, Skip, Take, TakeWhile, DropWhile, TakeUntil, Changes,
    Unique, Last)  # noqa
from .ops.transform import (
    Constant, Iterate, Enumerate, Timestamp, Chunk, ChunkWith,
    Map, Emap, Mergemap, Chainmap, Concatmap, Switchmap,
    Partial, PartialRight, Star, Pack, Pluck,
    Previous, Copy, Deepcopy)  # noqa
from .ops.array import (Array, ArrayMin, ArrayMax, ArraySum,  # noqa
    ArrayProd, ArrayMean, ArrayStd, ArrayAny, ArrayAll) # noqa
from .ops.aggregate import (
    Count, Reduce, Min, Max, Sum, Product, Mean, Any, All,
    Ema, Pairwise, List as ListOp, Deque)  # noqa
from .ops.timing import (
    Delay, Timeout, Throttle, Debounce, Sample)  # noqa
from .ops.misc import Errors, EndOnError  # noqa
