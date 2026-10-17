# Native bitmap composition roots are created after the selected toolkit graph.
# They consume an independently admitted retained provider; no target here builds
# an engine or adds a guest interpreter to the web-only application.
include_guard(GLOBAL)
if(EMSCRIPTEN OR NOT FOUNDATION_APPENDED_PROFILE MATCHES "^(web|both)$")
    return()
endif()
if(NOT FOUNDATION_APPENDED_KERNEL_MAINTENANCE OR
        NOT FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED OR
        NOT FOUNDATION_APPENDED_ENGINE_NATIVE_CONSUMER_VERIFIED OR
        NOT TARGET foundation_gui_native_engine_bitmap_composition OR
        NOT TARGET foundation_appended_native_engine_loader OR
        NOT EXISTS "${_foundation_native_profile_directory}/appended_engine_compiled_native_profile.hpp")
    message(FATAL_ERROR "Native bitmap hosts require the admitted native rich application graph")
endif()

function(foundation_appended_native_bitmap_host backend)
    set(_target "foundation-appended-engine-${backend}")
    add_executable(${_target} "hosts/appended_engine_${backend}_main.cpp")
    target_link_libraries(${_target} PRIVATE
        foundation_gui_appended_demo_services
        foundation_gui_native_engine_bitmap_composition foundation_gui_native_surface
        foundation_appended_native_engine_loader foundation_appended_startup)
    target_include_directories(${_target} PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}"
        "${_foundation_native_profile_directory}" "${PROJECT_SOURCE_DIR}/abi/appended")
    target_compile_definitions(${_target} PRIVATE
        FOUNDATION_APPENDED_ENGINE_NATIVE_PROFILE_ENABLED=1
        "FOUNDATION_APPENDED_ENGINE_NATIVE_RUNTIME_HINT=\"${_foundation_native_runtime_hint_cpp}\"")
    if(FOUNDATION_APPENDED_ENGINE_NATIVE_ACTIONS_PROFILE)
        target_compile_definitions(${_target} PRIVATE FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=1)
    else()
        target_compile_definitions(${_target} PRIVATE FOUNDATION_APPENDED_ENGINE_NATIVE_DOCUMENT_ACTIONS_PROFILE=0)
    endif()
    if(FOUNDATION_APPENDED_PROFILE STREQUAL "both")
        target_compile_definitions(${_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=1)
        target_link_libraries(${_target} PRIVATE foundation_appended_engine_module_binding)
    else()
        target_compile_definitions(${_target} PRIVATE FOUNDATION_APPENDED_BINARY_CAPABILITY=0)
    endif()
    if(backend STREQUAL "fltk")
        foundation_gui_fltk_surface_target(${_target})
    elseif(backend STREQUAL "sdl")
        if(NOT TARGET foundation_gui_native_sdl_surface)
            message(FATAL_ERROR "Native SDL bitmap host is missing its generic Surface peer target")
        endif()
        target_link_libraries(${_target} PRIVATE foundation_gui_native_sdl_surface foundation_gui_sdl)
    elseif(backend STREQUAL "rev")
        if(NOT TARGET foundation_gui_native_rev_surface)
            message(FATAL_ERROR "Native Rev bitmap host is missing its generic Surface peer target")
        endif()
        target_link_libraries(${_target} PRIVATE foundation_gui_native_rev_surface gui_rev_adapter)
    elseif(NOT backend STREQUAL "framebuffer")
        message(FATAL_ERROR "Unknown native bitmap backend: ${backend}")
    endif()
    if(WIN32)
        # Keep the ordinary argc/argv contract, populated from original UTF-16
        # arguments before any narrow CRT conversion. Console output uses it too.
        target_compile_definitions(${_target} PRIVATE main=foundation_gui_main SDL_MAIN_HANDLED)
        target_sources(${_target} PRIVATE hosts/appended_engine_windows_entry.cpp)
        target_link_libraries(${_target} PRIVATE shell32)
        if(backend STREQUAL "framebuffer")
            target_compile_definitions(${_target} PRIVATE FOUNDATION_NATIVE_BITMAP_CONSOLE_ENTRY=1)
        else()
            set_target_properties(${_target} PROPERTIES WIN32_EXECUTABLE TRUE)
        endif()
        if(backend STREQUAL "sdl")
            target_compile_definitions(${_target} PRIVATE FOUNDATION_GUI_SDL_ENTRY)
        endif()
        if(MSVC)
            target_link_options(${_target} PRIVATE /MANIFEST:EMBED
                "/MANIFESTINPUT:${CMAKE_CURRENT_SOURCE_DIR}/hosts/windows_gui.manifest")
        else()
            enable_language(RC)
            target_include_directories(${_target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/hosts")
            target_sources(${_target} PRIVATE hosts/windows_gui.rc)
        endif()
    endif()
    target_compile_features(${_target} PRIVATE cxx_std_20)
    set_target_properties(${_target} PROPERTIES CXX_EXTENSIONS OFF)
    add_dependencies(${_target} foundation_gui_contract)
    add_dependencies(foundation-gui-hosts ${_target})
    foundation_options(${_target})
    if(FOUNDATION_GUI_DISTRIBUTABLE)
        install(TARGETS ${_target} RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR})
    endif()
endfunction()

foundation_appended_native_bitmap_host(framebuffer)
if(FOUNDATION_GUI_FLTK)
    foundation_appended_native_bitmap_host(fltk)
endif()
if(FOUNDATION_GUI_SDL)
    foundation_appended_native_bitmap_host(sdl)
endif()
if(FOUNDATION_GUI_REV)
    foundation_appended_native_bitmap_host(rev)
endif()
