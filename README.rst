|Build| |PyVersion| |Status| |PyPiVersion| |License| |Docs|

About eventkit
--------------

Send events between loosely coupled components,
compose all kinds of data pipelines.

See the examples and the
`introduction notebook <https://github.com/erdewit/eventkit/tree/master/notebooks/eventkit_introduction.ipynb>`_
to get a true feel for the possibilities.

Installation
------------

::

    pip3 install eventkit

Python_ version 3.6 or higher is required.


Examples
--------

**Create an event and connect two listeners**

.. code-block:: python

    import eventkit as ev

    def f(a, b):
        print(a * b)

    def g(a, b):
        print(a / b)

    event = ev.Event()
    event += f
    event += g
    event.emit(10, 5)

**Create a simple pipeline**

.. code-block:: python

    import eventkit as ev

    event = (
        ev.Sequence('abcde')
        .map(str.upper)
        .enumerate()
    )

    print(event.run())  # in Jupyter: await event.list()

Output::

    [(0, 'A'), (1, 'B'), (2, 'C'), (3, 'D'), (4, 'E')]

**Create a pipeline to get a running average and standard deviation**

.. code-block:: python

    import random
    import eventkit as ev

    source = ev.Range(1000).map(lambda i: random.gauss(0, 1))

    event = source.array(500)[ev.ArrayMean, ev.ArrayStd].zip()

    print(event.last().run())  # in Jupyter: await event.last()

Output::

    [(0.00790957852672618, 1.0345673260655333)]

**Combine async iterators together**

.. code-block:: python

    import asyncio
    import eventkit as ev

    async def ait(r):
        for i in r:
            await asyncio.sleep(0.1)
            yield i

    async def main():
        async for t in ev.Zip(ait('XYZ'), ait('123')):
            print(t)

    asyncio.get_event_loop().run_until_complete(main())  # in Jupyter: await main()

Output::

    ('X', '1')
    ('Y', '2')
    ('Z', '3')

**Realtime video analysis pipeline**

.. code-block:: python

    self.video = VideoStream(conf.CAM_ID)
    scene = self.video | FaceTracker | SceneAnalyzer
    lastScene = scene.aiter(skip_to_last=True)
    async for frame, faces, persons in lastScene:
        ...

`Full source code <https://github.com/erdewit/heartwave/blob/396eae46bb975d7f5e3cb943e813996dac951c8d/heartwave/app.py#L88>`_

Distributed computing
---------------------

The `distex <https://github.com/erdewit/distex>`_ library provides a
``poolmap`` extension method to put multiple cores or machines to use:

.. code-block:: python

    from distex import Pool
    import eventkit as ev
    import bz2

    pool = Pool()
    # await pool  # un-comment in Jupyter
    data = [b'A' * 1000000] * 1000

    pipe = ev.Sequence(data).poolmap(pool, bz2.compress).map(len).mean().last()

    print(pipe.run())  # in Jupyter: print(await pipe)
    pool.shutdown()


Inspired by:
------------

    * `Qt Signals & Slots <https://doc.qt.io/qt-5/signalsandslots.html>`_
    * `itertools <https://docs.python.org/3/library/itertools.html>`_
    * `aiostream <https://github.com/vxgmichel/aiostream>`_
    * `Bacon <https://baconjs.github.io/index.html>`_
    * `aioreactive <https://github.com/dbrattli/aioreactive>`_
    * `Reactive extensions <http://reactivex.io/documentation/operators.html>`_
    * `underscore.js <https://underscorejs.org>`_
    * `.NET Events <https://docs.microsoft.com/en-us/dotnet/standard/events>`_

Documentation
-------------

The complete `API documentation <https://eventkit.readthedocs.io/en/latest/api.html>`_.



.. _Python: http://www.python.org
.. _`Interactive Brokers Python API`: http://interactivebrokers.github.io

.. |Build| image:: https://travis-ci.org/erdewit/eventkit
   :alt: Travis build
   :target: https://travis-ci.org/erdewit/eventkit

.. |PyPiVersion| image:: https://img.shields.io/pypi/v/eventkit.svg
   :alt: PyPi
   :target: https://pypi.python.org/pypi/eventkit


.. |PyVersion| image:: https://img.shields.io/badge/python-3.6+-blue.svg
   :alt:

.. |Status| image:: https://img.shields.io/badge/status-beta-green.svg
   :alt:

.. |License| image:: https://img.shields.io/badge/license-BSD-blue.svg
   :alt:

.. |Docs| image:: https://readthedocs.org/projects/eventkit/badge/?version=latest
   :alt: Documentation
   :target: https://eventkit.readthedocs.io


