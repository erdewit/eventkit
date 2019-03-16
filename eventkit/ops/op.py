from ..event import Event


class Op(Event):
    """
    Base functionality for operators.

    The Observer pattern is implemented by the following three methods::

        on_source(self, *args)
        on_source_error(self, source, error)
        on_source_done(self, source)

    The default handlers will pass along source emits, errors and done events.
    This makes ``Op`` also suitable as an identity operator.
    """
    __slots__ = ()

    def __init__(self, source: Event = None):
        Event.__init__(self)
        if source is not None:
            self.set_source(source)

    on_source = Event.emit

    def on_source_error(self, source, error):
        if len(self.error_event):
            self.error_event.emit(source, error)
        else:
            Event.logger.exception(error)

    def on_source_done(self, source):
        if self._source is not None:
            self._disconnect_from(self._source)
            self._source = None
        self.set_done()

    def set_source(self, source):
        source = Event.create(source)
        if self._source is None:
            self._source = source
            self._connect_from(source)
        else:
            self._source.set_source(source)

    def _connect_from(self, source: Event):
        if source.done():
            self.set_done()
        else:
            source.connect(
                self.on_source,
                self.on_source_error,
                self.on_source_done)

    def _disconnect_from(self, source: Event):
        source.disconnect(
            self.on_source,
            self.on_source_error,
            self.on_source_done)
