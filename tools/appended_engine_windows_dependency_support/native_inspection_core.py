"""Maintained pure native byte inspectors, extracted without executing a product.

Original definitions: immutable producer3fbc20556abc33366c1288f871ea9e631b9fb77cfe06815aead9a5fda7a56695.
No native/runtime/module admission authority is issued by this byte reader.
"""

import hashlib
import re
import struct

MAX_BINARY = 512 * 1024 * 1024
SYSTEM_IMPORTS = frozenset(('advapi32.dll', 'bcrypt.dll', 'combase.dll', 'crypt32.dll', 'd2d1.dll', 'dwrite.dll', 'gdi32.dll', 'iphlpapi.dll', 'kernel32.dll', 'kernelbase.dll', 'normaliz.dll', 'ntdll.dll', 'ole32.dll', 'oleaut32.dll', 'secur32.dll', 'shell32.dll', 'shlwapi.dll', 'user32.dll', 'version.dll', 'windowscodecs.dll', 'winmm.dll', 'ws2_32.dll'))

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def _span(raw, offset, size, label):
    if offset < 0 or size < 0 or offset > len(raw) or (size > len(raw) - offset):
        raise ValueError('Truncated COFF ' + label)
    return raw[offset:offset + size]

def _directives(raw, allowed_default_libraries=None):
    try:
        text = raw.rstrip(b'\x00').decode('ascii')
    except UnicodeError as error:
        raise ValueError('COFF linker directives must be bounded ASCII') from error
    tokens, cursor = ([], 0)
    while cursor < len(text):
        if text[cursor].isspace():
            cursor += 1
            continue
        token, quoted = ('', False)
        while cursor < len(text) and (quoted or not text[cursor].isspace()):
            char = text[cursor]
            cursor += 1
            if char == '"':
                quoted = not quoted
            else:
                token += char
        if quoted:
            raise ValueError('Unterminated COFF linker directive quote')
        tokens.append(token)
    for token in tokens:
        lowered = token.casefold()
        if not lowered.startswith(('/defaultlib:', '-defaultlib:', '/failifmismatch:', '-failifmismatch:', '/include:', '-include:', '/alternatename:', '-alternatename:', '/merge:', '-merge:', '/section:', '-section:')):
            raise ValueError('COFF archive has an unsupported linker directive; no ambient path/output escape is allowed')
        if lowered.startswith(('/defaultlib:', '-defaultlib:')):
            library = lowered.split(':', 1)[1]
            if library.endswith('.lib'):
                library = library[:-4]
            if not re.fullmatch('[a-z0-9_.-]+', library) or library.startswith(('msvcrt', 'msvcprt', 'ucrt', 'vcruntime', 'concrt', 'vccorlib')) or library in ('libcmtd', 'libcpmtd', 'libvcruntimed', 'libucrtd'):
                raise ValueError('COFF archive requests a dynamic CRT or aliased default library')
            if allowed_default_libraries is not None and library not in allowed_default_libraries:
                raise ValueError('COFF default library escapes the exact static dependency/system library set: ' + library)
        if lowered.startswith(('/failifmismatch:', '-failifmismatch:')) and 'runtimelibrary=' in lowered:
            if lowered.split('runtimelibrary=', 1)[1] != 'mt_staticrelease':
                raise ValueError('COFF archive has a non-/MT Release runtime mismatch')
    return tokens

