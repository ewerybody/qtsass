# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
# Copyright (c) 2015 Yann Lanthony
# Copyright (c) 2017-2018 Spyder Project Contributors
#
# Licensed under the terms of the MIT License
# (See LICENSE.txt for details)
# -----------------------------------------------------------------------------
"""qtsass - Compile SCSS files to valid Qt stylesheets."""

# yapf: disable

from __future__ import absolute_import, print_function

# Standard library imports
from collections import Mapping, Sequence
import logging
import os

# Third party imports
from watchdog.observers import Observer
import sass

# Local imports
from qtsass.conformers import qt_conform, scss_conform
from qtsass.events import SourceEventHandler
from qtsass.functions import qlineargradient, rgba
from qtsass.importers import qss_importer


# yapf: enable

# Constants
DEFAULT_CUSTOM_FUNCTIONS = {'qlineargradient': qlineargradient, 'rgba': rgba}
DEFAULT_SOURCE_COMMENTS = False

# Logger setup
logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger(__name__)


def compile(string, **kwargs):
    """
    Conform and Compile QtSASS source code to CSS.

    This function conforms QtSASS to valid SCSS before passing it to
    sass.compile. Any keyword arguments you provide will be combined with
    qtsass's default keyword arguments and passed to sass.compile.

    .. code-block:: python

        >>> import qtsass
        >>> qtsass.compile("QWidget {background: rgb(0, 0, 0);}")
        QWidget {background:black;}

    :param string: QtSASS source code to conform and compile.
    :param kwargs: Keyword arguments to pass to sass.compile
    :returns: CSS string
    """
    kwargs.setdefault('source_comments', DEFAULT_SOURCE_COMMENTS)
    kwargs.setdefault('custom_functions', [])
    kwargs.setdefault('importers', [])
    kwargs.setdefault('include_paths', [])

    # Add QtSass importers
    if isinstance(kwargs['importers'], Sequence):
        kwargs['importers'] = (list(kwargs['importers']) +
                               [(0, qss_importer(*kwargs['include_paths']))])
    else:
        raise ValueError('Expected Sequence for importers '
                         'got {}'.format(type(kwargs['importers'])))

    # Add QtSass custom_functions
    if isinstance(kwargs['custom_functions'], Sequence):
        kwargs['custom_functions'] = dict(
            DEFAULT_CUSTOM_FUNCTIONS,
            **{fn.__name__: fn
               for fn in kwargs['custom_functions']})
    elif isinstance(kwargs['custom_functions'], Mapping):
        kwargs['custom_functions'].update(DEFAULT_CUSTOM_FUNCTIONS)
    else:
        raise ValueError('Expected Sequence or Mapping for custom_functions '
                         'got {}'.format(type(kwargs['custom_functions'])))

    # Conform QtSass source code
    try:
        kwargs['string'] = scss_conform(string)
    except Exception:
        _log.error('Failed to conform source code')
        raise

    # Compile QtSass source code
    try:
        return qt_conform(sass.compile(**kwargs))
    except sass.CompileError:
        _log.error('Failed to compile source code')
        raise


def compile_filename(input_file, output_file, **kwargs):
    """Compile and save QtSASS file as CSS.

    .. code-block:: python

        >>> import qtsass
        >>> qtsass.compile_filename("dummy.scss", "dummy.css")

    :param input_file: Path to QtSass file.
    :param output_file: Path to write Qt compliant CSS.
    :param kwargs: Keyword arguments to pass to sass.compile
    :returns: CSS string
    """
    input_root = os.path.abspath(os.path.dirname(input_file))
    kwargs.setdefault('include_paths', [input_root])

    with open(input_file, 'r') as f:
        string = f.read()

    _log.debug('Compiling {}...'.format(os.path.normpath(input_file)))
    css = compile(string, **kwargs)

    with open(output_file, 'w') as css_file:
        css_file.write(css)
        _log.info('Created CSS file {}'.format(os.path.normpath(output_file)))
    return css


def compile_dirname(input_dir, output_dir, **kwargs):
    """Compiles QtSASS files in a directory including subdirectories.

    .. code-block:: python

        >>> import qtsass
        >>> qtsass.compile_dirname("./scss", "./css")

    :param input_dir: Directory containing QtSass files.
    :param output_dir: Directory to write compiled Qt compliant CSS files to.
    :param kwargs: Keyword arguments to pass to sass.compile
    """
    kwargs.setdefault('include_paths', [input_dir])

    def is_valid(file_name):
        return not file_name.startswith('_') and file_name.endswith('.scss')

    for root, _, files in os.walk(input_dir):
        relative_root = os.path.relpath(root, input_dir)
        output_root = os.path.join(output_dir, relative_root)
        fkwargs = dict(kwargs)
        fkwargs['include_paths'] = fkwargs['include_paths'] + [root]

        for file_name in [f for f in files if is_valid(f)]:
            scss_path = os.path.join(root, file_name)
            css_file = os.path.splitext(file_name)[0] + '.css'
            css_path = os.path.join(output_root, css_file)

            if not os.path.isdir(output_root):
                os.makedirs(output_root)

            compile_filename(scss_path, css_path, **fkwargs)


def watch(source, destination, compiler=None, recursive=True):
    """
    Watches a source file or directory, compiling QtSass files when modified.

    The compiler function defaults to compile_filename when source is a file
    and compile_dirname when source is a directory.

    :param source: Path to source QtSass file or directory.
    :param destination: Path to output css file or directory.
    :param compiler: Compile function (optional)
    :param recursive: If True, watch subdirectories (default: True).
    :returns: watchdog.Observer
    """
    if os.path.isfile(source):
        watch_dir = os.path.dirname(source)
        compiler = compiler or compile_filename
    elif os.path.isdir(source):
        watch_dir = source
        compiler = compiler or compile_dirname
    else:
        raise ValueError('source arg must be a dirname or filename...')

    event_handler = SourceEventHandler(source, destination, compiler)

    observer = Observer()
    observer.schedule(event_handler, watch_dir, recursive=recursive)
    return observer
