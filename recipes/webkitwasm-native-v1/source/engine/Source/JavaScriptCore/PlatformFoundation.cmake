# Shared portable JSC implementation; native CLoop selection happens in
# CMakeLists.txt. No public GLib API, remote inspector or Windows COM API.
if (ENABLE_REMOTE_INSPECTOR OR ENABLE_JIT OR NOT ENABLE_C_LOOP)
    message(FATAL_ERROR "Foundation candidate requires CLoop without remote inspector")
endif ()
