# Value-only prerequisites for native guard fixtures and optional appended
# profiles. No VM, retained SDK, kernel, supplier engine or startup route.
include_guard(GLOBAL)
get_filename_component(_foundation_appended_source_root "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)

function(foundation_appended_options target)
  target_compile_features(${target} PUBLIC cxx_std_20)
  target_include_directories(${target} PUBLIC
    "$<BUILD_INTERFACE:${_foundation_appended_source_root}/include>"
    "$<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>")
  set_target_properties(${target} PROPERTIES CXX_EXTENSIONS OFF)
  foundation_options(${target})
endfunction()

# Ordinary native tests must not add these leaves to the default build.
# Selected appended profiles retain their existing ABI target behavior.
if(FOUNDATION_APPENDED_PROFILE STREQUAL "none")
  add_library(foundation_appended_abi STATIC EXCLUDE_FROM_ALL src/appended/abi.cpp src/appended/registry.cpp)
else()
  add_library(foundation_appended_abi STATIC src/appended/abi.cpp src/appended/registry.cpp)
endif()
add_library(foundation_appended_document_forms STATIC EXCLUDE_FROM_ALL src/appended/document_forms.cpp)
target_link_libraries(foundation_appended_document_forms PUBLIC foundation_appended_abi)
# The copied editor wire and owner controller contain no HTML engine or VM.
# The pure C protocol leaf is private to this source graph; it is not an
# installed SDK include directory. Owner headers need it transitively in-tree.
add_library(foundation_appended_editor_codec STATIC EXCLUDE_FROM_ALL
  gui/shared/native_editor_codec.cpp)
target_include_directories(foundation_appended_editor_codec PUBLIC
  "$<BUILD_INTERFACE:${_foundation_appended_source_root}/abi/appended>")
foreach(_appended_codec foundation_appended_abi foundation_appended_document_forms
    foundation_appended_editor_codec)
  foundation_appended_options(${_appended_codec})
endforeach()
