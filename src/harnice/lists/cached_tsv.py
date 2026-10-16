"""Cached read/write for Harnice TSV list files.

Use this instead of ``open()`` / ``csv`` / ``fileio.read_tsv`` for the major
list files (instances list, channel map, circuits list, etc.).

Read
----
::

    from harnice.lists import cached_tsv

    rows = cached_tsv.read(fileio.path("instances list"))
    # -> list of dicts (copies; safe to mutate locally)

Write
-----
Replace the whole file. Disk and the in-memory cache stay in sync::

    cached_tsv.write(fileio.path("instances list"), COLUMNS, rows)

Edit (read → change → write under one lock)
-------------------------------------------
::

    with cached_tsv.edit(fileio.path("instances list"), COLUMNS) as rows:
        rows.append({"instance_name": "foo", ...})
        # file is written when this block exits successfully

``columns`` is the header order to write. Extra keys already on disk, or
present in ``rows`` when the block ends, are appended to that header.
"""

from __future__ import annotations

import csv
import os
import tempfile
import time
from contextlib import contextmanager
from threading import RLock

_lock = RLock()
_cache = {}  # path -> {"signature": (mtime_ns, size), "fieldnames": [...], "rows": [...]}


def _abspath(path):
    return os.path.abspath(os.fspath(path))


def _signature(path):
    stat = os.stat(path)
    return stat.st_mtime_ns, stat.st_size


def _load(path, *, allow_missing=False):
    """Return ``(fieldnames, rows)`` from cache or disk. Caller must hold ``_lock``."""
    path = _abspath(path)
    try:
        signature = _signature(path)
    except FileNotFoundError:
        if allow_missing:
            return [], []
        raise

    cached = _cache.get(path)
    if cached is not None and cached["signature"] == signature:
        return cached["fieldnames"], cached["rows"]

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    _cache[path] = {
        "signature": signature,
        "fieldnames": fieldnames,
        "rows": rows,
    }
    return fieldnames, rows


def _headers(columns, rows, existing_fieldnames=None):
    fieldnames = list(columns)
    for name in existing_fieldnames or []:
        if name not in fieldnames:
            fieldnames.append(name)
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


def _normalize(fieldnames, rows):
    return [
        {
            name: "" if row.get(name) is None else str(row.get(name, ""))
            for name in fieldnames
        }
        for row in rows
    ]


def _write(path, fieldnames, rows):
    """Atomically replace the TSV and refresh the cache. Caller must hold ``_lock``."""
    path = _abspath(path)
    rows = _normalize(fieldnames, rows)
    tmp_fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or None, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
            writer.writeheader()
            writer.writerows(rows)
            f.flush()
            os.fsync(f.fileno())

        for attempt in range(10):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(0.05 * (attempt + 1))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    _cache[path] = {
        "signature": _signature(path),
        "fieldnames": list(fieldnames),
        "rows": rows,
    }


def read(path):
    """Return a copy of every row in the TSV (from cache when possible)."""
    with _lock:
        _, rows = _load(path)
        return [dict(row) for row in rows]


def write(path, columns, rows):
    """Replace the TSV with ``rows`` and update the cache.

    ``columns`` is the header order. Extra keys found in ``rows`` are appended.
    """
    with _lock:
        _write(path, _headers(columns, rows), rows)


@contextmanager
def edit(path, columns, *, allow_missing=False):
    """Read rows, yield a mutable list, write the file when the block succeeds.

    Example::

        with cached_tsv.edit(fileio.path("instances list"), COLUMNS) as rows:
            rows.append({"instance_name": "foo"})
    """
    with _lock:
        existing_fieldnames, existing_rows = _load(path, allow_missing=allow_missing)
        rows = [dict(row) for row in existing_rows]
        yield rows
        _write(path, _headers(columns, rows, existing_fieldnames), rows)
