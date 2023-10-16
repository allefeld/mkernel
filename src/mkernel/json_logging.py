"""JSON Logging: Complete, structured logging to JSON Lines

The idea is that the logfile contains everything, in a structured form enabled
by JSON Lines. A friendly human-readable representation can later be generated
by a viewer.

Usage:
```
# initialization
from json_logging import getJSONLogger, selfless
log = getJSONLogger(__name__)
# e.g. at function start
log.info('called with', extra=selfless(locals()))
# e.g. at function send
log.info('returning', extra={'value': value})
# e.g for harmless exceptions
try:
    ...
except Exception as e:
    log.error('exception', exc_info=e)
```

This module was inspired by
<https://aminalaee.dev/posts/2022/python-json-logging/>. It is not intended as
a package, but as a module which can be copied into projects as needed.

Copyright © 2023 Carsten Allefeld
SPDX-License-Identifier: GPL-3.0-or-later
"""


import json
import logging
from subprocess import Popen, DEVNULL
from shutil import which
from os import getpid, environ
from tempfile import gettempdir


def getJSONLogger(name):
    """obtain JSON Lines logger

    The function replicates `logging.getLogger`, except that
    -   the returned logger is of class `ExtraLogger` to make sure `extra` is
        not folded into the top level of a record,
    -   the log level is set to the minimum (1),
    -   a `logging.FileHandler` writing to `<tempdir>/<name>-<pid>.json.log'`
        is added,
    -   and an instance of `JSONFormatter` is set.

    For debugging it is useful to set the environment variable `JSONLOGVIEWER`
    to an executable. If the variable exists, the function runs the executable
    with the started log file as argument. It is recommended to use
    a jq-based viewer with the expression:
    ```jq
    select(.levelno > 10) | {
        heading: "\\(.levelname) – \\(.asctime)",
        message: "\\(.funcName): \\(.message)",
        extra: .extra,
        location: "\\(.filename):\\(.lineno)"
    } | del(..|nulls)
    ```
    """
    # make sure `extra` is kept separate
    logging.setLoggerClass(ExtraLogger)
    logger = logging.getLogger(name)
    # log everything
    logger.setLevel(1)
    # log to file in JSON Lines format
    filename = f'{gettempdir()}/{name}-{getpid()}.json.log'
    filehandler = logging.FileHandler(filename)
    filehandler.setFormatter(JSONFormatter())
    logger.addHandler(filehandler)
    # run `$JSONLOGVIEWER` on log file
    try:
        jlv = which(environ['JSONLOGVIEWER'])
        Popen([jlv, filename], stdout=DEVNULL, stderr=DEVNULL)
    except Exception:
        pass
    return logger


def selfless(d):
    """utility function to remove `self` from a method's `locals()`"""
    return {k: v for k, v in d.items() if k != 'self'}


class ExtraLogger(logging.Logger):
    """modification of `Logger` to keep `extra` separate"""
    def makeRecord(self, name, level, fn, lno, msg, args, exc_info,
                   func=None, extra=None, sinfo=None):
        # call original implementation with `extra` set to None
        rv = super().makeRecord(name, level, fn, lno, msg, args, exc_info,
                                func=func, extra=None, sinfo=sinfo)
        # add extra as nested dictionary
        rv.__dict__['extra'] = extra
        return rv


class JSONFormatter(logging.Formatter):
    """modification of `Formatter` to write complete log records as JSON"""
    def format(self, record):
        # format message
        record.message = record.getMessage()
        # format time
        record.asctime = self.formatTime(record, self.datefmt)
        # convert to `dict`
        entry = record.__dict__.copy()
        # remove fields made obsolete by `getMessage()`
        entry.pop('msg', None)
        entry.pop('args', None)
        # return as JSON
        return json.dumps(entry, default=repr)
