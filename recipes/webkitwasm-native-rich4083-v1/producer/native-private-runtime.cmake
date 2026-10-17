# A source policy for one admitted GNU/Linux shared object. This does not prove
# PIC, compiler selection or runtime privacy: actual link trace/map and ELF
# inspection remain mandatory. No compiler query, search path or global flag is
# added here. The producer has already admitted ordinary files and ownership.
include_guard(GLOBAL)

function(_bib_native_runtime_pin value role)
    string(LENGTH "${value}" _length)
    if(NOT _length EQUAL 64 OR NOT "${value}" MATCHES "^[0-9a-f]+$" OR
            "${value}" STREQUAL "0000000000000000000000000000000000000000000000000000000000000000")
        message(FATAL_ERROR "Private C++ runtime requires a nonzero lowercase SHA256: ${role}")
    endif()
endfunction()

function(_bib_native_runtime_file path role)
    # These paths also enter a GNU driver/linker argument. No list expansion,
    # generator expression, linker comma separator or shell interpretation is
    # admitted. SDK input regular-file/link-count checks belong to the producer.
    if(NOT IS_ABSOLUTE "${path}" OR NOT "${path}" MATCHES "^/[A-Za-z0-9_./+-]+$" OR
            NOT EXISTS "${path}" OR IS_DIRECTORY "${path}" OR IS_SYMLINK "${path}")
        message(FATAL_ERROR "Private C++ runtime requires an admitted ordinary absolute file: ${role}")
    endif()
    set(_path "${path}")
    cmake_path(NORMAL_PATH _path OUTPUT_VARIABLE _normal)
    file(REAL_PATH "${path}" _real)
    if(NOT "${path}" STREQUAL "${_normal}" OR NOT "${path}" STREQUAL "${_real}")
        message(FATAL_ERROR "Private C++ runtime refuses non-normal or symlinked paths: ${role}")
    endif()
endfunction()

