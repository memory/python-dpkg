"""pydpkg.dpkg.Dpkg: a class to represent dpkg files"""

from __future__ import annotations

# stdlib imports
import hashlib
import logging
import os
from collections import defaultdict
from email import message_from_file, message_from_string
from email.message import Message
from typing import TYPE_CHECKING, Any

# pypi imports
import six
import pgpy


# local imports
from pydpkg.exceptions import (
    DscMissingFileError,
    DscBadChecksumsError,
)
from pydpkg.base import _Dbase

if TYPE_CHECKING:
    from hashlib import _Hash

REQUIRED_HEADERS = ("package", "version", "architecture")


class Dsc(_Dbase):
    """Class allowing import and manipulation of a debian source
    description (dsc) file."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, filename: str | None = None, logger: logging.Logger | None = None) -> None:
        if not isinstance(filename, six.string_types):
            raise TypeError("filename must be a string")

        self.filename = os.path.expanduser(filename)
        self._dirname = os.path.dirname(self.filename)
        self._log = logger or logging.getLogger(__name__)
        self._message: Message[str, str] | None = None
        self._source_files: list[tuple[str, int, bool]] | None = None
        self._sizes: set[tuple[str, int]] | None = None
        self._message_str: str | None = None
        self._checksums: dict[str, dict[str, str]] | None = None
        self._corrected_checksums: dict[str, defaultdict[str, str | None]] | None = None
        self._pgp_message: pgpy.PGPMessage | None = None

    def __repr__(self) -> str:  # type: ignore[explicit-override]
        return repr(self.message_str)

    def __str__(self) -> str:  # type: ignore[explicit-override]
        return six.text_type(self.message_str)  # type: ignore[no-any-return]

    def __getattr__(self, attr: str) -> Any:
        """Overload getattr to treat message headers as object
        attributes (so long as they do not conflict with an existing
        attribute).

        :param attr: string
        :returns: string
        :raises: AttributeError
        """
        self._log.debug("grabbing attr: %s", attr)
        if attr in self.__dict__:
            return self.__dict__[attr]
        # handle attributes with dashes :-(
        munged = attr.replace("_", "-")
        # beware: email.Message[nonexistent] returns None not KeyError
        if munged in self.message:
            return self.message[munged]
        raise AttributeError(f"'Dsc' object has no attribute '{attr}'")

    def get(self, item: str, ret: str | None = None) -> Any | None:
        """Public wrapper for getitem"""
        try:
            return self[item]
        except KeyError:
            return ret

    @property
    def message(self) -> Message[str, str]:
        """Return an email.Message object containing the parsed dsc file"""
        self._log.debug("accessing message property")
        if self._message is None:
            self._message = self._process_dsc_file()
        return self._message

    @property
    def headers(self) -> dict[str, str]:
        """Return a dictionary of the message items"""
        if self._message is None:
            self._message = self._process_dsc_file()
        return dict(self._message.items())

    @property
    def pgp_message(self) -> pgpy.PGPMessage | None:
        """Return a pgpy.PGPMessage object containing the signed dsc
        message (or None if the message is unsigned)"""
        if self._message is None:
            self._message = self._process_dsc_file()
        return self._pgp_message

    @property
    def source_files(self) -> list[str]:
        """Return a list of source files found in the dsc file"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return [x[0] for x in self._source_files]

    @property
    def all_files_present(self) -> bool:
        """Return true if all files listed in the dsc have been found"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return all(x[2] for x in self._source_files)

    @property
    def all_checksums_correct(self) -> bool:
        """Return true if all checksums are correct"""
        return not self.corrected_checksums

    @property
    def corrected_checksums(self) -> dict[str, defaultdict[str, str | None]]:
        """Returns a dict of the CORRECT checksums in any case
        where the ones provided by the dsc file are incorrect."""
        if self._corrected_checksums is None:
            self._corrected_checksums = self._validate_checksums()
        return self._corrected_checksums

    @property
    def missing_files(self) -> list[str]:
        """Return a list of all files from the dsc that we failed to find"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return [x[0] for x in self._source_files if x[2] is False]

    @property
    def sizes(self) -> set[tuple[str, int]]:
        """Return a list of source files found in the dsc file"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return {(x[0], x[1]) for x in self._source_files}

    @property
    def message_str(self) -> str:
        """Return the dsc message as a string

        :returns: string
        """
        if self._message_str is None:
            self._message_str = self.message.as_string()
        return self._message_str

    @property
    def checksums(self) -> dict[str, dict[str, str]]:
        """Return a dictionary of checksums for the source files found
        in the dsc file, keyed first by hash type and then by filename."""
        if self._checksums is None:
            self._checksums = self._process_checksums()
        return self._checksums

    def validate(self) -> None:
        """Raise exceptions if files are missing or checksums are bad."""
        if not self.all_files_present:
            if self._source_files is None:
                raise DscMissingFileError("Source files are not processed")
            raise DscMissingFileError([x[0] for x in self._source_files if not x[2]])
        if not self.all_checksums_correct:
            raise DscBadChecksumsError(self.corrected_checksums)

    def _process_checksums(self) -> dict[str, dict[str, str]]:
        """Walk through the dsc message looking for any keys in the
        format 'Checksum-hashtype'.  Return a nested dictionary in
        the form {hashtype: {filename: {digest}}}"""
        self._log.debug("process_checksums()")
        sums: dict[str, dict[str, str]] = {}
        for key in self.message.keys():
            if key.lower().startswith("checksums"):
                hashtype = key.split("-")[1].lower()
            # grrrrrr debian :( :( :(
            elif key.lower() == "files":
                hashtype = "md5"
            else:
                continue
            sums[hashtype] = {}
            source = self.message[key]
            for line in source.split("\n"):
                if line:  # grrr py3--
                    digest, _, filename = line.strip().split(" ")
                    pathname = os.path.abspath(os.path.join(self._dirname, filename))
                    sums[hashtype][pathname] = digest
        return sums

    def _internalize_message(self, msg: Message[str, str]) -> Message[str, str]:
        """Ugh: the dsc message body may not include a Files or
        Checksums-foo entry for _itself_, which makes for hilarious
        misadventures up the chain.  So, pfeh, we add it."""
        self._log.debug("internalize_message()")
        base = os.path.basename(self.filename)
        size = os.path.getsize(self.filename)
        for key, source in msg.items():
            self._log.debug("processing key: %s", key)
            if key.lower().startswith("checksums"):
                hashtype = key.split("-")[1].lower()
            elif key.lower() == "files":
                hashtype = "md5"
            else:
                continue
            found = []
            for line in source.split("\n"):
                if line:  # grrr
                    found.append(line.strip().split(" "))
            files = [x[2] for x in found]
            if base not in files:
                self._log.debug("dsc file not found in %s: %s", key, base)
                self._log.debug("getting hasher for %s", hashtype)
                hasher: _Hash = getattr(hashlib, hashtype)()
                self._log.debug("hashing file")
                with open(self.filename, "rb") as fileobj:
                    # pylint: disable=cell-var-from-loop
                    for chunk in iter(lambda: fileobj.read(1024), b""):
                        hasher.update(chunk)
                    self._log.debug("completed hashing file")
                self._log.debug("got %s digest: %s", hashtype, hasher.hexdigest())
                newline = f"\n {hasher.hexdigest()} {size} {base}"
                self._log.debug("new line: %s", newline)
                msg.replace_header(key, msg[key] + newline)
        return msg

    def _process_dsc_file(self) -> Message[str, str]:
        """Extract the dsc message from a file: parse the dsc body
        and return an email.Message object.  Attempt to extract the
        RFC822 message from an OpenPGP message if necessary."""
        self._log.debug("process_dsc_file()")
        if not (self.filename.endswith(".dsc") or self.filename.endswith(".dsc.asc")):
            self._log.debug(
                "File %s does not appear to be a dsc file; pressing "
                "on but we may experience some turbulence and possibly "
                "explode.",
                self.filename,
            )
        try:
            self._pgp_message = pgpy.PGPMessage.from_file(self.filename)
            self._log.debug("Found pgp signed message")
        except IOError as ex:
            self._log.fatal('Could not read dsc file "%s": %s', self.filename, ex)
            raise
        except (ValueError, pgpy.errors.PGPError) as ex:
            self._log.warning("dsc file %s is not signed or has a corrupt sig: %s", self.filename, ex)
        if self._pgp_message is not None:
            msg = message_from_string(self._pgp_message.message)
        else:
            with open(self.filename, encoding="UTF-8") as fileobj:
                msg = message_from_file(fileobj)
        return self._internalize_message(msg)

    def _process_source_files(self) -> list[tuple[str, int, bool]]:
        """Walk through the list of lines in the 'Files' section of
        the dsc message, and verify that the file exists in the same
        location on our filesystem as the dsc file.  Return a list
        of tuples: the normalized pathname for the file, the
        size of the file (as claimed by the dsc) and whether the file
        is actually present in the filesystem locally.

        Also extract the file size from the message lines and fill
        out the _files dictionary.
        """
        self._log.debug("process_source_files()")
        filenames: list[tuple[str, int, bool]] = []
        try:
            files = self.message["Files"]
        except KeyError:
            self._log.fatal('DSC file "%s" does not have a Files section', self.filename)
            raise
        for line in files.split("\n"):
            if line:
                _, size, filename = line.strip().split(" ")
                pathname = os.path.abspath(os.path.join(self._dirname, filename))
                filenames.append((pathname, int(size), os.path.isfile(pathname)))
        return filenames

    def _validate_checksums(self) -> dict[str, defaultdict[str, str | None]]:
        """Iterate over the dict of asserted checksums from the
        dsc file.  Check each in turn.  If any checksum is invalid,
        append the correct checksum to a similarly structured dict
        and return them all at the end."""
        self._log.debug("validate_checksums()")
        bad_hashes: defaultdict[str, defaultdict[str, str | None]] = defaultdict(lambda: defaultdict(None))
        for hashtype, filenames in six.iteritems(self.checksums):
            for filename, digest in six.iteritems(filenames):
                hasher: _Hash = getattr(hashlib, hashtype)()
                with open(filename, "rb") as fileobj:
                    # pylint: disable=cell-var-from-loop
                    for chunk in iter(lambda: fileobj.read(128), b""):
                        hasher.update(chunk)
                if hasher.hexdigest() != digest:
                    bad_hashes[hashtype][filename] = hasher.hexdigest()
        return dict(bad_hashes)
