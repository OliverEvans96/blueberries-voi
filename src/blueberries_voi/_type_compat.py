"""Helpers so dataclass type checks survive pytest-xdist dual imports.

Workers can load the same file as both ``blueberries_voi.*`` (editable install)
and ``src.blueberries_voi.*`` (root on ``sys.path``). Those are distinct types
for ``isinstance`` even though they are the same class definition.
"""

from __future__ import annotations

import re

_VOI_TAIL = re.compile(r"(?:^|\.)(blueberries_voi(?:\.\w+)+)$")


def _package_type_key(typ: type) -> tuple[str, str, str]:
    module = typ.__module__
    match = _VOI_TAIL.search(module)
    tail = match.group(1) if match is not None else module
    return (typ.__name__, typ.__qualname__, tail)


def is_same_package_type(obj: object, expected: type) -> bool:
    """True if ``obj`` is ``expected`` or a dual-import twin of that class."""
    if isinstance(obj, expected):
        return True
    return _package_type_key(type(obj)) == _package_type_key(expected)
