import asyncio
import time
import copy
from collections import deque

from ..util import NO_VALUE

from .op import Op
from .combine import Merge, Chain, Concat, Switch


class Constant(Op):
    __slots__ = ('_constant',)

    def __init__(self, constant, source=None):
        Op.__init__(self, source)
        self._constant = constant

    def on_source(self, *args):
        self.emit(self._constant)


class Iterate(Op):
    __slots__ = ('_it',)

    def __init__(self, it, source=None):
        Op.__init__(self, source)
        self._it = iter(it)

    def on_source(self, *args):
        try:
            value = next(self._it)
            self.emit(value)
        except StopIteration:
            self._disconnect_from(self._source)
            self.set_done()


class Enumerate(Op):
    __slots__ = ('_step', '_i')

    def __init__(self, start=0, step=1, source=None):
        Op.__init__(self, source)
        self._i = start
        self._step = step

    def on_source(self, *args):
        self.emit(
            self._i,
            args[0] if len(args) == 1 else args if args else NO_VALUE)
        self._i += self._step


class Timestamp(Op):
    __slots__ = ()

    def on_source(self, *args):
        self.emit(
            time.time(),
            args[0] if len(args) == 1 else args if args else NO_VALUE)


class Partial(Op):
    __slots__ = ('_left_args',)

    def __init__(self, *left_args, source=None):
        Op.__init__(self, source)
        self._left_args = left_args

    def on_source(self, *args):
        self.emit(*(self._left_args + args))


class PartialRight(Op):
    __slots__ = ('_right_args',)

    def __init__(self, *right_args, source=None):
        Op.__init__(self, source)
        self._right_args = right_args

    def on_source(self, *args):
        self.emit(*(args + self._right_args))


class Star(Op):
    __slots__ = ()

    def on_source(self, arg):
        self.emit(*arg)


class Pack(Op):
    __slots__ = ()

    def on_source(self, *args):
        self.emit(args)


class Pluck(Op):
    __slots__ = ('_selections',)

    def __init__(self, *selections, source=None):
        Op.__init__(self, source)
        self._selections = []  # list of [arg-index, *sub-attributes]
        for sel in selections:
            if type(sel) is int:
                s = [sel]
            else:
                s = sel.split('.')
                if s[0].isdigit():
                    s[0] = int(s[0])
                elif s[0] == '':
                    s[0] = 0
                else:
                    s.insert(0, 0)
            self._selections.append(s)

    def on_source(self, *args):
        values = []
        for s in self._selections:
            try:
                value = args[s[0]]
                for attr in s[1:]:
                    value = getattr(value, attr)
            except Exception:
                value = NO_VALUE
            values.append(value)
        self.emit(*values)


class Previous(Op):
    __slots__ = ('_count', '_q')

    def __init__(self, count=1, source=None):
        Op.__init__(self, source)
        self._count = count
        self._q = deque()

    def on_source(self, *args):
        self._q.append(args)
        if len(self._q) > self._count:
            self.emit(*self._q.popleft())


class Copy(Op):
    __slots__ = ()

    def on_source(self, *args):
        self.emit(*(copy.copy(a) for a in args))


class Deepcopy(Op):
    __slots__ = ()

    def on_source(self, *args):
        self.emit(*copy.deepcopy(args))


class Chunk(Op):
    __slots__ = ('_size', '_list')

    def __init__(self, size, source=None):
        Op.__init__(self, source)
        self._size = size
        self._list = []

    def on_source(self, *args):
        self._list.append(
            args[0] if len(args) == 1 else args if args else NO_VALUE)
        if len(self._list) == self._size:
            self.emit(self._list)
            self._list = []

    def on_source_done(self, source):
        if self._list:
            self.emit(self._list)
        self._disconnect_from(self._source)
        self._source = None
        self.set_done()


