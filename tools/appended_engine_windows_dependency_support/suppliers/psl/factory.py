"""Fixed libpsl 0.21.5 Windows static recipe; pure declarations, no execution.

The owned project bypasses the upstream NMake orchestration.  Its two literal
translation units, configuration, DAFSA command and compile definitions follow
the independently reviewed msvc files and src/libpsl-srcs.mk.  Original source
bytes and original Python/LLVM/CMake/Ninja runtimes are admitted by the caller.
"""
import copy

import _foundation_windows_supplier_factory_contract_v1 as contract


CONSUMER_FACTS = {
    'LibPSL::LibPSL': {
        'includes': ['include'],
        'definitions': ['PSL_STATIC'],
        'links': ['ICU::uc', 'ws2_32'],
    },
}

# These are executable/configuration Source decisions, not a body audit of the
# ordinary compiler input closure.  Every selected row also joins the actual
# original source projection in the shared contract.
_REVIEWED = {
    'msvc/config.h.win32': (4698, 'a9370c3ddddab11b617cf05580d1fbf508d5a43cef716b52f2f8b88df748f4d2'),
    'src/libpsl-srcs.mk': (48, '6aef57c68bd3921795a4483946fbb60b5f7a7af300b681379143acfd5eb2b4a2'),
    'src/psl-make-dafsa': (22739, '252e22a3ad8e48542a71ae5625b3c2ca7e9b90ce5edbab68ecf4d0ccec82c604'),
}
_DATA = ('include/libpsl.h', 'list/public_suffix_list.dat',
    'src/lookup_string_in_fixed_set.c', 'src/psl.c')


def _sources(context):
    files = context['source_layout']['files']
    names = sorted([*_REVIEWED, *_DATA])
    missing = [name for name in names if name not in files]
    if missing:
        raise contract.MissingInputs(['windows-psl-retained-source-files'])
    for member, (size, pin) in _REVIEWED.items():
        if files[member] != {'bytes': size, 'sha256': pin}:
            raise ValueError('Reviewed libpsl Source differs: ' + member)
    return [{'member': member, **copy.deepcopy(files[member])} for member in names]


def _cmake_path(value):
    # No CMake list, variable, quote or escape syntax may be injected by a path.
    if type(value) is not str or any(char in value for char in '$;"\\\r\n'):
        raise ValueError('Literal fixed CMake path required')
    return value


def _project(context):
    source = _cmake_path(context['source_root'])
    prefix = _cmake_path(context['prefix_root'])
    # ICU release-77-1 utypes.h:321-328 (71796ca8be8e420323a2f2a230e070dca
    # 842d75818a374d545406a62a65f9b9c) grounds this static consumer constant.
    return '''cmake_minimum_required(VERSION 3.24)
project(foundation_owned_psl LANGUAGES C)
if(NOT WIN32 OR NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "The fixed PSL recipe requires Windows AMD64 MSVC ABI")
endif()
if(NOT CMAKE_BUILD_TYPE STREQUAL "Release")
  message(FATAL_ERROR "The fixed PSL recipe requires Release")
endif()
if(NOT DEFINED FOUNDATION_PSL_DAFSA OR NOT IS_ABSOLUTE "${FOUNDATION_PSL_DAFSA}")
  message(FATAL_ERROR "The separately produced DAFSA input is required")
endif()
set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)
configure_file("''' + source + '''/msvc/config.h.win32"
  "${CMAKE_CURRENT_BINARY_DIR}/config.h" COPYONLY)
configure_file("${FOUNDATION_PSL_DAFSA}"
  "${CMAKE_CURRENT_BINARY_DIR}/suffixes_dafsa.h" COPYONLY)
add_library(foundation_psl STATIC
  "''' + source + '''/src/psl.c"
  "''' + source + '''/src/lookup_string_in_fixed_set.c")
set_target_properties(foundation_psl PROPERTIES
  OUTPUT_NAME psl PREFIX "" SUFFIX ".lib"
  MSVC_RUNTIME_LIBRARY MultiThreaded INTERPROCEDURAL_OPTIMIZATION FALSE)
target_compile_definitions(foundation_psl PRIVATE
  HAVE_CONFIG_H BUILDING_PSL PSL_STATIC WITH_LIBICU=1 ENABLE_BUILTIN=1
  _CRT_SECURE_NO_WARNINGS _CRT_NONSTDC_NO_WARNINGS
  "ssize_t=signed __int64" U_STATIC_IMPLEMENTATION)
target_include_directories(foundation_psl PRIVATE
  "${CMAKE_CURRENT_BINARY_DIR}" "''' + source + '''/include"
  "''' + source + '''" "''' + prefix + '''/include")
install(TARGETS foundation_psl ARCHIVE DESTINATION lib)
install(FILES "''' + source + '''/include/libpsl.h" DESTINATION include)
'''


