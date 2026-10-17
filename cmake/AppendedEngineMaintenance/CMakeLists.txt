cmake_minimum_required(VERSION 3.24)
project(FoundationCopied259Maintenance LANGUAGES NONE)

# This is a closed incremental producer. Never include the supplier's CMake or
# its embedder hook here: those names denote broad live vendor graphs.
if(NOT DEFINED FOUNDATION_ENGINE_PLAN OR NOT IS_ABSOLUTE "${FOUNDATION_ENGINE_PLAN}")
  message(FATAL_ERROR "Provide the independently verified maintenance plan fragment")
endif()
include("${FOUNDATION_ENGINE_PLAN}")
if(NOT FOUNDATION_ENGINE_GRAPH_VERSION STREQUAL "1")
  message(FATAL_ERROR "Unsupported copied259 maintenance graph")
endif()
foreach(_live IN ITEMS WebCore Skia Skia::Skia JavaScriptCore PAL WTF)
  if(TARGET "${_live}")
    message(FATAL_ERROR "Live supplier target is forbidden: ${_live}")
  endif()
endforeach()

add_custom_command(OUTPUT "${ENGINE_HEADER}" "${ENGINE_PROVIDER_BUILD}"
  COMMAND ${ENGINE_METADATA_COMMAND}
  DEPENDS ${ENGINE_METADATA_DEPENDS}
  VERBATIM COMMAND_EXPAND_LISTS)
set(_objects)
foreach(_id IN LISTS ENGINE_OBJECT_IDS)
  if(ENGINE_OBJECT_${_id}_IMPORTED)
    # Original depfiles are provenance only: their target is the old output.
    # Import failure is terminal; this edge contains no compiler fallback.
    add_custom_command(OUTPUT "${ENGINE_OBJECT_${_id}_OUTPUT}"
      BYPRODUCTS "${ENGINE_OBJECT_${_id}_REPORT}" "${ENGINE_OBJECT_${_id}_PROVENANCE}"
      COMMAND ${ENGINE_OBJECT_${_id}_COMMAND}
      DEPENDS ${ENGINE_OBJECT_${_id}_DEPENDS}
      VERBATIM COMMAND_EXPAND_LISTS)
  else()
  add_custom_command(OUTPUT "${ENGINE_OBJECT_${_id}_OUTPUT}"
    COMMAND ${ENGINE_OBJECT_${_id}_COMMAND}
    DEPENDS ${ENGINE_OBJECT_${_id}_DEPENDS} "${ENGINE_HEADER}" "${ENGINE_PROVIDER_BUILD}"
    DEPFILE "${ENGINE_OBJECT_${_id}_DEPFILE}"
    VERBATIM COMMAND_EXPAND_LISTS)
  endif()
  list(APPEND _objects "${ENGINE_OBJECT_${_id}_OUTPUT}")
endforeach()

set(_archives)
set(_archive_reports)
foreach(_name IN LISTS ENGINE_ARCHIVE_NAMES)
  if(ENGINE_ARCHIVE_${_name}_IMPORTED)
    # Copy an independently admitted exact regular archive. This edge has no
    # archive/index command and no compiler or repack fallback.
    add_custom_command(OUTPUT "${ENGINE_ARCHIVE_${_name}_OUTPUT}" "${ENGINE_ARCHIVE_${_name}_REPORT}"
      BYPRODUCTS "${ENGINE_ARCHIVE_${_name}_IMPORT_REPORT}"
      COMMAND ${ENGINE_ARCHIVE_${_name}_COMMAND}
      DEPENDS ${ENGINE_ARCHIVE_${_name}_DEPENDS}
      VERBATIM COMMAND_EXPAND_LISTS)
  else()
  add_custom_command(OUTPUT "${ENGINE_ARCHIVE_${_name}_OUTPUT}" "${ENGINE_ARCHIVE_${_name}_REPORT}"
    COMMAND ${ENGINE_ARCHIVE_${_name}_COMMAND}
    COMMAND ${ENGINE_ARCHIVE_${_name}_INDEX}
    COMMAND ${ENGINE_ARCHIVE_${_name}_READBACK}
    DEPENDS ${ENGINE_ARCHIVE_${_name}_DEPENDS}
    VERBATIM COMMAND_EXPAND_LISTS)
  endif()
  add_library("FoundationRetained::${_name}" STATIC IMPORTED GLOBAL)
  set_target_properties("FoundationRetained::${_name}" PROPERTIES
    IMPORTED_LOCATION "${ENGINE_ARCHIVE_${_name}_OUTPUT}"
    INTERFACE_LINK_LIBRARIES "")
  list(APPEND _archives "${ENGINE_ARCHIVE_${_name}_OUTPUT}")
  list(APPEND _archive_reports "${ENGINE_ARCHIVE_${_name}_REPORT}")
endforeach()
add_custom_command(OUTPUT "${ENGINE_FACTORY}" "${ENGINE_WASM}" "${ENGINE_MAP}"
  COMMAND ${ENGINE_LINK_COMMAND}
  DEPENDS ${_objects} ${_archives} ${ENGINE_LINK_DEPENDS}
  VERBATIM COMMAND_EXPAND_LISTS)
add_custom_command(OUTPUT "${ENGINE_INSPECTION}"
  COMMAND ${ENGINE_INSPECT_COMMAND}
  DEPENDS "${ENGINE_FACTORY}" "${ENGINE_WASM}" "${ENGINE_MAP}"
    ${ENGINE_INSPECT_DEPENDS} ${_archive_reports}
  VERBATIM COMMAND_EXPAND_LISTS)
add_custom_target(foundation-neutral-engine DEPENDS "${ENGINE_INSPECTION}")
