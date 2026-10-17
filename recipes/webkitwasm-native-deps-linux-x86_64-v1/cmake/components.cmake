# Complete component order is fixed in the parent CMakeLists. DEPENDS always
# includes the previous project's completed install, enforcing a global cap of
# one four-job child build, even when the outer build has more than four jobs.
set(_native_recipe "${CMAKE_CURRENT_LIST_DIR}/..")
set(_native_profile_file "${_native_recipe}/profile.json")
set(_native_previous native-assets)
set(_native_env "${PROGRAM_cmake}" -E env
  --unset=MAKEFLAGS --unset=MFLAGS --unset=DESTDIR
  --unset=CPATH --unset=C_INCLUDE_PATH --unset=CPLUS_INCLUDE_PATH
  --unset=LIBRARY_PATH --unset=LD_LIBRARY_PATH
  "PKG_CONFIG=${PROGRAM_pkg_config}"
  "PKG_CONFIG_PATH=" "PKG_CONFIG_SYSROOT_DIR="
  "PKG_CONFIG_LIBDIR=${NATIVE_PREFIX}/lib/pkgconfig"
  "CC=${PROGRAM_c}" "CXX=${PROGRAM_cxx}"
  "AR=${PROGRAM_archiver}" "RANLIB=${PROGRAM_ranlib}"
  "CFLAGS=${NATIVE_C_FLAGS}"
  "CXXFLAGS=${NATIVE_CXX_FLAGS}"
  "CPPFLAGS=-I${NATIVE_PREFIX}/include"
  "LDFLAGS=--sysroot=${NATIVE_SYSROOT} -L${NATIVE_PREFIX}/lib"
  "PYTHON=${PROGRAM_python}" "PERL=${PROGRAM_perl}"
  "GPERF=${PROGRAM_gperf}" "CONFIG_SHELL=${PROGRAM_sh}"
  "CMAKE_BUILD_PARALLEL_LEVEL=4")
