"""
Base class to avoid pylint complaining about duplicate code
"""


class _Dbase:
    # pylint: disable=too-few-public-methods
    def __getitem__(self, item):
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