def _command(context, identifier, stage, role, arguments, initial_cache=None):
    program = contract.original_program(context, role)
    return {'id': identifier, 'supplier': 'psl', 'stage': stage, 'program': program,
        'argv': [program['declaration']['path'], *arguments],
        'cwd': context['binary_root'], 'environment': copy.deepcopy(context['environment']),
        'initial_cache': copy.deepcopy(initial_cache), 'response_files': [],
        'log_policy': 'stdout-stderr-combined'}


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    if supplier != 'psl':
        raise ValueError('The fixed PSL factory cannot select another supplier')
    context = contract.factory_context(supplier, identity=identity,
        source_layout=source_layout, build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    selected = _sources(context)
    return _complete(context, selected)


def _complete(context, selected):
    common = contract.render_cmake_inputs(context)
    rendered = common['rendered_files'] + [{
        'output': 'recipes/psl/CMakeLists.txt', 'content': _project(context)}]
    rendered.sort(key=lambda row: row['output'])
    generated = context['binary_root'] + '/suffixes_dafsa.generated.h'
    cache = common['references']['initial-cache.cmake']
    commands = [
        _command(context, 'psl-generate-dafsa', 'generate', 'python', [
            '-I', '-S', '-B', context['source_root'] + '/src/psl-make-dafsa',
            '--output-format=cxx+', context['source_root'] + '/list/public_suffix_list.dat',
            generated]),
        _command(context, 'psl-configure', 'configure', 'cmake', [
            '-S', context['project_root'], '-B', context['binary_root'], '-G', 'Ninja',
            '-C', cache['path'], '-DCMAKE_TOOLCHAIN_FILE:FILEPATH=' + context['toolchain_file'],
            '-DCMAKE_BUILD_TYPE:STRING=Release',
            '-DCMAKE_INSTALL_PREFIX:PATH=' + context['prefix_root'],
            '-DFOUNDATION_PSL_DAFSA:FILEPATH=' + generated], cache),
        _command(context, 'psl-build', 'build', 'cmake', [
            '--build', context['binary_root'], '--config', 'Release', '--parallel', '1',
            '--target', 'foundation_psl']),
        _command(context, 'psl-install', 'install', 'cmake', [
            '--install', context['binary_root'], '--config', 'Release']),
    ]
    result = {'commands': commands, 'registration': {
        'stages': [{key: command[key] for key in ('id', 'supplier', 'stage')}
            for command in commands], 'produced_tools': {}},
        'source_files': selected, 'rendered_files': rendered,
        'generated_inputs': [{'consumer_command_id': 'psl-configure',
            'producing_command_id': 'psl-generate-dafsa',
            'output': 'build/psl/suffixes_dafsa.generated.h'}],
        'install_artifacts': {'libraries': {'LibPSL::LibPSL': 'lib/psl.lib'},
            'headers': ['include/libpsl.h']}}
    return contract.validate_factory_result(context, result)