set(_native_cmake_args
  "-DCMAKE_TOOLCHAIN_FILE:FILEPATH=${NATIVE_TOOLCHAIN}"
  "-DCMAKE_SYSROOT:PATH=${NATIVE_SYSROOT}"
  "-DCMAKE_C_COMPILER:FILEPATH=${PROGRAM_c}"
  "-DCMAKE_CXX_COMPILER:FILEPATH=${PROGRAM_cxx}"
  "-DCMAKE_AR:FILEPATH=${PROGRAM_archiver}"
  "-DCMAKE_RANLIB:FILEPATH=${PROGRAM_ranlib}"
  "-DCMAKE_MAKE_PROGRAM:FILEPATH=${PROGRAM_ninja}"
  "-DCMAKE_BUILD_TYPE:STRING=Release"
  "-DCMAKE_POSITION_INDEPENDENT_CODE:BOOL=ON"
  "-DCMAKE_C_FLAGS:STRING=${NATIVE_C_FLAGS}"
  "-DCMAKE_CXX_FLAGS:STRING=${NATIVE_CXX_FLAGS}"
  "-DCMAKE_EXE_LINKER_FLAGS:STRING=${NATIVE_LINK_FLAGS}"
  "-DCMAKE_SHARED_LINKER_FLAGS:STRING=${NATIVE_LINK_FLAGS}"
  "-DCMAKE_INSTALL_PREFIX:PATH=${NATIVE_PREFIX}"
  "-DCMAKE_INSTALL_LIBDIR:STRING=lib"
  "-DCMAKE_INSTALL_INCLUDEDIR:STRING=include"
  "-DBUILD_SHARED_LIBS:BOOL=OFF"
  "-DCMAKE_PREFIX_PATH:PATH=${NATIVE_PREFIX}"
  "-DCMAKE_FIND_ROOT_PATH:STRING=${NATIVE_PREFIX}|${NATIVE_SYSROOT}"
  "-DCMAKE_FIND_ROOT_PATH_MODE_PROGRAM:STRING=NEVER"
  "-DCMAKE_FIND_ROOT_PATH_MODE_LIBRARY:STRING=ONLY"
  "-DCMAKE_FIND_ROOT_PATH_MODE_INCLUDE:STRING=ONLY"
  "-DCMAKE_FIND_ROOT_PATH_MODE_PACKAGE:STRING=ONLY"
  "-DCMAKE_FIND_USE_PACKAGE_REGISTRY:BOOL=OFF"
  "-DCMAKE_FIND_USE_SYSTEM_PACKAGE_REGISTRY:BOOL=OFF"
  "-DCMAKE_FIND_USE_CMAKE_ENVIRONMENT_PATH:BOOL=OFF"
  "-DCMAKE_FIND_USE_SYSTEM_ENVIRONMENT_PATH:BOOL=OFF"
  "-DPKG_CONFIG_EXECUTABLE:FILEPATH=${PROGRAM_pkg_config}"
  "-DPKG_CONFIG_USE_CMAKE_PREFIX_PATH:BOOL=OFF"
  "-DPython3_EXECUTABLE:FILEPATH=${PROGRAM_python}"
  "-DPYTHON_EXECUTABLE:FILEPATH=${PROGRAM_python}"
  "-DPERL_EXECUTABLE:FILEPATH=${PROGRAM_perl}"
  "-DZLIB_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
  "-DZLIB_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libz.a"
  "-DZLIB_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libz.a"
  "-DZLIB_USE_STATIC_LIBS:BOOL=ON"
  "-DPNG_PNG_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
  "-DPNG_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libpng16.a"
  "-DPNG_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libpng16.a"
  "-DFREETYPE_INCLUDE_DIR_ft2build:PATH=${NATIVE_PREFIX}/include/freetype2"
  "-DFREETYPE_INCLUDE_DIR_freetype2:PATH=${NATIVE_PREFIX}/include/freetype2"
  "-DFREETYPE_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libfreetype.a"
  "-DBROTLIDEC_INCLUDE_DIRS:PATH=${NATIVE_PREFIX}/include"
  "-DBROTLIDEC_LIBRARIES:STRING=${NATIVE_PREFIX}/lib/libbrotlidec.a|${NATIVE_PREFIX}/lib/libbrotlicommon.a"
  "-DICU_ROOT:PATH=${NATIVE_PREFIX}"
  "-DICU_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
  "-DICU_DATA_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libicudata.a"
  "-DICU_UC_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libicuuc.a"
  "-DICU_I18N_LIBRARY_RELEASE:FILEPATH=${NATIVE_PREFIX}/lib/libicui18n.a")

