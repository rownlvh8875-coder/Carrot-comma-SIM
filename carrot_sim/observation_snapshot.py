"""Read-only observation metadata that remains compatible with JSON/asdict.

Metadata is a data boundary: use JSON scalars/containers (or tuples), not mutable
provider objects. Each observation owns a recursive snapshot of those values.
"""

from __future__ import annotations

from typing import Any


def _readonly(*args: Any, **kwargs: Any) -> None:
    raise TypeError("observation metadata is read-only")


class _SnapshotDict(dict):
    __setitem__ = __delitem__ = clear = pop = popitem = setdefault = update = __ior__ = _readonly

    def __deepcopy__(self, memo: dict) -> _SnapshotDict:
        return self


class _SnapshotList(list):
    __setitem__ = __delitem__ = append = clear = extend = insert = pop = remove = reverse = sort = _readonly
    __iadd__ = __imul__ = _readonly

    def __deepcopy__(self, memo: dict) -> _SnapshotList:
        return self


def freeze_metadata(value: Any) -> Any:
    """Detach nested data and block normal mutation without custom encoders."""
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise TypeError("observation metadata keys must be strings")
        return _SnapshotDict((key, freeze_metadata(item)) for key, item in value.items())
    if isinstance(value, list):
        return _SnapshotList(freeze_metadata(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze_metadata(item) for item in value)
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError("observation metadata must contain only JSON data or tuples")
