from ..event import Event
from .op import Op


class Errors(Event):
    __slots__ = ('_source',)

    def __init__(self, source=None):
        Event.__init__(self)
        self._source = source
        if source.done():
            self.set_done()
        else:
            source.error_event += self.emit


class EndOnError(Op):
    __slots__ = ()

    def __init__(self, source=None):
        Op.__init__(self, source)

    def on_source_error(self, error):
        self.disconnect_from(self._source)
        self.error_event.emit(error)
        self.set_done()
