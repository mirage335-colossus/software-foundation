"""Fixed, source-owned ICU static dependency graph.

This module declares commands only. Original H tools and admitted original files
are supplied by the controller; this source never opens supplier input bodies.
"""
import hashlib
import json
from pathlib import Path

import _foundation_windows_supplier_factory_contract_v1 as contract


_MANIFEST_SHA256 = "abd737be62f3a7e3f9999cefa6edf3afc3a1777ff78d7553ad51421af9cd8bbd"
_EMITTER_SHA256 = "8e0eed8476021071bb37a6762a87a6d3f2f40227c9ef24f5af96f3075eaaa978"
_UTYPES_SHA256 = "71796ca8be8e420323a2f2a230e070dca842d75818a374d545406a62a65f9b9c"
_SOURCE_PREFIX = "source/"
_DATA_MEMBER = _SOURCE_PREFIX + "data/in/icudt77l.dat"
PRODUCED_RUNTIME_FACTS = {}  # This direct graph produces no executable tools.
CONSUMER_FACTS = {
    "ICU::data": {"includes": ["include"], "definitions": ["U_STATIC_IMPLEMENTATION"], "links": []},
    "ICU::uc": {"includes": ["include"], "definitions": ["U_STATIC_IMPLEMENTATION"], "links": ["ICU::data"]},
    "ICU::i18n": {"includes": ["include"], "definitions": ["U_STATIC_IMPLEMENTATION"], "links": ["ICU::uc"]},
}


def _manifest():
    raw = Path(__file__).with_name("source-manifest.json").read_bytes()
    if len(raw) != 19715 or hashlib.sha256(raw).hexdigest() != _MANIFEST_SHA256:
        raise ValueError("Fixed ICU source manifest changed")
    result = json.loads(raw)
    if result.get("schema_version") != 1:
        raise ValueError("Fixed ICU source manifest schema changed")
    for group, expected in (("common", 201), ("i18n", 254)):
        names = result["source_groups"][group]
        if (len(names) != expected or len(set(names)) != expected
                or any(not name.endswith(".cpp") or "/" in name or "\\" in name for name in names)):
            raise ValueError("Literal finite ICU translation units required")
    return result


def _quote(value):
    if (type(value) is not str or not value or not value.isascii()
            or any(char in value for char in '$;"\\\r\n')):
        raise ValueError("Exact literal CMake path required")
    return '"' + value + '"'


def _source_selection(context, manifest):
    layout = context["source_layout"]["files"]
    required = {_DATA_MEMBER}
    if layout.get(_SOURCE_PREFIX + "common/unicode/utypes.h", {}).get("sha256") != _UTYPES_SHA256:
        raise ValueError("Reviewed ICU static/data-entry public interface changed")
    for group in ("common", "i18n"):
        directory = _SOURCE_PREFIX + group + "/"
        required.update(directory + name for name in manifest["source_groups"][group])
        evidence = manifest["evidence"][group]
        archive_member = evidence["original_member"]
        if not archive_member.startswith("icu/"):
            raise ValueError("Fixed original ICU archive prefix required")
        member = archive_member[len("icu/"):]
        if layout.get(member, {}).get("sha256") != evidence["body_sha256"]:
            raise ValueError("Original ICU project manifest differs from fixed source selection")
        required.add(member)
        # Ordinary compiler/header inputs are Data, not executable-source audits.
        required.update(name for name in layout if name.startswith(directory)
            and name.endswith((".h", ".inc", ".inl", ".ipp")))
    if not required.issubset(layout):
        raise ValueError("Original ICU projection lacks a selected compile/data input")
    headers = {}
    for group in ("common", "i18n"):
        prefix = _SOURCE_PREFIX + group + "/unicode/"
        for member in sorted(layout):
            if member.startswith(prefix) and member.endswith(".h"):
                destination = "include/unicode/" + member[len(prefix):]
                key = destination.casefold()
                if key in headers:
                    raise ValueError("ICU public header destinations alias")
                headers[key] = (destination, member)
                required.add(member)
    if not headers:
        raise ValueError("Fixed ICU public header set is empty")
    selected = [{"member": name, "sha256": layout[name]["sha256"], "bytes": layout[name]["bytes"]}
        for name in sorted(required)]
    return selected, sorted(value[0] for value in headers.values())


