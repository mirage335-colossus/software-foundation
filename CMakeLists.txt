cmake_minimum_required(VERSION 3.24)
project(Foundation VERSION 0.1.0 LANGUAGES CXX)

if(CMAKE_SOURCE_DIR STREQUAL CMAKE_BINARY_DIR)
  message(FATAL_ERROR "Use an out-of-source build directory")
endif()
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)
include(CTest)
option(FOUNDATION_SANITIZERS "Enable address and undefined-behavior checks" OFF)
option(FOUNDATION_BUILD_GUI "Build optional pinned GUI boundary examples" OFF)
set(FOUNDATION_GUI_SOURCE "" CACHE PATH "Explicit pinned GUI boundary checkout")

add_library(foundation_core STATIC src/store.cpp)
add_library(foundation::core ALIAS foundation_core)
set_target_properties(foundation_core PROPERTIES EXPORT_NAME core CXX_EXTENSIONS OFF)
target_compile_features(foundation_core PUBLIC cxx_std_20)
target_include_directories(foundation_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}/generated>
  $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)

function(foundation_options target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /permissive- /utf-8)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  if(FOUNDATION_SANITIZERS)
    if(MSVC OR NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
      message(FATAL_ERROR "This sanitizer preset requires GCC or Clang")
    endif()
    target_compile_options(${target} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${target} PRIVATE -fsanitize=address,undefined)
  endif()
endfunction()
foundation_options(foundation_core)
if(FOUNDATION_SANITIZERS)
  target_link_options(foundation_core INTERFACE -fsanitize=address,undefined)
endif()
configure_file(cmake/version.hpp.in generated/foundation/version.hpp @ONLY)
add_executable(foundation-cli src/main.cpp)
target_link_libraries(foundation-cli PRIVATE foundation::core)
target_include_directories(foundation-cli PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/generated")
foundation_options(foundation-cli)

if(BUILD_TESTING OR FOUNDATION_BUILD_GUI)
  find_package(Python3 3.9 REQUIRED COMPONENTS Interpreter)
endif()
if(BUILD_TESTING)
  add_executable(foundation_core_test EXCLUDE_FROM_ALL tests/store_test.cpp)
  target_link_libraries(foundation_core_test PRIVATE foundation::core)
  foundation_options(foundation_core_test)
  add_test(NAME core.store COMMAND foundation_core_test)
  set_tests_properties(core.store PROPERTIES LABELS "fast;core" TIMEOUT 30)
  add_test(NAME core.cli COMMAND ${Python3_EXECUTABLE}
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_cli.py" $<TARGET_FILE:foundation-cli>)
  set_tests_properties(core.cli PROPERTIES LABELS "fast;core" TIMEOUT 30)
  add_test(NAME docs.links COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tools/check_docs.py")
  set_tests_properties(docs.links PROPERTIES LABELS "fast;tools" TIMEOUT 30)
  # Only explicitly named suites run; adding one requires registering its label.
  foreach(suite build agent_board test_plan artifact gui_boundary)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_${suite}.py")
      message(FATAL_ERROR "Missing required tool suite: ${suite}")
    endif()
    add_test(NAME tools.${suite} COMMAND ${Python3_EXECUTABLE} -m unittest discover
        -s "${CMAKE_CURRENT_SOURCE_DIR}/tests" -p "test_${suite}.py")
    set_tests_properties(tools.${suite} PROPERTIES LABELS "tools" TIMEOUT 120)
  endforeach()
  if(NOT CMAKE_CROSSCOMPILING)
    add_test(NAME integration.install COMMAND ${Python3_EXECUTABLE}
      "${CMAKE_CURRENT_SOURCE_DIR}/tests/check_install.py"
      --build "${CMAKE_BINARY_DIR}" --config $<CONFIG>
      --source "${CMAKE_CURRENT_SOURCE_DIR}")
    set_tests_properties(integration.install PROPERTIES LABELS "integration" TIMEOUT 180
      RESOURCE_LOCK install-tree)
  endif()
  add_custom_target(foundation-tests-core DEPENDS foundation_core_test foundation-cli)
  add_custom_target(foundation-tests-fast DEPENDS foundation-tests-core)
  add_custom_target(foundation-tests-tools)
  add_custom_target(foundation-tests-integration DEPENDS foundation-cli foundation_core)
  add_custom_target(foundation-tests DEPENDS foundation-tests-core foundation-tests-tools
    foundation-tests-integration)
endif()

if(FOUNDATION_BUILD_GUI)
  add_subdirectory(gui)
  if(BUILD_TESTING)
    add_dependencies(foundation-tests foundation-gui-tests)
    add_custom_target(foundation-tests-gui DEPENDS foundation-gui-tests)
  endif()
endif()

install(TARGETS foundation_core foundation-cli EXPORT FoundationTargets
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/generated/foundation/version.hpp"
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}/foundation)
install(EXPORT FoundationTargets NAMESPACE foundation::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation)
configure_package_config_file(cmake/FoundationConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfig.cmake"
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation)
write_basic_package_version_file("${CMAKE_CURRENT_BINARY_DIR}/FoundationConfigVersion.cmake"
  VERSION ${PROJECT_VERSION} COMPATIBILITY SameMajorVersion)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/FoundationConfigVersion.cmake"
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/Foundation)
install(FILES LICENSE DESTINATION ${CMAKE_INSTALL_DOCDIR})
install(FILES docs/installed.md DESTINATION ${CMAKE_INSTALL_DOCDIR} RENAME README.md)
install(FILES third_party/dependencies.json DESTINATION ${CMAKE_INSTALL_DOCDIR}/third_party)
set(_build_info "Version: ${PROJECT_VERSION}\nCompiler: ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION}\nTarget: ${CMAKE_SYSTEM_NAME} ${CMAKE_SYSTEM_PROCESSOR}\nBuild type: ${CMAKE_BUILD_TYPE}\nGUI enabled: ${FOUNDATION_BUILD_GUI}\nSanitizers: ${FOUNDATION_SANITIZERS}\nCompatibility: native build; no older OS qualification implied\n")
file(CONFIGURE OUTPUT "${CMAKE_CURRENT_BINARY_DIR}/build-info.txt" CONTENT "${_build_info}" @ONLY)
install(FILES "${CMAKE_CURRENT_BINARY_DIR}/build-info.txt" DESTINATION ${CMAKE_INSTALL_DOCDIR})

set(CPACK_PACKAGE_NAME software-foundation)
set(CPACK_PACKAGE_VENDOR "Software Foundation contributors")
set(CPACK_PACKAGE_VERSION ${PROJECT_VERSION})
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "Generic software development reference")
set(CPACK_PACKAGE_DIRECTORY "${CMAKE_BINARY_DIR}/packages")
set(CPACK_PACKAGE_FILE_NAME "${CPACK_PACKAGE_NAME}-${PROJECT_VERSION}-${CMAKE_SYSTEM_NAME}-${CMAKE_SYSTEM_PROCESSOR}")
set(CPACK_VERBATIM_VARIABLES TRUE)
if(WIN32)
  set(CPACK_GENERATOR ZIP)
else()
  set(CPACK_GENERATOR TGZ)
endif()
# Direct CPack also observes release exclusions; bypassing the wrapper is no waiver.
configure_file(cmake/PackagePolicy.cmake.in "${CMAKE_BINARY_DIR}/PackagePolicy.cmake" @ONLY)
set(CPACK_PROJECT_CONFIG_FILE "${CMAKE_BINARY_DIR}/PackagePolicy.cmake")
include(CPack)
