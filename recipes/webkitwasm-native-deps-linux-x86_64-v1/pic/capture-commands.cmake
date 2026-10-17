cmake_minimum_required(VERSION 3.24)
foreach(_name NATIVE_NINJA NATIVE_PIC_BINARY)
  if(NOT DEFINED ${_name} OR NOT IS_ABSOLUTE "${${_name}}" OR
     NOT EXISTS "${${_name}}" OR IS_SYMLINK "${${_name}}")
    message(FATAL_ERROR "Missing admitted PIC command-capture input: ${_name}")
  endif()
endforeach()
foreach(_name pic-commands.log pic-commands.stderr.log)
  if(IS_SYMLINK "${NATIVE_PIC_BINARY}/${_name}" OR
     IS_DIRECTORY "${NATIVE_PIC_BINARY}/${_name}")
    message(FATAL_ERROR "PIC command evidence path is not ordinary: ${_name}")
  endif()
endforeach()
# Ninja's tools mode prints the generated commands without rebuilding or
# running the DSO. CMake owns this post-link evidence edge and output stream.
execute_process(
  COMMAND "${NATIVE_NINJA}" -C "${NATIVE_PIC_BINARY}" -t commands
    foundation-native-dependencies-pic-check
  OUTPUT_FILE "${NATIVE_PIC_BINARY}/pic-commands.log"
  ERROR_FILE "${NATIVE_PIC_BINARY}/pic-commands.stderr.log"
  RESULT_VARIABLE _result)
if(NOT _result EQUAL 0)
  message(FATAL_ERROR "PIC command capture failed: ${_result}")
endif()
file(SIZE "${NATIVE_PIC_BINARY}/pic-commands.log" _bytes)
if(_bytes EQUAL 0)
  message(FATAL_ERROR "PIC command capture produced an empty record")
endif()
