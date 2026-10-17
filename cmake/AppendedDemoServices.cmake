# Application-owned composition examples; declaring this pure leaf enables no
# appended runtime, engine, Module or GUI backend in an ordinary build.
include_guard(GLOBAL)
get_filename_component(_foundation_demo_services_root "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
add_library(foundation_gui_appended_demo_services STATIC EXCLUDE_FROM_ALL
  "${_foundation_demo_services_root}/gui/shared/appended_demo_services.cpp")
target_include_directories(foundation_gui_appended_demo_services PUBLIC
  "${_foundation_demo_services_root}/include")
target_compile_features(foundation_gui_appended_demo_services PUBLIC cxx_std_20)
set_target_properties(foundation_gui_appended_demo_services PROPERTIES CXX_EXTENSIONS OFF)
foundation_options(foundation_gui_appended_demo_services)
