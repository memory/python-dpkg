"""
Base class to avoid pylint complaining about duplicate code
"""

from __future__ import annotations

from typing import Any


class _Dbase:
    # pylint: disable=too-few-public-methods
    def __getitem__(self, item: str) -> Any:
        """Overload getitem to treat the message plus our local
        properties as items.

        :param item: string
        :returns: string
        :raises: KeyError
        """
        try:
            return getattr(self, item)
        except AttributeError:
            try:
                return self.__getattr__(item)  # type: ignore[attr-defined]
            except AttributeError as ex:
                raise KeyError(item) from ex