def _cmake_project(context, manifest):
    root = context["source_root"] + "/source"
    project = [
        "cmake_minimum_required(VERSION 3.24)",
        "cmake_policy(SET CMP0091 NEW)",
        "project(FoundationFixedICU LANGUAGES C CXX)",
        'if(NOT WIN32 OR NOT CMAKE_SIZEOF_VOID_P EQUAL 8)',
        '  message(FATAL_ERROR "Fixed ICU graph requires Windows x86_64")',
        "endif()",
        'if(NOT CMAKE_CXX_COMPILER_ID STREQUAL "Clang" OR NOT CMAKE_CXX_SIMULATE_ID STREQUAL "MSVC")',
        '  message(FATAL_ERROR "Fixed ICU graph requires the admitted clang-cl frontend")',
        "endif()",
        "set(CMAKE_C_STANDARD 11)",
        "set(CMAKE_C_STANDARD_REQUIRED ON)",
        "set(CMAKE_CXX_STANDARD 17)",
        "set(CMAKE_CXX_STANDARD_REQUIRED ON)",
        "set(CMAKE_CXX_EXTENSIONS ON)",
        "set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)",
        "set(CMAKE_INTERPROCEDURAL_OPTIMIZATION OFF)",
        'if(NOT DEFINED ICU_DATA_SOURCE OR NOT EXISTS "${ICU_DATA_SOURCE}")',
        '  message(FATAL_ERROR "Earlier fixed data-render stage output required")',
        "endif()",
        'add_library(icu_data STATIC "${ICU_DATA_SOURCE}")',
    ]
    for group, target in (("common", "icu_uc"), ("i18n", "icu_i18n")):
        project.append("add_library(" + target + " STATIC")
        project.extend("  " + _quote(root + "/" + group + "/" + name)
            for name in manifest["source_groups"][group])
        project.append(")")
    project.extend([
        "set_target_properties(icu_data PROPERTIES OUTPUT_NAME icudata)",
        "set_target_properties(icu_uc PROPERTIES OUTPUT_NAME icuuc)",
        "set_target_properties(icu_i18n PROPERTIES OUTPUT_NAME icui18n)",
        "foreach(target IN ITEMS icu_data icu_uc icu_i18n)",
        "  set_target_properties(${target} PROPERTIES INTERPROCEDURAL_OPTIMIZATION FALSE MSVC_RUNTIME_LIBRARY MultiThreaded)",
        "  target_compile_definitions(${target} PUBLIC U_STATIC_IMPLEMENTATION)",
        "  target_compile_definitions(${target} PRIVATE NDEBUG WIN32 WIN64 WINVER=0x0601 _WIN32_WINNT=0x0601 _CRT_SECURE_NO_DEPRECATE)",
        "  target_compile_options(${target} PRIVATE /utf-8 $<$<COMPILE_LANGUAGE:CXX>:/Zc:wchar_t>)",
        "endforeach()",
        "target_compile_definitions(icu_uc PRIVATE U_COMMON_IMPLEMENTATION U_ATTRIBUTE_DEPRECATED= U_PLATFORM_USES_ONLY_WIN32_API=1 _HAS_EXCEPTIONS=0)",
        "target_compile_definitions(icu_i18n PRIVATE U_I18N_IMPLEMENTATION U_ATTRIBUTE_DEPRECATED= _HAS_EXCEPTIONS=0)",
        "target_include_directories(icu_data PRIVATE " + _quote(root + "/common") + ")",
        "target_include_directories(icu_uc PRIVATE " + _quote(root + "/common") + ")",
        "target_include_directories(icu_i18n PRIVATE " + _quote(root + "/i18n") + " " + _quote(root + "/common") + ")",
        "target_link_libraries(icu_uc PUBLIC icu_data)",
        "target_link_libraries(icu_i18n PUBLIC icu_uc)",
        # Upstream reldatefmt.cpp explicitly permits extensions; this fixed
        # target policy permits them for every source, including that item.
        "install(TARGETS icu_data icu_uc icu_i18n ARCHIVE DESTINATION lib)",
        "install(DIRECTORY " + _quote(root + "/common/unicode/") + " " + _quote(root + "/i18n/unicode/") + " DESTINATION include/unicode FILES_MATCHING PATTERN \"*.h\")",
    ])
    return "\n".join(project) + "\n"


