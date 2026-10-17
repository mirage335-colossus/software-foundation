"""Fixed private CMake declarations; never imports/launches a native producer.

Original source identities and executable recipe pins come from the closed
selected-body review. Source-owned wrappers provide static target/install policy.
The caller's source projection is data, independently admitted by the controller.
"""

import copy

from _foundation_windows_supplier_factory_contract_v1 import (
    MissingInputs, factory_context, original_program, render_cmake_inputs,
    validate_factory_result,
)


HELPER_SOURCE = '977ec0c9437db00caebabcb61ac23c44698196cf9f42d50a9de983a4a32d9620'


SOURCES = {
    'zlib': {'version': '1.3.1', 'archive': 'zlib.tar.gz',
        'sha256': '9a93b2b7dfdac77ceba5a558a580e74667dd6fede4585b91eefb60f03b72df23',
        'bytes': 1512791, 'format': 'tar-gzip', 'strip_prefix': 'zlib-1.3.1'},
    'brotli': {'version': '1.1.0', 'archive': 'brotli.tar.gz',
        'sha256': 'e720a6ca29428b803f4ad165371771f5398faba397edf6778837a18599ea13ff',
        'bytes': 511969, 'format': 'tar-gzip', 'strip_prefix': 'brotli-1.1.0'},
    'png': {'version': '1.6.43', 'archive': 'libpng.tar.gz',
        'sha256': 'fecc95b46cf05e8e3fc8a414750e0ba5aad00d89e9fdf175e94ff041caf1a03a',
        'bytes': 1554715, 'format': 'tar-gzip', 'strip_prefix': 'libpng-1.6.43'},
    'jpeg': {'version': '3.0.4', 'archive': 'libjpeg-turbo.tar.gz',
        'sha256': '0270f9496ad6d69e743f1e7b9e3e9398f5b4d606b6a47744df4b73df50f62e38',
        'bytes': 2400356, 'format': 'tar-gzip', 'strip_prefix': 'libjpeg-turbo-3.0.4'},
    'webp': {'version': '1.4.0', 'archive': 'libwebp.tar.gz',
        'sha256': '12af50c45530f0a292d39a88d952637e43fb2d4ab1883c44ae729840f7273381',
        'bytes': 3800514, 'format': 'tar-gzip', 'strip_prefix': 'libwebp-1.4.0'},
}

REVIEWED_RECIPES = {
    'zlib': {
        'CMakeLists.txt': ('ab5f3afca6fe38983dc30a28da4877706e3a690a564eda3d4929fff39dab190e', 7649),
        'zlib.pc.cmakein': ('2f1d0b18ce37c2af415a469857f02aee2c41a58877aff21d29e9c6db32b55cb7', 294),
        'zconf.h.cmakein': ('350fb02462487a3e8612c18ad279053996ce0c85ebfece25a959baea9db86562', 16551),
    },
    'brotli': {
        'CMakeLists.txt': ('4b80f1d96bf334c81b20b52a261c18a48f10adb891afa28c6878392b459bb117', 12897),
    },
    'png': {
        'CMakeLists.txt': ('c3e20995b6cc3699bdb01ce38d13f5abd89b6fffc879d09c967dce37eb3345f6', 45132),
        'scripts/cmake/genchk.cmake.in': ('28b6dce0d2641aae9f8cecd739ed0ac05c13b68f32064a8acd61a2e315623e92', 1609),
        'scripts/cmake/genout.cmake.in': ('bb96a6d1310709aa892237ecb73ff703a3ec1aec4dd07144b6723d4ce0fd420f', 3388),
        'scripts/cmake/gensrc.cmake.in': ('37a84346239b50e2f9c9d53f8fd2cd10f4678327d74d68b31275c4a3bf8fb9d2', 5246),
        'scripts/pnglibconf.h.prebuilt': ('b5b0821371a9eccc464b6d4ee3df5a35d71ce80d97b7dcf99b5adb72e8d7deba', 7814),
    },
    'webp': {
        'CMakeLists.txt': ('0b6961ba54877488cce9f1080cc431ef5d175a6e4b89f96d9fa66e3037e1b686', 32240),
        'cmake/WebPConfig.cmake.in': ('4c226280ad286c14be68454cac754c81a269a4bd158396c348fa08ba05fa985e', 528),
        'cmake/config.h.in': ('c94bf6daa34581e6e69e1cf5304346969014500b941e2770868ce9c025ef97d0', 3337),
        'cmake/cpu.cmake': ('09dddb83cff48231c384d46e8a75cfe97141b2138e37028cd4272b5a6ce0316b', 6331),
        'cmake/deps.cmake': ('d9e2596a91f758854c0e19ecb63a9d6128126ea79b3a7048b39e71fb3fdb8f03', 5169),
    },
}