foreach(_component IN LISTS _native_order)
  set(_source "${SOURCE_${_component}}")
  set(_binary "${NATIVE_WORK}/${_component}")
  string(JSON _system GET "${_native_profile}" components ${_component} build_system)
  string(JSON _option_count LENGTH "${_native_profile}" components ${_component} configure_options)
  set(_options)
  if(_option_count GREATER 0)
    math(EXPR _last "${_option_count} - 1")
    foreach(_index RANGE 0 ${_last})
      string(JSON _option GET "${_native_profile}" components ${_component} configure_options ${_index})
      if(_system STREQUAL "cmake")
        list(APPEND _options "-D${_option}")
      else()
        list(APPEND _options "${_option}")
      endif()
    endforeach()
  endif()
  set(_build_source "${_source}")
  if(_component STREQUAL "sqlite")
    set(_build_source "${_native_recipe}/sqlite")
    set(_options "-DSQLITE_AMALGAMATION:PATH=${_source}")
    set(_system cmake)
  endif()
  if(_system STREQUAL "cmake")
    set(_targets)
    string(JSON _target_count LENGTH "${_native_profile}" components ${_component} build_targets)
    math(EXPR _last "${_target_count} - 1")
    foreach(_index RANGE 0 ${_last})
      string(JSON _target GET "${_native_profile}" components ${_component} build_targets ${_index})
      list(APPEND _targets "${_target}")
    endforeach()
    if(_component STREQUAL "curl")
      list(APPEND _options
        "-DOPENSSL_ROOT_DIR:PATH=${NATIVE_PREFIX}"
        "-DOPENSSL_USE_STATIC_LIBS:BOOL=ON"
        "-DOPENSSL_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
        "-DOPENSSL_SSL_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libssl.a"
        "-DOPENSSL_CRYPTO_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libcrypto.a"
        "-DBROTLI_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
        "-DBROTLIDEC_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libbrotlidec.a"
        "-DBROTLICOMMON_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libbrotlicommon.a"
        "-DNGHTTP2_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
        "-DNGHTTP2_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libnghttp2.a"
        "-DLIBPSL_INCLUDE_DIR:PATH=${NATIVE_PREFIX}/include"
        "-DLIBPSL_LIBRARY:FILEPATH=${NATIVE_PREFIX}/lib/libpsl.a"
        # curl's C-language configure checks may link the selected static PSL.
        # Its ICU dependencies need the admitted C++ runtime even for those
        # checks; the final consumer closure is recorded independently.
        "-DCMAKE_C_STANDARD_LIBRARIES:STRING=${NATIVE_PREFIX}/lib/libicuuc.a ${NATIVE_PREFIX}/lib/libicudata.a -lstdc++ -pthread -ldl -lm"
        "-DCURL_CA_BUNDLE:FILEPATH=${NATIVE_PREFIX}/share/certs/ca-bundle.pem")
    elseif(_component STREQUAL "nghttp2")
      # Its root probes these even in lib-only mode. Explicitly prevent every
      # unselected application dependency instead of relying on host absence.
      foreach(_package Libev Libcares Libbrotlienc Libbrotlidec WolfSSL OpenSSL
          Libngtcp2 Libngtcp2_crypto_quictls Libngtcp2_crypto_wolfssl Libnghttp3
          Libbpf Systemd Jansson Libevent LibXml2 Jemalloc)
        list(APPEND _options "-DCMAKE_DISABLE_FIND_PACKAGE_${_package}:BOOL=ON")
      endforeach()
    endif()
    ExternalProject_Add(native-${_component}
      SOURCE_DIR "${_source}" BINARY_DIR "${_binary}"
      PREFIX "${NATIVE_WORK}/ep-${_component}"
      DOWNLOAD_COMMAND "" UPDATE_COMMAND "" PATCH_COMMAND ""
      LIST_SEPARATOR "|"
      CONFIGURE_COMMAND ${_native_env} "${PROGRAM_cmake}"
        -S "${_build_source}" -B "${_binary}" -G Ninja
        ${_native_cmake_args} ${_options}
      BUILD_COMMAND ${_native_env} "${PROGRAM_cmake}" --build "${_binary}"
        --target ${_targets} --parallel 4
      INSTALL_COMMAND "${PROGRAM_cmake}"
        "-DNATIVE_COMPONENT=${_component}" "-DNATIVE_SOURCE=${_source}"
        "-DNATIVE_BINARY=${_binary}" "-DNATIVE_PREFIX=${NATIVE_PREFIX}"
        "-DNATIVE_PROFILE=${_native_profile_file}"
        -P "${_native_recipe}/cmake/install-selected.cmake"
      DEPENDS ${_native_previous} EXCLUDE_FROM_ALL TRUE)
  else()
    set(_configure ${_native_env} "${PROGRAM_sh}" "${_source}/configure"
      "--prefix=${NATIVE_PREFIX}" "--libdir=${NATIVE_PREFIX}/lib" ${_options})
    set(_build ${_native_env} "${PROGRAM_make}" -j4 "SHELL=${PROGRAM_sh}")
    if(_component STREQUAL "icu")
      # Plain Linux respects the explicit CC/CXX variables. Linux/gcc and
      # Linux/clang would replace them with bare compiler names.
      set(_configure ${_native_env} "${PROGRAM_sh}"
        "${_source}/source/runConfigureICU" Linux
        "--prefix=${NATIVE_PREFIX}" "--libdir=${NATIVE_PREFIX}/lib" ${_options})
      list(APPEND _build all)
    elseif(_component STREQUAL "openssl")
      set(_configure ${_native_env} "${PROGRAM_perl}" "${_source}/Configure"
        ${_options} "--prefix=${NATIVE_PREFIX}"
        "--openssldir=${NATIVE_PREFIX}/etc/ssl")
      list(APPEND _build build_libs)
    elseif(_component STREQUAL "psl")
      # No upstream --disable-tools flag exists. Select only the library.
      set(_configure ${_native_env}
        "LIBICU_CFLAGS=-I${NATIVE_PREFIX}/include -DU_STATIC_IMPLEMENTATION"
        "LIBICU_LIBS=-L${NATIVE_PREFIX}/lib -licuuc -licudata -lstdc++ -pthread -ldl -lm"
        "${PROGRAM_sh}" "${_source}/configure"
        "--prefix=${NATIVE_PREFIX}" "--libdir=${NATIVE_PREFIX}/lib" ${_options})
      list(APPEND _build -C "${_binary}/src" libpsl.la)
    elseif(_component STREQUAL "fontconfig")
      set(_font_static
        "FREETYPE_LIBS=-L${NATIVE_PREFIX}/lib -lfreetype -lbrotlidec -lbrotlicommon -lpng16 -lz -lm"
        "LIBXML2_LIBS=-L${NATIVE_PREFIX}/lib -lxml2 -licui18n -licuuc -licudata -lz -lstdc++ -pthread -ldl -lm"
        "JSONC_CFLAGS=" "JSONC_LIBS=")
      set(_configure ${_native_env} ${_font_static} "${PROGRAM_sh}"
        "${_source}/configure" "--prefix=${NATIVE_PREFIX}"
        "--libdir=${NATIVE_PREFIX}/lib" ${_options}
        "--sysconfdir=${NATIVE_PREFIX}/etc"
        "--with-default-fonts=${NATIVE_PREFIX}/share/fonts"
        "--with-cache-dir=${NATIVE_PREFIX}/var/cache/fontconfig"
        "--with-baseconfigdir=${NATIVE_PREFIX}/etc/fonts"
        "--with-configdir=${NATIVE_PREFIX}/etc/fonts/conf.d"
        "--with-templatedir=${NATIVE_PREFIX}/share/fontconfig/conf.avail"
        "--with-xmldir=${NATIVE_PREFIX}/share/xml/fontconfig")
      set(_build ${_native_env} "${PROGRAM_make}" -j4 "SHELL=${PROGRAM_sh}" -C "${_binary}/fontconfig" all
        COMMAND ${_native_env} "${PROGRAM_make}" -j4 "SHELL=${PROGRAM_sh}" -C "${_binary}/fc-case" all
        COMMAND ${_native_env} "${PROGRAM_make}" -j4 "SHELL=${PROGRAM_sh}" -C "${_binary}/fc-lang" all
        COMMAND ${_native_env} "${PROGRAM_make}" -j4 "SHELL=${PROGRAM_sh}" -C "${_binary}/src" all)
    endif()
    ExternalProject_Add(native-${_component}
      SOURCE_DIR "${_source}" BINARY_DIR "${_binary}"
      PREFIX "${NATIVE_WORK}/ep-${_component}"
      DOWNLOAD_COMMAND "" UPDATE_COMMAND "" PATCH_COMMAND ""
      CONFIGURE_COMMAND ${_configure}
      BUILD_COMMAND ${_build}
      INSTALL_COMMAND "${PROGRAM_cmake}"
        "-DNATIVE_COMPONENT=${_component}" "-DNATIVE_SOURCE=${_source}"
        "-DNATIVE_BINARY=${_binary}" "-DNATIVE_PREFIX=${NATIVE_PREFIX}"
        "-DNATIVE_PROFILE=${_native_profile_file}"
        -P "${_native_recipe}/cmake/install-selected.cmake"
      DEPENDS ${_native_previous} EXCLUDE_FROM_ALL TRUE)
  endif()
  set(_native_previous native-${_component})
endforeach()