def inspect_coff_object(raw, *, allowed_default_libraries=None):
    """Strict ordinary COFF/BigObj reader; import objects never count as static."""
    if type(raw) is not bytes or len(raw) < 20 or len(raw) > MAX_BINARY:
        raise ValueError('Bounded COFF object bytes required')
    symbol_size = 18
    if raw[:4] == b'\x00\x00\xff\xff':
        if len(raw) < 56 or struct.unpack_from('<H', raw, 4)[0] != 2 or raw[12:28] != bytes.fromhex('c7a1bad1eebaa94baf20faf66aa4dcb8'):
            raise ValueError('COFF short import/anonymous object is not a static object')
        machine = struct.unpack_from('<H', raw, 6)[0]
        sections, symbols, count = struct.unpack_from('<III', raw, 44)
        header, symbol_size = (56, 20)
    else:
        machine, sections, _timestamp, symbols, count, optional, flags = struct.unpack_from('<HHIIIHH', raw)
        if optional or flags & 8194:
            raise ValueError('COFF archive contains an image or optional header')
        header = 20
    if machine != 34404 or not 1 <= sections <= 65536 or count > 16 * 1024 * 1024:
        raise ValueError('Static Windows archive requires bounded x86_64 COFF objects')
    table_end = header + sections * 40
    _span(raw, header, sections * 40, 'section table')
    strings = b''
    if symbols:
        _span(raw, symbols, count * symbol_size + 4, 'symbol table')
        string_at = symbols + count * symbol_size
        string_size = struct.unpack_from('<I', raw, string_at)[0]
        if string_size < 4:
            raise ValueError('Invalid COFF string table size')
        strings = _span(raw, string_at, string_size, 'string table')
        if symbols < table_end:
            raise ValueError('COFF symbol table overlaps headers')
    elif count:
        raise ValueError('COFF symbols lack their table')
    primary_symbols, symbol_index = (set(), 0)
    while symbol_index < count:
        symbol_at = symbols + symbol_index * symbol_size
        symbol = _span(raw, symbol_at, symbol_size, 'primary symbol')
        auxiliary_count = symbol[-1]
        if auxiliary_count > count - symbol_index - 1:
            raise ValueError('COFF auxiliary symbol records exceed the declared symbol table')
        section = struct.unpack_from('<i' if symbol_size == 20 else '<h', symbol, 12)[0]
        if not -2 <= section <= sections:
            raise ValueError('COFF primary symbol has an invalid section number')
        if symbol[:4] == bytes(4):
            string_offset = struct.unpack_from('<I', symbol, 4)[0]
            if not 4 <= string_offset < len(strings) or strings.find(b'\x00', string_offset) < 0:
                raise ValueError('COFF primary symbol has an invalid long name')
        elif not symbol[:8].split(b'\x00', 1)[0]:
            raise ValueError('COFF primary symbol has an empty name')
        primary_symbols.add(symbol_index)
        symbol_index += 1 + auxiliary_count
    directives = []
    spans = [(0, table_end)]
    if symbols:
        spans.append((symbols, count * symbol_size + len(strings)))
    for index in range(sections):
        at = header + index * 40
        name_raw = raw[at:at + 8].rstrip(b'\x00')
        if name_raw.startswith(b'/'):
            if not name_raw[1:].isdigit() or not strings:
                raise ValueError('Invalid COFF long section name')
            position = int(name_raw[1:])
            _span(strings, position, 1, 'long section name')
            end = strings.find(b'\x00', position)
            if position < 4 or end < 0 or end - position > 128:
                raise ValueError('Unterminated COFF long section name')
            name_raw = strings[position:end]
        try:
            name = name_raw.decode('ascii')
        except UnicodeError as error:
            raise ValueError('Invalid COFF section name') from error
        size, offset, relocations, line_numbers, reloc_count, line_count = struct.unpack_from('<IIIIHH', raw, at + 16)
        if struct.unpack_from('<I', raw, at + 36)[0] & 16777216:
            raise ValueError('COFF relocation-overflow sections need a separate bounded reader')
        if name.startswith('.idata'):
            raise ValueError('COFF archive contains an old-format import-library object')
        for start, length, label in ((offset, size, 'section data'), (relocations, reloc_count * 10, 'relocations'), (line_numbers, line_count * 6, 'line numbers')):
            if length:
                if start < table_end:
                    raise ValueError('COFF data overlaps its headers')
                _span(raw, start, length, label)
                for previous, extent in spans:
                    if start < previous + extent and previous < start + length:
                        raise ValueError('Overlapping COFF data ranges')
                spans.append((start, length))
        for relocation_index in range(reloc_count):
            _address, symbol_index, relocation_type = struct.unpack_from('<IIH', raw, relocations + relocation_index * 10)
            if symbol_index not in primary_symbols:
                raise ValueError('COFF relocation must reference an existing primary symbol, not an absent or auxiliary record')
            if relocation_type > 16:
                raise ValueError('COFF relocation has an unsupported x64 type')
        if name == '.drectve':
            directives.extend(_directives(_span(raw, offset, size, 'directives'), allowed_default_libraries))
    return {'machine': 'x86_64', 'sections': sections, 'directives': directives, 'format': 'coff-bigobj' if symbol_size == 20 else 'coff'}

