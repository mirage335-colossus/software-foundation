"""Small pure value contract for the private builtin-version source candidate.

This module has no filesystem, runtime, process, SDK or admission authority.
"""

import re


KIND = 'foundation-native-engine-runtime-version-v1'


class MissingMethod(ValueError):
    """A named missing semantic method, never a passed observation."""


def closed_fields(value, names, label):
    if type(value) is not dict or set(value) != set(names):
        raise ValueError(label + ' requires its exact closed fields')
    return value


def integer(value, label, min=0, max=2147483647):
    if type(value) is not int or not min <= value <= max:
        raise ValueError(label + ' requires a bounded exact integer')
    return value


def numeric_release(value, label):
    if (type(value) is not str or len(value) > 32 or
            re.fullmatch(r'(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)', value) is None):
        raise ValueError(label + ' requires a canonical numeric triple')
    for part in value.split('.'):
        integer(int(part), label + ' component')
    return value


def explicit_path(value, label):
    """Bound a declaration; the native issuer must admit its physical identity."""
    if (type(value) is not str or not 1 <= len(value) <= 4096 or
            any(ord(character) < 32 or ord(character) == 127 for character in value)):
        raise ValueError(label + ' requires an explicit bounded path declaration')
    return value