STATIC_TARGETS = {
    'zlib': ('zlibstatic',), 'brotli': ('brotlicommon', 'brotlidec'),
    'png': ('png_static',), 'webp': ('sharpyuv', 'webp', 'webpdemux'),
}
LIBRARIES = {
    'zlib': {'ZLIB::ZLIB': 'lib/zlibstatic.lib'},
    'brotli': {'Brotli::common': 'lib/brotlicommon.lib', 'Brotli::dec': 'lib/brotlidec.lib'},
    'png': {'PNG::PNG': 'lib/libpng16_static.lib'},
    'webp': {'WebP::sharpyuv': 'lib/libsharpyuv.lib',
             'WebP::libwebp': 'lib/libwebp.lib', 'WebP::demux': 'lib/libwebpdemux.lib'},
}


def _literal(value):
    if type(value) is not str or not value or not value.isascii() or any(
            char in value for char in ('\x00', '\r', '\n')) or ']==]' in value:
        raise ValueError('A rendered CMake path must be an exact ASCII literal')
    return '[==[' + value + ']==]'


def _cache(supplier, prefix):
    options = {
        'zlib': [('ZLIB_BUILD_EXAMPLES', 'OFF')],
        'brotli': [('BUILD_SHARED_LIBS', 'OFF'), ('BROTLI_DISABLE_TESTS', 'ON'),
                   ('BROTLI_BUNDLED_MODE', 'ON')],
        'png': [('PNG_SHARED', 'OFF'), ('PNG_STATIC', 'ON'), ('PNG_TESTS', 'OFF'),
                ('PNG_TOOLS', 'OFF'), ('PNG_FRAMEWORK', 'OFF'), ('PNG_BUILD_ZLIB', 'ON'),
                ('PNG_HARDWARE_OPTIMIZATIONS', 'ON')],
        'webp': [('BUILD_SHARED_LIBS', 'OFF'), ('WEBP_LINK_STATIC', 'ON'),
                 ('WEBP_ENABLE_SIMD', 'ON'), ('WEBP_USE_THREAD', 'OFF'),
                 ('HAVE_WINCODEC_H', 'OFF'),
                 ('WEBP_BUILD_ANIM_UTILS', 'OFF'), ('WEBP_BUILD_CWEBP', 'OFF'),
                 ('WEBP_BUILD_DWEBP', 'OFF'), ('WEBP_BUILD_GIF2WEBP', 'OFF'),
                 ('WEBP_BUILD_IMG2WEBP', 'OFF'), ('WEBP_BUILD_VWEBP', 'OFF'),
                 ('WEBP_BUILD_WEBPINFO', 'OFF'), ('WEBP_BUILD_LIBWEBPMUX', 'OFF'),
                 ('WEBP_BUILD_WEBPMUX', 'OFF'), ('WEBP_BUILD_EXTRAS', 'OFF'),
                 ('WEBP_BUILD_WEBP_JS', 'OFF'), ('CMAKE_DISABLE_FIND_PACKAGE_OpenGL', 'ON')],
    }[supplier]
    text = ('# Source-owned static Windows configuration.\n'
        'set(CMAKE_POLICY_DEFAULT_CMP0091 NEW CACHE STRING "" FORCE)\n'
        'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded CACHE STRING "" FORCE)\n'
        'set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)\n'
        'set(CMAKE_INSTALL_PREFIX ' + _literal(prefix) + ' CACHE PATH "" FORCE)\n'
        'set(CMAKE_INSTALL_LIBDIR lib CACHE PATH "" FORCE)\n'
        'set(CMAKE_INSTALL_INCLUDEDIR include CACHE PATH "" FORCE)\n'
        'set(CMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH OFF CACHE BOOL "" FORCE)\n'
        'set(CMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH OFF CACHE BOOL "" FORCE)\n'
        'set(CMAKE_FIND_USE_PACKAGE_REGISTRY OFF CACHE BOOL "" FORCE)\n'
        'set(CMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY OFF CACHE BOOL "" FORCE)\n'
        'set(CMAKE_FIND_USE_CMAKE_SYSTEM_PATH OFF CACHE BOOL "" FORCE)\n'
        'set(CMAKE_FIND_USE_INSTALL_PREFIX OFF CACHE BOOL "" FORCE)\n')
    for name, value in options:
        text += 'set(' + name + ' ' + value + ' CACHE BOOL "" FORCE)\n'
    if supplier == 'png':
        text += ('# A defined false literal suppresses a fresh find_program search.\n'
                 'set(AWK OFF CACHE FILEPATH "" FORCE)\n'
                 'set(PNG_PREFIX "" CACHE STRING "" FORCE)\n'
                 'set(DFA_XTRA "" CACHE FILEPATH "" FORCE)\n'
                 'set(ZLIB_ROOT "" CACHE PATH "" FORCE)\n')
    return text


