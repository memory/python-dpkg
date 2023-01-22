#!/usr/bin/env python

"""
dpkg_inspect: a simple tool to dump the control information from
a debian package file using python-dpkg
"""

import glob
import logging
import os
import sys

from pydpkg import Dpkg

logging.basicConfig()
log = logging.getLogger("dpkg_extract")
log.setLevel(logging.INFO)

PRETTY = """Filename: {0}
Size:     {1}
MD5:      {2}
SHA1:     {3}
SHA256:   {4}
Headers:
{5}"""


def indent(input_str, prefix):
    """
    Given a multiline string, return it with every line prefixed by "prefix"
    """
    return "\n".join([f"{prefix}{x}" for x in input_str.split("\n")])


def main():
    """pylint really wants a docstring :)"""
    try:
        file_names = sys.argv[1:]
    except KeyError:
        log.fatal("You must list at least one deb file as an argument")
        sys.exit(1)

    for files in file_names:
        for file_name in glob.glob(files):
            if not os.path.isfile(file_name):
                log.warning("%s is not a file, skipping", file_name)
            log.debug("checking %s", file_name)
            package = Dpkg(file_name)
            print(
                PRETTY.format(
                    file_name,
                    package.filesize,
                    package.md5,
                    package.sha1,
                    package.sha256,
                    indent(str(package), "  "),
                )
            )


if __name__ == "__main__":
    main()
