#!/usr/bin/env python3
"""Pure synthetic native dynamic-table parsing; never load or execute an image."""
import importlib.util
import os
from pathlib import Path
import struct
import sys
import unittest

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
_source=os.environ.get('FOUNDATION_NATIVE_PARSER_TEST_SOURCE')
if _source:
    _spec=importlib.util.spec_from_file_location('explicit_native_parser_test_source',_source)
    parser=importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(parser)
else:
    import appended_engine_native_consumer as parser


def _gnu_hash(value):
    result=5381
    for byte in value.encode():result=((result<<5)+result+byte)&0xffffffff
    return result


def elf_fixture(*,processor='x86_64',versioned=True,defined_version=False,gnu=False,dual_empty_gnu=False):
    """Structured ELF tables only; these bytes contain no executable program."""
    strings=bytearray(b'\0')
    indexes={}
    for value in ['bib_engine_get_provider_v1','puts','weak_hook','libz.so','liba.so',
                  'GLIBC_2.2.5','fixture.so','$ORIGIN/private:$ORIGIN','VER_1']:
        indexes[value]=len(strings);strings.extend(value.encode()+b'\0')
    names=['bib_engine_get_provider_v1','puts','weak_hook']
    symbols=bytes(24)+b''.join(struct.pack('<IBBHQQ',indexes[value],0x22 if value=='weak_hook' else 0x12,
        0,1 if ordinal==0 else 0,0x1100 if ordinal==0 else 0,0) for ordinal,value in enumerate(names))
    chunks=[]
    def add(label,type_,body,link=0,info=0,entsize=0):
        chunks.append({'label':label,'type':type_,'body':bytes(body),'link':link,'info':info,'entsize':entsize})
    add('strings',3,strings)
    add('symbols',11,symbols,link=1,info=1,entsize=24)
    if not gnu:
        add('hash',5,struct.pack('<IIIIIII',1,4,1,0,2,3,0),link=2,entsize=4)
    if gnu or dual_empty_gnu:
        hashes=[_gnu_hash(value) for value in names]
        bloom=0
        for value in hashes:bloom|=(1<<(value%64))|(1<<((value>>5)%64))
        body=(struct.pack('<IIIIQ',1,4,1,5,0)+struct.pack('<I',0)) if dual_empty_gnu else (
            struct.pack('<IIIIQ',1,1,1,5,bloom)+struct.pack('<I',1)
            +b''.join(struct.pack('<I',(value&~1)|(1 if index==len(hashes)-1 else 0)) for index,value in enumerate(hashes)))
        add('gnu_hash',0x6ffffff6,body,link=2)
    if versioned:
        add('versym',0x6fffffff,struct.pack('<HHHH',0,3 if defined_version else 1,2,1),link=2,entsize=2)
        need=struct.pack('<HHIII',1,1,indexes['libz.so'],16,0)+struct.pack('<IHHII',0,0,2,indexes['GLIBC_2.2.5'],0)
        add('verneed',0x6ffffffe,need,link=1,info=1)
        if defined_version:
            definition=struct.pack('<HHHHIII',1,0,3,1,0,20,0)+struct.pack('<II',indexes['VER_1'],0)
            add('verdef',0x6ffffffd,definition,link=1,info=1)
    offset=256
    for item in chunks:
        offset=(offset+7)//8*8;item['offset']=offset;item['address']=0x1000+offset;offset+=len(item['body'])
    by_name={item['label']:item for item in chunks}
    tags=[(1,indexes['libz.so']),(1,indexes['liba.so']),(5,by_name['strings']['address']),
          (10,len(strings)),(6,by_name['symbols']['address']),(11,24),(14,indexes['fixture.so']),
          (29,indexes['$ORIGIN/private:$ORIGIN'])]
    if 'hash' in by_name:tags.append((4,by_name['hash']['address']))
    if 'gnu_hash' in by_name:tags.append((0x6ffffef5,by_name['gnu_hash']['address']))
    if versioned:
        tags.extend([(0x6ffffff0,by_name['versym']['address']),(0x6ffffffe,by_name['verneed']['address']),(0x6fffffff,1)])
        if defined_version:tags.extend([(0x6ffffffc,by_name['verdef']['address']),(0x6ffffffd,1)])
    tags.append((0,0))
    add('dynamic',6,b''.join(struct.pack('<qQ',*value) for value in tags),link=1,entsize=16)
    item=chunks[-1];offset=(offset+7)//8*8;item['offset']=offset;item['address']=0x1000+offset;offset+=len(item['body'])
    by_name['dynamic']=item
    section_table=(offset+63)//64*64
    count=len(chunks)+1
    total=section_table+count*64
    raw=bytearray(total)
    raw[:16]=b'\x7fELF\x02\x01\x01'+b'\0'*9
    struct.pack_into('<HHIQQQIHHHHHH',raw,16,3,62 if processor=='x86_64' else 183,1,0,64,section_table,0,64,56,2,64,count,0)
    struct.pack_into('<IIQQQQQQ',raw,64,1,5,0,0x1000,0x1000,total,total,4096)
    dynamic=by_name['dynamic']
    struct.pack_into('<IIQQQQQQ',raw,120,2,4,dynamic['offset'],dynamic['address'],dynamic['address'],len(dynamic['body']),len(dynamic['body']),8)
    for index,item in enumerate(chunks,1):
        raw[item['offset']:item['offset']+len(item['body'])]=item['body']
        item['section_offset']=section_table+64*index
        struct.pack_into('<IIQQQQIIQQ',raw,item['section_offset'],0,item['type'],2,item['address'],item['offset'],len(item['body']),item['link'],item['info'],8,item['entsize'])
    return bytes(raw),by_name,indexes


