import asyncio
import datetime
from typing import AsyncIterator


class _NoValue:
    def __bool__(self):
        return False

    def __repr__(self):
        return '<NoValue>'

    __str__ = __repr__


NO_VALUE = _NoValue()

main_event_loop = asyncio.get_event_loop()


async def timerange(start=0, end=None, step: float = 1) \
        -> AsyncIterator[datetime.datetime]:
    """
    Iterator that waits periodically until certain time points are
    reached while yielding those time points.

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
    tz = getattr(start, 'tzinfo', None)
    now = datetime.datetime.now(tz)
    delta = datetime.timedelta(seconds=step)
    t = start
    if t == 0 or isinstance(t, (int, float)):
        t = now + datetime.timedelta(seconds=t)
        # quantize to step
        t = datetime.datetime.fromtimestamp(
            step * int(t.timestamp() / step))
    elif isinstance(t, datetime.time):
        t = datetime.datetime.combine(now.today(), t)

    if t < now:
        # t += delta
        t -= ((t - now) // delta) * delta

    if isinstance(end, datetime.time):
        end = datetime.datetime.combine(now.today(), end)
    elif isinstance(end, (int, float)):
        end = now + datetime.timedelta(seconds=end)

    while end is None or t <= end:
        now = datetime.datetime.now(tz)
        secs = (t - now).total_seconds()
        await asyncio.sleep(secs)
        yield t
        t += delta