function(bib_apply_private_cpp_runtime target)
    if(NOT TARGET "${target}")
        message(FATAL_ERROR "Private C++ runtime requires an existing shared-object owner")
    endif()
    get_target_property(_alias "${target}" ALIASED_TARGET)
    get_target_property(_imported "${target}" IMPORTED)
    get_target_property(_type "${target}" TYPE)
    get_target_property(_applied "${target}" BIB_NATIVE_PRIVATE_CPP_RUNTIME_POLICY)
    if(_alias OR _imported OR NOT _type STREQUAL "SHARED_LIBRARY" OR _applied)
        message(FATAL_ERROR "Private C++ runtime requires one non-imported, non-alias SHARED owner")
    endif()
    if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR NOT CMAKE_SYSTEM_PROCESSOR STREQUAL "x86_64" OR
            NOT CMAKE_SIZEOF_VOID_P EQUAL 8 OR NOT CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        message(FATAL_ERROR "Private C++ runtime is limited to GNU/Linux x86_64 ELF64 shared objects")
    endif()
    if(NOT DEFINED BIB_NATIVE_RUNTIME_COMPILER_TRIPLE OR
            NOT BIB_NATIVE_RUNTIME_COMPILER_TRIPLE STREQUAL "x86_64-buildroot-linux-gnu")
        message(FATAL_ERROR "Private C++ runtime requires the admitted x86_64-buildroot-linux-gnu triple")
    endif()
    if(DEFINED CMAKE_CXX_COMPILER_TARGET AND NOT CMAKE_CXX_COMPILER_TARGET STREQUAL "" AND
            NOT CMAKE_CXX_COMPILER_TARGET STREQUAL BIB_NATIVE_RUNTIME_COMPILER_TRIPLE)
        message(FATAL_ERROR "Private C++ runtime compiler target differs from the original SDK")
    endif()

    foreach(_name IN ITEMS POLICY_SHA256 SELECTION_SHA256 SELECTION_PATH LINK_MAP)
        if(NOT DEFINED BIB_NATIVE_RUNTIME_${_name} OR BIB_NATIVE_RUNTIME_${_name} STREQUAL "")
            message(FATAL_ERROR "Missing explicit private C++ runtime input: ${_name}")
        endif()
    endforeach()
    _bib_native_runtime_pin("${BIB_NATIVE_RUNTIME_POLICY_SHA256}" "policy")
    _bib_native_runtime_pin("${BIB_NATIVE_RUNTIME_SELECTION_SHA256}" "selection")
    set(_policy "${CMAKE_CURRENT_FUNCTION_LIST_DIR}/private-cpp-runtime-policy-v1.json")
    _bib_native_runtime_file("${_policy}" "fixed policy")
    _bib_native_runtime_file("${BIB_NATIVE_RUNTIME_SELECTION_PATH}" "original selection")
    file(SHA256 "${_policy}" _policy_sha)
    file(SHA256 "${BIB_NATIVE_RUNTIME_SELECTION_PATH}" _selection_sha)
    if(NOT _policy_sha STREQUAL BIB_NATIVE_RUNTIME_POLICY_SHA256 OR
            NOT _selection_sha STREQUAL BIB_NATIVE_RUNTIME_SELECTION_SHA256)
        message(FATAL_ERROR "Private C++ runtime policy/selection bytes differ from their independent pins")
    endif()

    set(_expected_LIBSTDCXX "8deac041936d2916dfd538457347fa2299ef6b37e242182b62104d34850b28a0")
    set(_expected_LIBGCC "caa681527d53fa4b78d6aa767f5c566bb2a06f28dbbca6401e8764b8eb57e85b")
    set(_expected_LIBGCC_EH "e9d5eda0cca41430e0215f8c9b110bbea8f5add09a3db10596188d407044cca6")
    set(_expected_CRTBEGINS "9e7965279f33ed90e46c48a440e3632bdcc6efa5a3ee7e62f7c6875c71bb9428")
    set(_expected_CRTENDS "c6357d4963582a97541ebf045cac7d47906977adb8803ae4c167217ad9c42a48")
    set(_basename_LIBSTDCXX "libstdc++.a")
    set(_basename_LIBGCC "libgcc.a")
    set(_basename_LIBGCC_EH "libgcc_eh.a")
    set(_basename_CRTBEGINS "crtbeginS.o")
    set(_basename_CRTENDS "crtendS.o")
    set(_files)
    foreach(_role IN ITEMS LIBSTDCXX LIBGCC LIBGCC_EH CRTBEGINS CRTENDS)
        if(NOT DEFINED BIB_NATIVE_RUNTIME_${_role}_PATH OR NOT DEFINED BIB_NATIVE_RUNTIME_${_role}_SHA256)
            message(FATAL_ERROR "Missing exact private C++ runtime role: ${_role}")
        endif()
        set(_path "${BIB_NATIVE_RUNTIME_${_role}_PATH}")
        set(_pin "${BIB_NATIVE_RUNTIME_${_role}_SHA256}")
        _bib_native_runtime_pin("${_pin}" "${_role}")
        if(NOT _pin STREQUAL _expected_${_role})
            message(FATAL_ERROR "Private C++ runtime role is outside the original SDK hash cohort: ${_role}")
        endif()
        _bib_native_runtime_file("${_path}" "${_role}")
        cmake_path(GET _path FILENAME _basename)
        if(NOT _basename STREQUAL _basename_${_role})
            message(FATAL_ERROR "Private C++ runtime role has an unexpected basename: ${_role}")
        endif()
        file(SHA256 "${_path}" _actual)
        if(NOT _actual STREQUAL _pin)
            message(FATAL_ERROR "Private C++ runtime archive/startup bytes changed: ${_role}")
        endif()
        list(APPEND _files "${_path}")
    endforeach()

    set(_gcc_path "${BIB_NATIVE_RUNTIME_LIBGCC_PATH}")
    cmake_path(GET _gcc_path PARENT_PATH _support)
    if(NOT _support MATCHES "^(.+)/(lib|lib64)/gcc/x86_64-buildroot-linux-gnu/15[.]3[.]0$")
        message(FATAL_ERROR "Private C++ runtime requires the original GCC15.3.0 support directory")
    endif()
    set(_sdk_root "${CMAKE_MATCH_1}")
    foreach(_role IN ITEMS LIBGCC_EH CRTBEGINS CRTENDS)
        if(NOT "${BIB_NATIVE_RUNTIME_${_role}_PATH}" STREQUAL "${_support}/${_basename_${_role}}")
            message(FATAL_ERROR "Private C++ runtime GCC/startup files must share one selected support directory")
        endif()
    endforeach()
    set(_libstdcxx_candidates "${_sdk_root}/x86_64-buildroot-linux-gnu/lib64/libstdc++.a"
        "${_sdk_root}/x86_64-buildroot-linux-gnu/sysroot/usr/lib/libstdc++.a"
        "${_sdk_root}/x86_64-buildroot-linux-gnu/sysroot/usr/lib64/libstdc++.a")
    if(NOT BIB_NATIVE_RUNTIME_LIBSTDCXX_PATH IN_LIST _libstdcxx_candidates)
        message(FATAL_ERROR "Private C++ runtime C++ archive is outside the same original SDK cohort")
    endif()

    set(_map "${BIB_NATIVE_RUNTIME_LINK_MAP}")
    if(NOT IS_ABSOLUTE "${_map}" OR NOT "${_map}" MATCHES "^/[A-Za-z0-9_./+-]+$" OR
            EXISTS "${_map}" OR IS_SYMLINK "${_map}")
        message(FATAL_ERROR "Private C++ runtime link map requires a fresh literal absolute destination")
    endif()
    cmake_path(NORMAL_PATH _map OUTPUT_VARIABLE _normal)
    cmake_path(GET _map PARENT_PATH _parent)
    if(NOT _map STREQUAL _normal OR NOT IS_DIRECTORY "${_parent}")
        message(FATAL_ERROR "Private C++ runtime link-map parent must already exist")
    endif()
    file(REAL_PATH "${CMAKE_BINARY_DIR}" _build_root)
    file(REAL_PATH "${_parent}" _real_parent)
    cmake_path(IS_PREFIX _build_root "${_parent}" NORMALIZE _inside)
    if(NOT _parent STREQUAL _real_parent OR NOT _inside)
        message(FATAL_ERROR "Private C++ runtime link map escapes the owned CMake binary root")
    endif()

    # Do not add archive names, whole-archive groups, global search paths or a
    # second runtime implementation. The exact driver-selected files must be
    # proved by the actual retained --trace/map and post-link ELF inspection.
    target_link_options("${target}" PRIVATE -static-libstdc++ -static-libgcc
        "LINKER:--exclude-libs,ALL" "LINKER:-z,defs" "LINKER:-z,text"
        "LINKER:-Map,${_map}" "LINKER:--trace")
    set_property(TARGET "${target}" APPEND PROPERTY LINK_DEPENDS
        ${_files} "${_policy}" "${BIB_NATIVE_RUNTIME_SELECTION_PATH}"
        "${CMAKE_CURRENT_FUNCTION_LIST_FILE}")
    set_target_properties("${target}" PROPERTIES
        LINKER_LANGUAGE CXX
        BIB_NATIVE_PRIVATE_CPP_RUNTIME_POLICY "private-static-gcc-sdk-v1"
        BIB_NATIVE_PRIVATE_CPP_RUNTIME_POLICY_SHA256 "${_policy_sha}"
        BIB_NATIVE_PRIVATE_CPP_RUNTIME_SELECTION_SHA256 "${_selection_sha}"
        BIB_NATIVE_PRIVATE_CPP_RUNTIME_LINK_MAP "${_map}")
endfunction()
