cmake_minimum_required(VERSION 3.24)
project(FoundationNativeSQLite VERSION 3.46.1 LANGUAGES C)
if(NOT IS_ABSOLUTE "${SQLITE_AMALGAMATION}" OR
   NOT EXISTS "${SQLITE_AMALGAMATION}/sqlite3.c" OR
   NOT EXISTS "${SQLITE_AMALGAMATION}/sqlite3.h")
  message(FATAL_ERROR "Missing admitted SQLite 3.46.1 amalgamation")
endif()
add_library(sqlite3 STATIC "${SQLITE_AMALGAMATION}/sqlite3.c")
set_target_properties(sqlite3 PROPERTIES POSITION_INDEPENDENT_CODE ON)
target_compile_definitions(sqlite3 PUBLIC SQLITE_THREADSAFE=1
  SQLITE_OMIT_LOAD_EXTENSION SQLITE_ENABLE_FTS5)
target_include_directories(sqlite3 PUBLIC "${SQLITE_AMALGAMATION}")
find_package(Threads REQUIRED)
target_link_libraries(sqlite3 PUBLIC Threads::Threads m)
# The superbuild's explicit selected installer owns header/archive/.pc staging.
