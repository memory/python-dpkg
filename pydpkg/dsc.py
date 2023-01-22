""" pydpkg.dpkg.Dpkg: a class to represent dpkg files """

# stdlib imports
import hashlib
import logging
import os
from collections import defaultdict
from email import message_from_file, message_from_string

import pgpy

# pypi imports
import six

# local imports
from pydpkg.exceptions import (
    DscMissingFileError,
    DscBadChecksumsError,
)
from pydpkg.base import _Dbase

REQUIRED_HEADERS = ("package", "version", "architecture")


class Dsc(_Dbase):
    """Class allowing import and manipulation of a debian source
    description (dsc) file."""

    # pylint: disable=too-many-instance-attributes
    def __init__(self, filename=None, logger=None):
        self.filename = os.path.expanduser(filename)
        self._dirname = os.path.dirname(self.filename)
        self._log = logger or logging.getLogger(__name__)
        self._message = None
        self._source_files = None
        self._sizes = None
        self._message_str = None
        self._checksums = None
        self._corrected_checksums = None
        self._pgp_message = None

    def __repr__(self):
        return repr(self.message_str)

    def __str__(self):
        return six.text_type(self.message_str)

    def __getattr__(self, attr):
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

    def get(self, item, ret=None):
        """Public wrapper for getitem"""
        try:
            return self[item]
        except KeyError:
            return ret

    @property
    def message(self):
        """Return an email.Message object containing the parsed dsc file"""
        self._log.debug("accessing message property")
        if self._message is None:
            self._message = self._process_dsc_file()
        return self._message

    @property
    def headers(self):
        """Return a dictionary of the message items"""
        if self._message is None:
            self._message = self._process_dsc_file()
        return dict(self._message.items())

    @property
    def pgp_message(self):
        """Return a pgpy.PGPMessage object containing the signed dsc
        message (or None if the message is unsigned)"""
        if self._message is None:
            self._message = self._process_dsc_file()
        return self._pgp_message

    @property
    def source_files(self):
        """Return a list of source files found in the dsc file"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return [x[0] for x in self._source_files]

    @property
    def all_files_present(self):
        """Return true if all files listed in the dsc have been found"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return all(x[2] for x in self._source_files)

    @property
    def all_checksums_correct(self):
        """Return true if all checksums are correct"""
        return not self.corrected_checksums

    @property
    def corrected_checksums(self):
        """Returns a dict of the CORRECT checksums in any case
        where the ones provided by the dsc file are incorrect."""
        if self._corrected_checksums is None:
            self._corrected_checksums = self._validate_checksums()
        return self._corrected_checksums

    @property
    def missing_files(self):
        """Return a list of all files from the dsc that we failed to find"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return [x[0] for x in self._source_files if x[2] is False]

    @property
    def sizes(self):
        """Return a list of source files found in the dsc file"""
        if self._source_files is None:
            self._source_files = self._process_source_files()
        return {(x[0], x[1]) for x in self._source_files}

    @property
    def message_str(self):
        """Return the dsc message as a string

        :returns: string
        """
        if self._message_str is None:
            self._message_str = self.message.as_string()
        return self._message_str

    @property
    def checksums(self):
        """Return a dictionary of checksums for the source files found
        in the dsc file, keyed first by hash type and then by filename."""
        if self._checksums is None:
            self._checksums = self._process_checksums()
        return self._checksums

    def validate(self):
        """Raise exceptions if files are missing or checksums are bad."""
        if not self.all_files_present:
            raise DscMissingFileError([x[0] for x in self._source_files if not x[2]])
        if not self.all_checksums_correct:
            raise DscBadChecksumsError(self.corrected_checksums)

    def _process_checksums(self):
        """Walk through the dsc message looking for any keys in the
        format 'Checksum-hashtype'.  Return a nested dictionary in
        the form {hashtype: {filename: {digest}}}"""
        self._log.debug("process_checksums()")
        sums = {}
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

    def _internalize_message(self, msg):
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
                hasher = getattr(hashlib, hashtype)()
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

    def _process_dsc_file(self):
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
            self._log.warning(
                "dsc file %s is not signed or has a corrupt sig: %s", self.filename, ex
            )
        if self._pgp_message is not None:
            msg = message_from_string(self._pgp_message.message)
        else:
            with open(self.filename, encoding="UTF-8") as fileobj:
                msg = message_from_file(fileobj)
        return self._internalize_message(msg)

    def _process_source_files(self):
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
        filenames = []
        try:
            files = self.message["Files"]
        except KeyError:
            self._log.fatal(
                'DSC file "%s" does not have a Files section', self.filename
            )
            raise
        for line in files.split("\n"):
            if line:
                _, size, filename = line.strip().split(" ")
                pathname = os.path.abspath(os.path.join(self._dirname, filename))
                filenames.append((pathname, int(size), os.path.isfile(pathname)))
        return filenames

    def _validate_checksums(self):
        """Iterate over the dict of asserted checksums from the
        dsc file.  Check each in turn.  If any checksum is invalid,
        append the correct checksum to a similarly structured dict
        and return them all at the end."""
        self._log.debug("validate_checksums()")
        bad_hashes = defaultdict(lambda: defaultdict(None))
        for hashtype, filenames in six.iteritems(self.checksums):
            for filename, digest in six.iteritems(filenames):
                hasher = getattr(hashlib, hashtype)()
                with open(filename, "rb") as fileobj:
                    # pylint: disable=cell-var-from-loop
                    for chunk in iter(lambda: fileobj.read(128), b""):
                        hasher.update(chunk)
                if hasher.hexdigest() != digest:
                    bad_hashes[hashtype][filename] = hasher.hexdigest()
        return dict(bad_hashes)