def _project(supplier, context):
    prefix = context['prefix_root']
    text = ('cmake_minimum_required(VERSION 3.15)\n'
        'cmake_policy(SET CMP0091 NEW)\n')
    text += _cache(supplier, prefix)
    compiler = original_program(context, 'compiler')['declaration']['path']
    text += ('set(CMAKE_ASM_COMPILER ' + _literal(compiler) + ' CACHE FILEPATH "" FORCE)\n'
        'project(FoundationReviewedSupplier C)\n'
        'if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)\n'
        '  message(FATAL_ERROR "This fixed route requires native x64 MSVC")\n'
        'endif()\n'
        'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)\n'
        'set(_original ' + _literal(context['source_root']) + ')\n'
        'set(_source "${CMAKE_CURRENT_BINARY_DIR}/upstream-source")\n'
        '# Copy data into this owned binary tree; zlib may rename its zconf.h.\n'
        'file(MAKE_DIRECTORY "${_source}")\n'
        'file(COPY "${_original}/" DESTINATION "${_source}")\n')
    if supplier == 'png':
        text += ('# Use the same Workspace\'s preceding static zlib installation.\n'
            'add_library(ZLIB::ZLIB STATIC IMPORTED GLOBAL)\n'
            'set_target_properties(ZLIB::ZLIB PROPERTIES\n'
            '  IMPORTED_LOCATION ' + _literal(prefix + '/lib/zlibstatic.lib') + '\n'
            '  INTERFACE_INCLUDE_DIRECTORIES ' + _literal(prefix + '/include') + ')\n')
    text += ('# EXCLUDE_FROM_ALL also excludes upstream install rules from this parent.\n'
        'add_subdirectory("${_source}" "${CMAKE_CURRENT_BINARY_DIR}/upstream-build" EXCLUDE_FROM_ALL)\n')
    text += ('# Assert actual selected target properties; child directory variables do not propagate.\n'
        '# Empty dependencies require native CRT math; optional thread/WIC backends are off.\n'
        'function(_foundation_static_links target expected)\n'
        '  get_target_property(_kind "${target}" TYPE)\n'
        '  if(NOT "${_kind}" STREQUAL "STATIC_LIBRARY")\n'
        '    message(FATAL_ERROR "Selected supplier target is not a static library: ${target}")\n'
        '  endif()\n'
        '  foreach(_property LINK_LIBRARIES INTERFACE_LINK_LIBRARIES)\n'
        '    get_target_property(_links "${target}" "${_property}")\n'
        '    if("${_links}" STREQUAL "_links-NOTFOUND")\n'
        '      set(_links "")\n'
        '    endif()\n'
        '    if(NOT "${_links}" STREQUAL "${expected}")\n'
        '      message(FATAL_ERROR "Fixed native static link graph differs for ${target}: ${_property}=${_links}")\n'
        '    endif()\n'
        '  endforeach()\n'
        'endfunction()\n')
    links = {'zlib': {'zlibstatic': ''},
        'brotli': {'brotlicommon': '', 'brotlidec': 'brotlicommon'},
        'png': {'png_static': 'ZLIB::ZLIB'},
        'webp': {'sharpyuv': '', 'webp': 'sharpyuv', 'webpdemux': 'webp'}}[supplier]
    for target, expected in links.items():
        text += '_foundation_static_links(' + target + ' "' + expected + '")\n'
    stems = {'zlib': {'zlibstatic': 'zlibstatic'},
        'brotli': {'brotlicommon': 'brotlicommon', 'brotlidec': 'brotlidec'},
        'png': {'png_static': 'libpng16_static'},
        'webp': {'sharpyuv': 'libsharpyuv', 'webp': 'libwebp', 'webpdemux': 'libwebpdemux'}}[supplier]
    for target, stem in stems.items():
        text += ('set_target_properties(' + target + ' PROPERTIES PREFIX "" OUTPUT_NAME '
            + stem + ' SUFFIX ".lib" DEBUG_POSTFIX "" MSVC_RUNTIME_LIBRARY MultiThreaded)\n')
    text += 'install(TARGETS ' + ' '.join(STATIC_TARGETS[supplier]) + ' ARCHIVE DESTINATION lib)\n'
    if supplier == 'zlib':
        text += ('install(FILES "${_source}/zlib.h"\n'
            '  "${CMAKE_CURRENT_BINARY_DIR}/upstream-build/zconf.h" DESTINATION include)\n')
    elif supplier == 'brotli':
        text += 'install(DIRECTORY "${_source}/c/include/brotli" DESTINATION include FILES_MATCHING PATTERN "*.h")\n'
    elif supplier == 'png':
        text += ('install(FILES "${_source}/png.h" "${_source}/pngconf.h"\n'
            '  "${CMAKE_CURRENT_BINARY_DIR}/upstream-build/pnglibconf.h" DESTINATION include)\n')
    else:
        text += ('install(FILES "${_source}/src/webp/decode.h" "${_source}/src/webp/encode.h"\n'
            '  "${_source}/src/webp/types.h" "${_source}/src/webp/demux.h"\n'
            '  "${_source}/src/webp/mux_types.h" DESTINATION include/webp)\n'
            'install(FILES "${_source}/sharpyuv/sharpyuv.h"\n'
            '  "${_source}/sharpyuv/sharpyuv_csp.h" DESTINATION include/webp/sharpyuv)\n')
    return text


