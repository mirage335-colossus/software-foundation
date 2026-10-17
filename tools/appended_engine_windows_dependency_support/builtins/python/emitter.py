"""Source-only fixed builtin emitter. Never import this file in parser fixtures."""

import sys


if len(sys.argv) != 1:
    raise ValueError('runtime version emitter accepts no arguments')


def ascii_string(value):
    if type(value) is not str or not 1 <= len(value) <= 64:
        raise ValueError('runtime implementation name must be bounded')
    if any(ord(character) < 32 or ord(character) > 126 for character in value):
        raise ValueError('runtime implementation name must be printable ASCII')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def version_fields(value):
    numbers = (value.major, value.minor, value.micro, value.serial)
    if any(type(number) is not int or not 0 <= number <= 2147483647
           for number in numbers):
        raise ValueError('runtime version fields must be bounded integers')
    if (type(value.releaselevel) is not str or
            value.releaselevel not in ('alpha', 'beta', 'candidate', 'final')):
        raise ValueError('unknown runtime releaselevel')
    return ('{"major":%d,"minor":%d,"micro":%d,"releaselevel":"%s","serial":%d}'
            % (value.major, value.minor, value.micro, value.releaselevel, value.serial))


output = ('{"schema_version":1,"kind":"foundation-native-engine-runtime-version-v1",'
          '"role":"python","implementation":' + ascii_string(sys.implementation.name) +
          ',"version_info":' + version_fields(sys.version_info) +
          ',"implementation_version":' + version_fields(sys.implementation.version) + '}\n')
raw = output.encode('ascii')
if len(raw) > 4096:
    raise ValueError('runtime builtin output exceeds source bound')
if sys.stdout.buffer.write(raw) != len(raw):
    raise OSError('incomplete runtime builtin write')
sys.stdout.flush()
sys.stdout.close()
