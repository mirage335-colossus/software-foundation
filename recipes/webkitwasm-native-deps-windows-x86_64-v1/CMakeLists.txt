cmake_minimum_required(VERSION 3.24)

# This gate must precede project(), enable_language() and tool discovery.
include("${CMAKE_CURRENT_LIST_DIR}/cmake/components.cmake")
list(JOIN FOUNDATION_WINDOWS_DEPENDENCY_MISSING_INPUTS "\n  - " _missing)
message(FATAL_ERROR
  "MissingInputs:\n  - ${_missing}\n"
  "Windows dependency supplier entrypoint review is required. "
  "This metadata recipe has executable_plan=false and build=false.")

# Keep a literal, unreachable project() declaration: omitting it lets CMake
# insert an implicit project() before the gate and discover host compilers.
project(FoundationNativeWindowsDependencies LANGUAGES NONE)