def inspect_static_archive(raw, *, allowed_default_libraries=None):
    """Read Microsoft regular archives, including its two '/' linker members."""
    if type(raw) is not bytes or not 8 <= len(raw) <= MAX_BINARY or raw[:8] != b'!<arch>\n':
        raise ValueError('Windows dependencies require a bounded regular COFF archive')
    cursor, tables, longnames, members, names, indexes, member_offsets = (8, 0, None, [], set(), [], set())
    while cursor < len(raw):
        if len(members) + tables >= 65536:
            raise ValueError('Windows COFF archive member bound exceeded')
        header_offset = cursor
        header = _span(raw, cursor, 60, 'archive member header')
        cursor += 60
        if header[58:] != b'`\n' or not re.fullmatch(b' *[0-9]+ *', header[48:58]):
            raise ValueError('Malformed Windows COFF archive member header')
        size = int(header[48:58])
        body = _span(raw, cursor, size, 'archive member')
        cursor += size
        if cursor & 1:
            if _span(raw, cursor, 1, 'archive padding') != b'\n':
                raise ValueError('Invalid Windows COFF archive padding')
            cursor += 1
        try:
            name = header[:16].decode('ascii').rstrip(' ')
        except UnicodeError as error:
            raise ValueError('Non-ASCII COFF member name') from error
        if name == '/':
            tables += 1
            if tables > 2 or members or longnames is not None:
                raise ValueError('Misplaced or extra COFF linker table')
            indexes.append(body)
            continue
        if name == '//':
            if longnames is not None or members:
                raise ValueError('Misplaced or repeated COFF long-name table')
            longnames = body
            continue
        if name.startswith('/'):
            if not name[1:].isdigit() or longnames is None:
                raise ValueError('Invalid COFF long-member reference')
            position = int(name[1:])
            _span(longnames, position, 1, 'member name')
            ends = [end for end in (longnames.find(b'\x00', position), longnames.find(b'/\n', position)) if end >= 0]
            if not ends:
                raise ValueError('Unterminated COFF archive member name')
            try:
                name = longnames[position:min(ends)].decode('ascii')
            except UnicodeError as error:
                raise ValueError('Invalid long COFF member name') from error
        else:
            name = name.removesuffix('/')
        if not re.fullmatch('[A-Za-z0-9_.$+()-]{1,240}', name) or name.casefold() in names:
            raise ValueError('Unsafe or repeated COFF archive object name')
        names.add(name.casefold())
        member_offsets.add(header_offset)
        members.append({'name': name, 'sha256': digest(body), **inspect_coff_object(body, allowed_default_libraries=allowed_default_libraries)})
    if not members:
        raise ValueError('Windows static archive contains no actual COFF object')
    for index, body in enumerate(indexes):
        _span(body, 0, 4, 'linker index count')
        count = struct.unpack_from('>I' if index == 0 else '<I', body)[0]
        if count > 1048576:
            raise ValueError('COFF linker index exceeds its symbol/member bound')
        _span(body, 4, count * 4, 'linker index offsets')
        offsets = struct.unpack_from(('>' if index == 0 else '<') + str(count) + 'I', body, 4)
        if any((offset not in member_offsets for offset in offsets)):
            raise ValueError('COFF linker index points outside actual object members')
        cursor = 4 + count * 4
        symbols = count
        if index == 1:
            _span(body, cursor, 4, 'second linker symbol count')
            symbols = struct.unpack_from('<I', body, cursor)[0]
            cursor += 4
            if symbols > 1048576:
                raise ValueError('COFF second linker symbol bound exceeded')
            _span(body, cursor, symbols * 2, 'second linker member indices')
            indices = struct.unpack_from('<' + str(symbols) + 'H', body, cursor)
            if any((not 1 <= value <= count for value in indices)):
                raise ValueError('COFF second linker index has an invalid member number')
            cursor += symbols * 2
        names_raw = body[cursor:]
        if symbols and (not names_raw.endswith(b'\x00') or len(names_raw.split(b'\x00')) != symbols + 1) or (not symbols and names_raw) or any((not name for name in names_raw.split(b'\x00')[:-1])):
            raise ValueError('COFF linker index has an incomplete symbol string table')
    return {'format': 'coff-archive', 'machine': 'x86_64', 'sha256': digest(raw), 'bytes': len(raw), 'members': members}