def pe_fixture():
    """One synthetic PE section with complete export/import tables, no execution."""
    raw=bytearray(2048)
    raw[:2]=b'MZ';struct.pack_into('<I',raw,60,128);raw[128:132]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',raw,132,0x8664,1,0,0,0,240,0x2022)
    optional=152
    struct.pack_into('<H',raw,optional,0x20b)
    struct.pack_into('<Q',raw,optional+24,0x180000000)
    struct.pack_into('<II',raw,optional+32,4096,512)
    struct.pack_into('<II',raw,optional+56,8192,512)
    struct.pack_into('<I',raw,optional+108,16)
    struct.pack_into('<II',raw,optional+112,0x1000,0x100)
    struct.pack_into('<II',raw,optional+120,0x1100,40)
    section=392
    raw[section:section+8]=b'.rdata\0\0'
    struct.pack_into('<IIII',raw,section+8,0x1000,0x1000,1536,512)
    struct.pack_into('<I',raw,section+36,0x60000020)
    struct.pack_into('<IIHHIIIIIII',raw,512,0,0,0,0,0x1028,1,1,1,0x1058,0x1060,0x1068)
    raw[552:552+12]=b'fixture.dll\0'
    struct.pack_into('<I',raw,600,0x1300)
    struct.pack_into('<I',raw,608,0x1070)
    struct.pack_into('<H',raw,616,0)
    raw[624:624+len(b'bib_engine_get_provider_v1\0')]=b'bib_engine_get_provider_v1\0'
    struct.pack_into('<IIIII',raw,768,0x1240,0,0,0x1200,0x1260)
    raw[1024:1024+13]=b'KERNEL32.dll\0'
    for offset in (1088,1120):struct.pack_into('<QQQ',raw,offset,0x1280,(1<<63)|7,0)
    struct.pack_into('<H',raw,1152,0);raw[1154:1160]=b'Sleep\0'
    return bytes(raw)


