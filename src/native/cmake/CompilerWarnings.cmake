# Strict warnings for first-party native targets only (never applied to MinHook).
function(vic3_set_warnings target)
  if(MSVC)
    # C4324: structure padded due to alignment specifier (intentional cache-line alignment).
    target_compile_options(${target} PRIVATE /W4 /WX /permissive- /utf-8 /wd4324)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Werror)
  endif()
endfunction()