def inspect_tool_image(raw):
    """Read native tool machine/sections/imports without executing its entrypoint.

    Tool interpreters may use a retained dynamic CRT. That does not relax the
    provider's separate /MT policy. Imported non-system DLLs still need exact
    single-inventory resolution before a tool path joins a candidate plan.
    """
    if type(raw) is not bytes or not 64 <= len(raw) <= MAX_BINARY or raw[:2] != b'MZ':
        raise ValueError('Native Windows tool needs bounded actual PE bytes')
    nt = struct.unpack_from('<I', raw, 60)[0]
    _span(raw, nt, 24, 'tool PE header')
    if nt < 64 or raw[nt:nt + 4] != b'PE\x00\x00':
        raise ValueError('Invalid native tool PE signature')
    machine, count, _timestamp, _symbols, _symbol_count, optional_size, flags = struct.unpack_from('<HHIIIHH', raw, nt + 4)
    if machine != 34404 or not flags & 2 or (not 1 <= count <= 96) or (not 224 <= optional_size <= 4096):
        raise ValueError('Native Windows tool must be a bounded x64 PE image')
    optional = nt + 24
    _span(raw, optional, optional_size, 'tool optional header')
    if struct.unpack_from('<H', raw, optional)[0] != 523:
        raise ValueError('Native Windows tools require PE32+')
    directories = struct.unpack_from('<I', raw, optional + 108)[0]
    if not 14 <= directories <= 16 or 112 + 8 * directories > optional_size:
        raise ValueError('Native tool PE data-directory shape is incomplete')
    headers = struct.unpack_from('<I', raw, optional + 60)[0]
    image_size = struct.unpack_from('<I', raw, optional + 56)[0]
    section_alignment, file_alignment = struct.unpack_from('<II', raw, optional + 32)
    if not 4096 <= section_alignment <= 1 << 20 or section_alignment & section_alignment - 1 or (not 512 <= file_alignment <= 65536) or file_alignment & file_alignment - 1 or (file_alignment > section_alignment) or headers % file_alignment or (image_size <= headers) or image_size % section_alignment:
        raise ValueError('Invalid native tool PE image size or alignment')
    table = optional + optional_size
    _span(raw, table, count * 40, 'tool sections')
    if not table + 40 * count <= headers <= len(raw):
        raise ValueError('Native tool PE headers are truncated')
    sections = []
    for index in range(count):
        virtual, address, size, offset = struct.unpack_from('<IIII', raw, table + index * 40 + 8)
        extent = max(virtual, size)
        if not extent or address < headers or address + extent > image_size or address % section_alignment or (size and (offset < headers or offset % file_alignment or size % file_alignment)):
            raise ValueError('Invalid native tool PE section')
        _span(raw, offset, size, 'tool section data')
        for prior_address, prior_extent, prior_offset, prior_size in sections:
            if address < prior_address + prior_extent and prior_address < address + extent or (size and prior_size and (offset < prior_offset + prior_size) and (prior_offset < offset + size)):
                raise ValueError('Overlapping native tool PE sections')
        sections.append((address, extent, offset, size))

    def rva(address, size):
        matches = [(offset + address - base, extent - (address - base)) for base, _virtual, offset, extent in sections if base <= address and address - base <= extent and (size <= extent - (address - base))]
        if len(matches) != 1:
            raise ValueError('Native tool PE RVA is unbacked or ambiguous')
        return matches[0]

    def directory(index):
        if index >= directories:
            return (0, 0)
        address, size = struct.unpack_from('<II', raw, optional + 112 + index * 8)
        if bool(address) != bool(size):
            raise ValueError('Incomplete native tool PE directory')
        if address:
            rva(address, size)
        return (address, size)
    if any((directory(index) != (0, 0) for index in (11, 13, 14))):
        raise ValueError('Native tool has unsupported bound/delayed/CLR dependencies')
    export_address, export_size = directory(0)
    if export_address:
        export_at, _available = rva(export_address, 40)
        function_count = struct.unpack_from('<I', raw, export_at + 20)[0]
        functions_address = struct.unpack_from('<I', raw, export_at + 28)[0]
        if export_size < 40 or not 1 <= function_count <= 65536 or (not functions_address):
            raise ValueError('Invalid native tool export table')
        functions_at, _available = rva(functions_address, function_count * 4)
        for index in range(function_count):
            address = struct.unpack_from('<I', raw, functions_at + index * 4)[0]
            if export_address <= address < export_address + export_size:
                raise ValueError('Native tool/runtime forwarded exports need a separate closed policy')
    needed, import_count = ([], 0)
    address, size = directory(1)
    if address:
        at, _available = rva(address, size)
        if size < 20:
            raise ValueError('Truncated native tool import descriptors')
        for cursor in range(0, size - 19, 20):
            original, timestamp, chain, name, first = struct.unpack_from('<IIIII', raw, at + cursor)
            if not any((original, timestamp, chain, name, first)):
                break
            if timestamp or chain or (not name) or (not first) or (len(needed) >= 4096):
                raise ValueError('Unsupported native tool import descriptor')
            location, available = rva(name, 1)
            end = raw.find(b'\x00', location, location + min(available, 129))
            if end < 0:
                raise ValueError('Unterminated native tool import basename')
            try:
                library = raw[location:end].decode('ascii')
            except UnicodeError as error:
                raise ValueError('Non-ASCII native tool import') from error
            if not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\\.dll', library, re.I) or library.casefold() in needed:
                raise ValueError('Aliased or repeated native tool import')
            needed.append(library.casefold())
            lookup = original or first
            for index in range(65536):
                lookup_at, _available = rva(lookup + index * 8, 8)
                rva(first + index * 8, 8)
                value = struct.unpack_from('<Q', raw, lookup_at)[0]
                if not value:
                    break
                import_count += 1
                if import_count > 65536:
                    raise ValueError('Native tool PE import-symbol bound exceeded')
                if value & 1 << 63:
                    if value & ~(1 << 63 | 65535) or not value & 65535:
                        raise ValueError('Invalid native tool ordinal import')
                else:
                    if value > 4294967295:
                        raise ValueError('Invalid native tool imported-name RVA width')
                    rva(value, 2)
                    symbol_at, available = rva(value + 2, 1)
                    end = raw.find(b'\x00', symbol_at, symbol_at + min(available, 65536))
                    if end <= symbol_at:
                        raise ValueError('Native tool imported symbol is empty or unterminated')
                    try:
                        raw[symbol_at:end].decode('ascii')
                    except UnicodeError as error:
                        raise ValueError('Non-ASCII native tool imported symbol') from error
            else:
                raise ValueError('Native tool import lookup lacks its bounded terminator')
        else:
            raise ValueError('Native tool imports lack their complete terminator')
    return {'machine': 'x86_64', 'format': 'pe32plus', 'dll': bool(flags & 8192), 'needed': needed}