def _headers(supplier, files):
    if supplier == 'zlib':
        return ['include/zconf.h', 'include/zlib.h']
    if supplier == 'png':
        return ['include/png.h', 'include/pngconf.h', 'include/pnglibconf.h']
    if supplier == 'brotli':
        headers = sorted('include/brotli/' + member[len('c/include/brotli/'):]
            for member in files if member.startswith('c/include/brotli/') and member.endswith('.h'))
        if not headers:
            raise ValueError('The admitted Brotli public-header projection is empty')
        return headers
    return ['include/webp/decode.h', 'include/webp/demux.h', 'include/webp/encode.h',
        'include/webp/mux_types.h', 'include/webp/sharpyuv/sharpyuv.h',
        'include/webp/sharpyuv/sharpyuv_csp.h', 'include/webp/types.h']


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    if supplier not in SOURCES:
        raise ValueError('Unsupported fixed CMake supplier')
    context = factory_context(supplier, identity=identity, source_layout=source_layout,
        build_root=build_root, prefix_root=prefix_root, source_recipe_bindings=source_recipe_bindings)
    if context['source_recipe_bindings']['source'] != SOURCES[supplier]:
        raise ValueError('Supplier original archive identity differs from the fixed source')
    if set(context['source_recipe_bindings']['recipes']) not in (
            set(), {'toolchain.cmake', 'initial-cache.cmake'}):
        raise ValueError('This fixed rendered route accepts no external executable recipe bindings')
    if supplier == 'jpeg':
        raise MissingInputs(('jpeg-cmake-package-info-source',
            'jpeg-md5-cmake-source', 'jpeg-cmake-build-packages-source'))
    files = context['source_layout']['files']
    for member, (pin, size) in REVIEWED_RECIPES[supplier].items():
        if files.get(member) != {'sha256': pin, 'bytes': size}:
            raise ValueError('Original reviewed recipe/input is missing or changed: ' + member)
    common = render_cmake_inputs(context)
    rendered = {row['output']: row['content'] for row in common['rendered_files']}
    rendered['recipes/' + supplier + '/CMakeLists.txt'] = _project(supplier, context)
    cache = common['references']['initial-cache.cmake']
    cmake = original_program(context, 'cmake')
    executable = cmake['declaration']['path']
    arguments = [
        ('configure', [executable, '-G', 'Ninja', '-S', context['project_root'],
            '-B', context['binary_root'], '-C', context['cache_file'],
            '-DCMAKE_TOOLCHAIN_FILE:FILEPATH=' + context['toolchain_file']]),
        ('build', [executable, '--build', context['binary_root'], '--config', 'Release', '--parallel', '1',
            '--target', *STATIC_TARGETS[supplier]]),
        ('install', [executable, '--install', context['binary_root'], '--config', 'Release']),
    ]
    commands = []
    for stage, argv in arguments:
        commands.append({'id': supplier + '-' + stage, 'supplier': supplier,
            'stage': stage, 'program': copy.deepcopy(cmake), 'argv': argv,
            'cwd': context['workspace_root'], 'environment': copy.deepcopy(context['environment']),
            'initial_cache': copy.deepcopy(cache) if stage == 'configure' else None,
            'response_files': [], 'log_policy': 'stdout-stderr-combined'})
    result = {'commands': commands,
        'registration': {'stages': [{key: command[key] for key in ('id', 'supplier', 'stage')}
            for command in commands], 'produced_tools': {}},
        'source_files': [{'member': member, **copy.deepcopy(files[member])} for member in sorted(files)],
        'rendered_files': [{'output': output, 'content': rendered[output]} for output in sorted(rendered)],
        'generated_inputs': [],
        'install_artifacts': {'libraries': copy.deepcopy(LIBRARIES[supplier]),
                              'headers': _headers(supplier, files)}}
    return validate_factory_result(context, result)
