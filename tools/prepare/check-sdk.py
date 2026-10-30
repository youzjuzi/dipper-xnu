#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare an SDK directory with the pinned upstream Git tree, without modifying it."""
import argparse
import hashlib
import os
from pathlib import Path

EXPECTED_TREE = '81466d46b666daa04ae3d2b0b9d5324f0f621359'


def git_hash(kind, content):
    return hashlib.sha1(kind + b' ' + str(len(content)).encode() + b'\0' + content).digest()


def tree(path):
    entries = []
    count = 0
    for child in path.iterdir():
        name = os.fsencode(child.name)
        if child.is_symlink():
            mode, data = b'120000', os.fsencode(os.readlink(child))
        elif child.is_dir():
            digest, children = tree(child)
            if children:
                entries.append((name + b'/', b'40000 ' + name + b'\0' + digest))
                count += children
            continue
        elif child.is_file():
            mode = b'100755' if child.stat().st_mode & 0o100 else b'100644'
            data = child.read_bytes()
        else:
            raise ValueError('Unsupported SDK entry: ' + str(child))
        entries.append((name, mode + b' ' + name + b'\0' + git_hash(b'blob', data)))
        count += 1
    return git_hash(b'tree', b''.join(raw for _, raw in sorted(entries))), count


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdk', type=Path)
    args = parser.parse_args()
    actual, count = tree(args.sdk)
    if actual.hex() != EXPECTED_TREE:
        raise SystemExit('SDK tree mismatch: ' + actual.hex() + '; expected ' + EXPECTED_TREE)
    print('PASS iPhoneOS16.5.sdk: %d files, Git tree %s' % (count, actual.hex()))
