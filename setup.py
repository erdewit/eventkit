import os
import codecs
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with codecs.open(os.path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

__version__ = None
exec(open(os.path.join(here, 'eventkit', 'version.py')).read())

setup(
    name='eventkit',
    version=__version__,
    description='Event-driven data pipelines',
    long_description=long_description,
    url='https://github.com/erdewit/eventkit',
    author='Ewald R. de Wit',
    author_email='ewald.de.wit@gmail.com',
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3 :: Only',
    ],
    keywords=('python asyncio event driven data pipelines'),
    packages=find_packages(),
    test_suite="tests",
    install_requires=['numpy'],
)