def _data_renderer(context):
    row = context["source_layout"]["files"][_DATA_MEMBER]
    if type(row["bytes"]) is not int or not 1 <= row["bytes"] <= 53673984:
        raise ValueError("Finite packed ICU original Data required")
    raw = Path(__file__).with_name("data-emitter.py.in").read_bytes()
    if len(raw) > 65536 or hashlib.sha256(raw).hexdigest() != _EMITTER_SHA256:
        raise ValueError("Fixed maintained ICU data renderer changed")
    content = raw.decode("ascii")
    replacements = {
        "@INPUT_PATH@": json.dumps(context["source_root"] + "/" + _DATA_MEMBER),
        "@OUTPUT_PATH@": json.dumps(context["workspace_root"] + "/build/icu-data/icudata.c"),
        "@INPUT_BYTES@": str(row["bytes"]),
        "@INPUT_SHA256@": json.dumps(row["sha256"]),
    }
    for token, value in replacements.items():
        if content.count(token) != 1:
            raise ValueError("Fixed ICU renderer placeholder changed")
        content = content.replace(token, value)
    if "@INPUT_" in content or "@OUTPUT_" in content:
        raise ValueError("Unresolved fixed ICU renderer placeholder")
    return content


def _command(context, identifier, stage, role, arguments, initial_cache=None):
    program = contract.original_program(context, role)
    return {"id": identifier, "supplier": "icu", "stage": stage,
        "program": program, "argv": [program["declaration"]["path"], *arguments],
        "cwd": context["workspace_root"], "environment": dict(context["environment"]),
        "initial_cache": initial_cache, "response_files": [],
        "log_policy": "stdout-stderr-combined"}


def reviewed_supplier_commands(supplier, *, identity, source_layout, build_root,
                               prefix_root, source_recipe_bindings):
    if supplier != "icu":
        raise ValueError("Fixed ICU supplier required")
    context = contract.factory_context(supplier, identity=identity,
        source_layout=source_layout, build_root=build_root, prefix_root=prefix_root,
        source_recipe_bindings=source_recipe_bindings)
    manifest = _manifest()
    selected, headers = _source_selection(context, manifest)
    renderer = _data_renderer(context)
    common = contract.render_cmake_inputs(context)
    renders = list(common["rendered_files"])
    renders.extend([
        {"output": "recipes/icu/CMakeLists.txt", "content": _cmake_project(context, manifest)},
        {"output": "recipes/icu/render-data.py", "content": renderer},
    ])
    renders.sort(key=lambda row: row["output"])
    data_output = "build/icu-data/icudata.c"
    data_path = context["workspace_root"] + "/" + data_output
    commands = [
        _command(context, "icu-render-data", "generate", "python",
            ["-I", "-S", "-B", context["project_root"] + "/render-data.py",
             context["source_root"] + "/" + _DATA_MEMBER, data_path]),
        _command(context, "icu-configure", "configure", "cmake",
            ["-S", context["project_root"], "-B", context["binary_root"], "-G", "Ninja",
             "-C", context["cache_file"], "-DCMAKE_TOOLCHAIN_FILE:FILEPATH=" + context["toolchain_file"],
             "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_INSTALL_PREFIX:PATH=" + prefix_root,
             "-DICU_DATA_SOURCE:FILEPATH=" + data_path],
            common["references"]["initial-cache.cmake"]),
        _command(context, "icu-build", "build", "cmake",
            ["--build", context["binary_root"], "--target", "icu_data", "icu_uc", "icu_i18n"]),
        _command(context, "icu-install", "install", "cmake",
            ["--install", context["binary_root"], "--prefix", prefix_root]),
    ]
    result = {"commands": commands,
        "registration": {"stages": [{key: row[key] for key in ("id", "supplier", "stage")}
            for row in commands], "produced_tools": {}},
        "source_files": selected, "rendered_files": renders,
        "generated_inputs": [{"consumer_command_id": "icu-configure",
            "producing_command_id": "icu-render-data", "output": data_output}],
        "install_artifacts": {"libraries": {"ICU::data": "lib/icudata.lib",
            "ICU::i18n": "lib/icui18n.lib", "ICU::uc": "lib/icuuc.lib"}, "headers": headers}}
    return contract.validate_factory_result(context, result)