class NativeBinaryTests(unittest.TestCase):
    def test_elf_actual_tables_include_versions_and_unresolved_unversioned_library(self):
        raw,_,_=elf_fixture()
        value=parser.scan_native_binary(raw)
        self.assertEqual(value,{'format':'elf64-le','machine':'x86_64','pointer_bits':64,
            'exports':['bib_engine_get_provider_v1'],
            'imports':[{'library':'libz.so','symbol':'puts','version':'GLIBC_2.2.5'},
                       {'library':None,'symbol':'weak_hook','version':None}],
            'needed':['libz.so','liba.so'],'soname':'fixture.so','runpath':['$ORIGIN/private','$ORIGIN']})

    def test_elf_aarch64_and_defined_export_version(self):
        raw,_,_=elf_fixture(processor='aarch64',defined_version=True)
        self.assertEqual(parser.scan_native_binary(raw)['machine'],'aarch64')

    def test_gnu_hash_real_bloom_bucket_chain_is_joined(self):
        raw,_,_=elf_fixture(gnu=True)
        self.assertEqual(parser.scan_native_binary(raw)['exports'],['bib_engine_get_provider_v1'])

    def test_dual_hash_getter_missing_from_gnu_is_refused(self):
        raw,_,_=elf_fixture(dual_empty_gnu=True)
        with self.assertRaisesRegex(parser.NativeBinaryError,'loader hashes'):
            parser.scan_native_binary(raw)

    def test_sysv_hash_cycle_is_refused(self):
        raw,tables,_=elf_fixture();bad=bytearray(raw)
        struct.pack_into('<I',bad,tables['hash']['offset']+8+4+4*3,1)
        with self.assertRaisesRegex(parser.NativeBinaryError,'Cyclic'):
            parser.scan_native_binary(bytes(bad))

    def test_gnu_bloom_and_chain_tampering_is_refused(self):
        raw,tables,_=elf_fixture(gnu=True)
        for offset in (tables['gnu_hash']['offset']+16,tables['gnu_hash']['offset']+28):
            bad=bytearray(raw)
            if offset==tables['gnu_hash']['offset']+16:struct.pack_into('<Q',bad,offset,0)
            else:bad[offset]^=0x20
            with self.subTest(offset=offset),self.assertRaises(parser.NativeBinaryError):
                parser.scan_native_binary(bytes(bad))

    def test_section_dynamic_decoy_cannot_replace_actual_program_dynamic(self):
        raw,tables,_=elf_fixture();bad=bytearray(raw)
        struct.pack_into('<Q',bad,120+8,tables['dynamic']['offset']+16)
        with self.assertRaisesRegex(parser.NativeBinaryError,'PT_DYNAMIC'):
            parser.scan_native_binary(bytes(bad))

    def test_symbol_section_wrong_file_mapping_is_refused(self):
        raw,tables,_=elf_fixture();bad=bytearray(raw)
        struct.pack_into('<Q',bad,tables['symbols']['section_offset']+24,tables['symbols']['offset']+8)
        with self.assertRaisesRegex(parser.NativeBinaryError,'load mapping'):
            parser.scan_native_binary(bytes(bad))

    def test_import_version_index_requires_actual_matching_verneed(self):
        raw,tables,_=elf_fixture();bad=bytearray(raw)
        struct.pack_into('<H',bad,tables['versym']['offset']+4,9)
        with self.assertRaisesRegex(parser.NativeBinaryError,'version index'):
            parser.scan_native_binary(bytes(bad))

    def test_nondefault_version_only_elf_getter_is_refused(self):
        raw,tables,_=elf_fixture(defined_version=True);bad=bytearray(raw)
        struct.pack_into('<H',bad,tables['versym']['offset']+2,0x8003)
        with self.assertRaisesRegex(parser.NativeBinaryError,'nondefault'):
            parser.scan_native_binary(bytes(bad))

    def test_elf_getter_object_and_ifunc_types_are_refused(self):
        raw,tables,_=elf_fixture()
        for symbol_type in (1,10):
            bad=bytearray(raw)
            bad[tables['symbols']['offset']+24+4]=0x10|symbol_type
            with self.subTest(symbol_type=symbol_type),self.assertRaisesRegex(parser.NativeBinaryError,'ordinary function'):
                parser.scan_native_binary(bytes(bad))

    def test_elf_getter_requires_file_backed_executable_load_memory(self):
        raw,tables,_=elf_fixture()
        for changed in ('non-executable','outside-load','zero-fill-only'):
            bad=bytearray(raw)
            if changed=='non-executable':struct.pack_into('<I',bad,68,4)
            elif changed=='outside-load':struct.pack_into('<Q',bad,tables['symbols']['offset']+24+8,0x800000)
            else:
                struct.pack_into('<Q',bad,64+40,len(raw)+4096)
                struct.pack_into('<Q',bad,tables['symbols']['offset']+24+8,0x1000+len(raw)+8)
            with self.subTest(changed=changed),self.assertRaisesRegex(parser.NativeBinaryError,'executable memory'):
                parser.scan_native_binary(bytes(bad))

    def test_version_need_library_must_be_in_actual_needed(self):
        raw,tables,indexes=elf_fixture();bad=bytearray(raw)
        struct.pack_into('<I',bad,tables['verneed']['offset']+4,indexes['fixture.so'])
        with self.assertRaisesRegex(parser.NativeBinaryError,'version-need'):
            parser.scan_native_binary(bytes(bad))

    def test_elf_rpath_is_an_explicit_unsupported_shape(self):
        raw,tables,_=elf_fixture();bad=bytearray(raw)
        for offset in range(tables['dynamic']['offset'],tables['dynamic']['offset']+len(tables['dynamic']['body']),16):
            if struct.unpack_from('<q',bad,offset)[0]==29:struct.pack_into('<q',bad,offset,15)
        with self.assertRaisesRegex(parser.NativeBinaryError,'RPATH'):
            parser.scan_native_binary(bytes(bad))

    def test_pe_names_ordinals_import_library_and_exports_are_actual_table_reads(self):
        self.assertEqual(parser.scan_native_binary(pe_fixture()),{'format':'pe32plus','machine':'x86_64','pointer_bits':64,
            'exports':['bib_engine_get_provider_v1'],'imports':[{'library':'KERNEL32.dll','symbol':'#7','version':None},
                {'library':'KERNEL32.dll','symbol':'Sleep','version':None}],
            'needed':['KERNEL32.dll'],'soname':None,'runpath':[]})

    def test_pe_forwarded_getter_is_refused(self):
        bad=bytearray(pe_fixture());struct.pack_into('<I',bad,600,0x10c0)
        bad[704:704+15]=b'KERNEL32.Sleep\0'
        with self.assertRaisesRegex(parser.NativeBinaryError,'Forwarded'):
            parser.scan_native_binary(bytes(bad))

    def test_pe_getter_requires_file_backed_executable_section(self):
        raw=pe_fixture()
        for changed in ('non-executable','zero-fill-only'):
            bad=bytearray(raw)
            if changed=='non-executable':struct.pack_into('<I',bad,392+36,0x40000040)
            else:struct.pack_into('<I',bad,600,0x1800)
            with self.subTest(changed=changed),self.assertRaises(parser.NativeBinaryError):
                parser.scan_native_binary(bytes(bad))

    def test_pe_delay_and_bound_imports_are_explicitly_unsupported(self):
        for index in (11,13):
            bad=bytearray(pe_fixture());struct.pack_into('<II',bad,152+112+index*8,0x1100,40)
            with self.subTest(index=index),self.assertRaisesRegex(parser.NativeBinaryError,'unsupported'):
                parser.scan_native_binary(bytes(bad))

    def test_pe_import_name_rva_cannot_escape_image(self):
        bad=bytearray(pe_fixture());struct.pack_into('<Q',bad,1088,0xfffffff0)
        with self.assertRaisesRegex(parser.NativeBinaryError,'RVA'):
            parser.scan_native_binary(bytes(bad))

    def test_pe_virtual_sections_cannot_alias(self):
        bad=bytearray(pe_fixture());struct.pack_into('<H',bad,134,2)
        bad[432:472]=bad[392:432]
        with self.assertRaisesRegex(parser.NativeBinaryError,'Overlapping'):
            parser.scan_native_binary(bytes(bad))

    def test_pe_declared_image_size_and_file_alignment_are_enforced(self):
        raw=pe_fixture()
        for offset,value in ((152+56,4096),(152+36,513)):
            bad=bytearray(raw);struct.pack_into('<I',bad,offset,value)
            with self.subTest(offset=offset),self.assertRaises(parser.NativeBinaryError):
                parser.scan_native_binary(bytes(bad))

    def test_pe_import_descriptor_needs_bounded_terminator(self):
        bad=bytearray(pe_fixture());struct.pack_into('<II',bad,152+120,0x1100,20)
        with self.assertRaisesRegex(parser.NativeBinaryError,'terminator'):
            parser.scan_native_binary(bytes(bad))

    def test_header_only_fixtures_cannot_supply_strict_actual_facts(self):
        elf=bytearray(64);elf[:7]=b'\x7fELF\x02\x01\x01'
        struct.pack_into('<HHI',elf,16,3,62,1);struct.pack_into('<H',elf,52,64)
        pe=bytearray(512);pe[:2]=b'MZ';struct.pack_into('<I',pe,60,128);pe[128:132]=b'PE\0\0'
        struct.pack_into('<HHIIIHH',pe,132,0x8664,0,0,0,0,240,0x2022);struct.pack_into('<H',pe,152,0x20b)
        for raw in (bytes(elf),bytes(pe)):
            with self.subTest(format=raw[:4]),self.assertRaises(parser.NativeBinaryError):parser.scan_native_binary(raw)

    def test_mutable_shared_unknown_and_oversized_inputs_are_refused(self):
        raw=pe_fixture()
        for value in (bytearray(raw),memoryview(raw),b'x'*64):
            with self.assertRaises(parser.NativeBinaryError):parser.scan_native_binary(value)
        with self.assertRaises(parser.NativeBinaryError):parser.scan_native_binary(raw,maximum_bytes=len(raw)-1)
        with self.assertRaises(parser.NativeBinaryError):parser.scan_native_binary(raw,maximum_bytes=True)


if __name__=='__main__':unittest.main()
