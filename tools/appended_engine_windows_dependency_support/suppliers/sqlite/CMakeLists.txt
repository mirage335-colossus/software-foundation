# Project-maintained static target for the exact retained SQLite amalgamation.
# The controller supplies its owned, validated native Windows toolchain/cache.
cmake_minimum_required(VERSION 3.24)
cmake_policy(SET CMP0091 NEW)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded CACHE STRING "Static Release CRT" FORCE)
project(FoundationWindowsSQLite VERSION 3.46.1 LANGUAGES C)

if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL "Windows" OR
   NOT CMAKE_SYSTEM_NAME STREQUAL "Windows" OR
   NOT CMAKE_SIZEOF_VOID_P EQUAL 8)
  message(FATAL_ERROR "SQLite supplier target requires native Windows x64")
endif()
if(NOT CMAKE_GENERATOR STREQUAL "Ninja" OR
   NOT CMAKE_C_COMPILER_ID STREQUAL "Clang" OR
   NOT CMAKE_C_SIMULATE_ID STREQUAL "MSVC" OR
   NOT CMAKE_C_COMPILER_TARGET STREQUAL "x86_64-pc-windows-msvc")
  message(FATAL_ERROR "SQLite supplier target requires the selected clang-cl/Ninja toolchain")
endif()
if(NOT CMAKE_BUILD_TYPE STREQUAL "Release")
  message(FATAL_ERROR "SQLite supplier target has only the static Release profile")
endif()
if(NOT IS_ABSOLUTE "${FOUNDATION_SQLITE_SOURCE}" OR
   NOT IS_DIRECTORY "${FOUNDATION_SQLITE_SOURCE}")
  message(FATAL_ERROR "The held exact SQLite amalgamation directory is required")
endif()
foreach(_file sqlite3.c sqlite3.h sqlite3ext.h)
  if(NOT EXISTS "${FOUNDATION_SQLITE_SOURCE}/${_file}" OR
     IS_DIRECTORY "${FOUNDATION_SQLITE_SOURCE}/${_file}")
    message(FATAL_ERROR "The exact SQLite amalgamation lacks ${_file}")
  endif()
endforeach()
file(STRINGS "${FOUNDATION_SQLITE_SOURCE}/sqlite3.h" _sqlite_version
     REGEX "^#define SQLITE_VERSION[ ]+\"3\\.46\\.1\"$" LIMIT_COUNT 1)
if(NOT _sqlite_version)
  message(FATAL_ERROR "The SQLite header version differs from the retained 3.46.1 archive")
endif()

add_library(sqlite3 STATIC "${FOUNDATION_SQLITE_SOURCE}/sqlite3.c")
set_target_properties(sqlite3 PROPERTIES
  OUTPUT_NAME sqlite3
  PREFIX ""
  SUFFIX ".lib"
  MSVC_RUNTIME_LIBRARY MultiThreaded
  INTERPROCEDURAL_OPTIMIZATION FALSE
  C_STANDARD 99
  C_STANDARD_REQUIRED TRUE)
# Preserve the maintained native Linux target's public SQLite API configuration.
target_compile_definitions(sqlite3 PUBLIC SQLITE_THREADSAFE=1
  SQLITE_OMIT_LOAD_EXTENSION SQLITE_ENABLE_FTS5)
# Same x64 SSE2 request as the maintained native Windows toolchain. The common
# controller must retain its fixed toolchain/cache policy through configure.
# This option alone is not evidence of an actual instruction-floor qualification.
target_compile_options(sqlite3 PRIVATE "/clang:-msse2")
target_include_directories(sqlite3 PUBLIC
  "$<BUILD_INTERFACE:${FOUNDATION_SQLITE_SOURCE}>"
  "$<INSTALL_INTERFACE:include>")
install(TARGETS sqlite3 ARCHIVE DESTINATION lib)
install(FILES "${FOUNDATION_SQLITE_SOURCE}/sqlite3.h"
              "${FOUNDATION_SQLITE_SOURCE}/sqlite3ext.h" DESTINATION include)
