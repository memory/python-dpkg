""" pydpkg.exceptions: what it says on the tin """


class DpkgError(Exception):
    """Base error class for Dpkg errors"""


class DscError(Exception):
    """Base error class for Dsc errors"""


class DpkgVersionError(DpkgError):
    """Corrupt or unparseable version string"""


class DpkgMissingControlFile(DpkgError):
    """No control file found in control.tar.gz/xz/zst"""


class DpkgMissingControlGzipFile(DpkgError):
    """No control.tar.gz/xz/zst file found in dpkg file"""


class DpkgMissingRequiredHeaderError(DpkgError):
    """Corrupt package missing a required header"""


class DscMissingFileError(DscError):
    """We were not able to find some of the files listed in the dsc"""


class DscBadChecksumsError(DscError):
    """Some of the files in the dsc have incorrect checksums"""


class DscBadSignatureError(DscError):
    """A dsc file has an invalid openpgp signature(s)"""
