cmake_minimum_required(VERSION 3.24)
project(cassifi_field_runtime LANGUAGES CXX)

add_executable(cassifi-field-runtime main.cpp)
target_compile_features(cassifi-field-runtime PRIVATE cxx_std_20)
target_compile_definitions(cassifi-field-runtime PRIVATE NOMINMAX WIN32_LEAN_AND_MEAN)

if(MSVC)
  target_compile_options(cassifi-field-runtime PRIVATE /W4 /permissive- /EHsc /utf-8)
else()
  target_compile_options(cassifi-field-runtime PRIVATE -Wall -Wextra -Wpedantic)
endif()

if(WIN32)
  target_link_libraries(cassifi-field-runtime PRIVATE advapi32)
endif()

set(CASSIFI_LLAMA_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/../../../CassiQwen/native/llama.cpp")
set(CASSIFI_LLAMA_BUILD "${CASSIFI_LLAMA_ROOT}/b8-stream")
if(WIN32 AND EXISTS "${CASSIFI_LLAMA_BUILD}/src/Release/llama.lib")
  target_include_directories(cassifi-field-runtime PRIVATE
    "${CASSIFI_LLAMA_ROOT}/include"
    "${CASSIFI_LLAMA_ROOT}/ggml/include")
  target_link_libraries(cassifi-field-runtime PRIVATE
    "${CASSIFI_LLAMA_BUILD}/src/Release/llama.lib")
  target_compile_definitions(cassifi-field-runtime PRIVATE CASSIFI_HAVE_LLAMA=1)
  foreach(runtime_dll llama.dll ggml.dll ggml-base.dll ggml-cpu.dll ggml-vulkan.dll)
    add_custom_command(TARGET cassifi-field-runtime POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different
        "${CASSIFI_LLAMA_BUILD}/bin/Release/${runtime_dll}"
        "$<TARGET_FILE_DIR:cassifi-field-runtime>/${runtime_dll}")
  endforeach()
endif()

find_package(Vulkan QUIET)
if(Vulkan_FOUND)
  target_link_libraries(cassifi-field-runtime PRIVATE Vulkan::Vulkan)
  target_compile_definitions(cassifi-field-runtime PRIVATE CASSIFI_HAVE_VULKAN=1)
endif()

install(TARGETS cassifi-field-runtime RUNTIME DESTINATION bin)

add_library(cassifi-weight-bank SHARED weight_bank.cpp)
target_compile_features(cassifi-weight-bank PRIVATE cxx_std_20)
target_compile_definitions(cassifi-weight-bank PRIVATE CASSIFI_WEIGHT_BANK_BUILD NOMINMAX WIN32_LEAN_AND_MEAN)
target_include_directories(cassifi-weight-bank PRIVATE
  "${CMAKE_CURRENT_SOURCE_DIR}"
  "${CASSIFI_LLAMA_ROOT}/ggml/include")
if(MSVC)
  target_compile_options(cassifi-weight-bank PRIVATE /W4 /permissive- /EHsc /utf-8)
else()
  target_compile_options(cassifi-weight-bank PRIVATE -Wall -Wextra -Wpedantic)
endif()

set(CASSIFI_GGML_BUILD "" CACHE PATH
  "Existing safe GGML build tree (for example b8-learn or b8-stream)")
if(NOT CASSIFI_GGML_BUILD)
  foreach(_candidate b8-learn b8-stream)
    if(EXISTS "${CASSIFI_LLAMA_ROOT}/${_candidate}/ggml/src/Release/ggml.lib")
      set(CASSIFI_GGML_BUILD "${CASSIFI_LLAMA_ROOT}/${_candidate}" CACHE PATH
        "Existing safe GGML build tree (for example b8-learn or b8-stream)" FORCE)
      break()
    endif()
  endforeach()
endif()
set(CASSIFI_GGML_LIB_DIR "${CASSIFI_GGML_BUILD}/ggml/src/Release" CACHE PATH
  "Directory containing ggml, ggml-base and ggml-cpu libraries")
set(CASSIFI_GGML_VULKAN_LIB "${CASSIFI_GGML_BUILD}/ggml/src/ggml-vulkan/Release/ggml-vulkan.lib" CACHE FILEPATH
  "GGML Vulkan library; leave empty to build CPU-only weight bank")
set(CASSIFI_GGML_RUNTIME_DIR "${CASSIFI_GGML_BUILD}/bin/Release" CACHE PATH
  "Directory containing GGML runtime DLLs")
set(_cassifi_ggml_libs
  "${CASSIFI_GGML_LIB_DIR}/ggml.lib"
  "${CASSIFI_GGML_LIB_DIR}/ggml-base.lib"
  "${CASSIFI_GGML_LIB_DIR}/ggml-cpu.lib")
foreach(_lib IN LISTS _cassifi_ggml_libs)
  if(NOT EXISTS "${_lib}")
    message(FATAL_ERROR "CassiFI weight bank requires GGML library: ${_lib}. Set CASSIFI_GGML_BUILD/CASSIFI_GGML_LIB_DIR explicitly.")
  endif()
endforeach()
target_link_libraries(cassifi-weight-bank PRIVATE ${_cassifi_ggml_libs})
if(EXISTS "${CASSIFI_GGML_VULKAN_LIB}")
  target_link_libraries(cassifi-weight-bank PRIVATE "${CASSIFI_GGML_VULKAN_LIB}")
  target_compile_definitions(cassifi-weight-bank PRIVATE CASSIFI_WEIGHT_BANK_HAS_VULKAN=1)
  find_package(Vulkan REQUIRED)
  target_link_libraries(cassifi-weight-bank PRIVATE Vulkan::Vulkan)
endif()
if(WIN32)
  foreach(_runtime ggml.dll ggml-base.dll ggml-cpu.dll ggml-vulkan.dll)
    if(EXISTS "${CASSIFI_GGML_RUNTIME_DIR}/${_runtime}")
      add_custom_command(TARGET cassifi-weight-bank POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_if_different
          "${CASSIFI_GGML_RUNTIME_DIR}/${_runtime}"
          "$<TARGET_FILE_DIR:cassifi-weight-bank>/${_runtime}")
    endif()
  endforeach()
endif()
install(TARGETS cassifi-weight-bank RUNTIME DESTINATION bin LIBRARY DESTINATION lib ARCHIVE DESTINATION lib)
install(FILES weight_bank.h DESTINATION include)
