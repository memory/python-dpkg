"""
Base class to avoid pylint complaining about duplicate code
"""

from __future__ import annotations


class _Dbase:
    # pylint: disable=too-few-public-methods
    def __getitem__(self, item: str) -> str:
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
                return self.__getattr__(item)
            except AttributeError as ex:
                raise KeyError(item) from ex