class ChunkWith(Op):
    __slots__ = ('_timer', '_list', '_emit_empty')

    def __init__(self, timer, emit_empty, source=None):
        Op.__init__(self, source)
        self._timer = timer
        self._emit_empty = emit_empty
        self._list = []
        timer.connect(
            self._on_timer,
            self.on_source_error,
            self.on_source_done)

    def on_source(self, *args):
        self._list.append(
            args[0] if len(args) == 1 else args if args else NO_VALUE)

    def _on_timer(self, *args):
        if self._list or self._emit_empty:
            self.emit(self._list)
            self._list = []

    def on_source_done(self, source):
        if self._list:
            self.emit(self._list)
            self._list = None
        if self._source is not None:
            self._disconnect_from(self._source)
            self._source = None
        if self._timer is not None:
            self._timer.disconnect(
                self._on_timer,
                self.on_source_error,
                self.on_source_done)
            self._timer = None
        self.set_done()


class Map(Op):
    __slots__ = (
        '_func', '_timeout', '_ordered', '_task_limit', '_coro_q', '_tasks')

    def __init__(
            self, func, timeout=0, ordered=True, task_limit=None, source=None):
        Op.__init__(self, source)
        if source.done():
            return
        self._func = func
        self._timeout = timeout
        self._ordered = ordered
        self._task_limit = task_limit
        self._coro_q = deque()
        self._tasks = deque()

    def on_source(self, *args):
        obj = self._func(*args)
        if hasattr(obj, '__await__'):
            # function returns an awaitable
            if not self._task_limit or len(self._tasks) < self._task_limit:
                # schedule right away
                self._create_task(obj)
            else:
                # queue for later
                self._coro_q.append(obj)
        else:
            # regular function returns the result directly
            self.emit(obj)

    def on_source_done(self, source):
        if not self._tasks:
            # only end when no tasks are pending
            Op.on_source_done(self, self)
        self._source = None

    def _create_task(self, coro):
        # schedule a task to be run
        if self._timeout:
            coro = asyncio.wait_for(coro, self._timeout)
        task = asyncio.ensure_future(coro)
        task.add_done_callback(self._on_task_done)
        self._tasks.append(task)

    def _on_task_done(self, task):
        # handle task result
        tasks = self._tasks
        if self._ordered:
            while tasks and tasks[0].done():
                # remove task after emitting result
                task = tasks[0]
                self._emit_task(task)
                task = tasks.popleft()
        else:
            # remove task after emitting result
            self._emit_task(task)
            tasks.remove(task)

        # schedule pending awaitables from the queue
        while self._coro_q and (
                not self._task_limit or len(tasks) < self._task_limit):
            self._create_task(self._coro_q.popleft())

        # end when source has ended with no pending tasks
        if not tasks and self._source is None:
            Op.on_source_done(self, self)

    def _emit_task(self, task):
        try:
            result = task.result()
        except Exception as error:
            result = NO_VALUE
            self.error_event.emit(error)
        self.emit(result)


class Emap(Op):
    __slots__ = ('_constr', '_joiner',)

    def __init__(self, constr, joiner, source=None):
        Op.__init__(self, source)
        self._constr = constr
        self._joiner = joiner
        joiner.set_parent(source)
        joiner.connect(
            self.emit,
            self.error_event.emit,
            self._on_joiner_done)

    def on_source(self, *args):
        obj = self._constr(*args)
        event = self.create(obj)
        self._joiner.add_source(event)

    def on_source_done(self, source):
        pass

    def _on_joiner_done(self, joiner):
        joiner.disconnect(
            self.emit,
            self.error_event.emit,
            self._on_joiner_done)
        self._joiner = None
        self.set_done()


class Mergemap(Emap):
    __slots__ = ()

    def __init__(self, constr, source=None):
        Emap.__init__(self, constr, Merge(), source)


class Chainmap(Emap):
    __slots__ = ()

    def __init__(self, constr, source=None):
        Emap.__init__(self, constr, Chain(), source)


class Concatmap(Emap):
    __slots__ = ()

    def __init__(self, constr, source=None):
        Emap.__init__(self, constr, Concat(), source)


class Switchmap(Emap):
    __slots__ = ()

    def __init__(self, constr, source=None):
        Emap.__init__(self, constr, Switch(), source)
