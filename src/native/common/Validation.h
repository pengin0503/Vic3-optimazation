#pragma once
#include <stdexcept>
namespace vic3 {
enum class ValidationError { None, FileIo, HashFailed, UnsupportedHash, UnsupportedMachine, UnsupportedPe, MalformedPe, InvalidTargetSpec, SignatureMissing, SignatureAmbiguous, InvalidAddress, UnreadableVtable, VtableMismatch };
template<class T> struct ValidationResult { T value{}; ValidationError error{ValidationError::None}; explicit operator bool() const noexcept { return error==ValidationError::None; } };
class ValidationFailure : public std::runtime_error { public: ValidationError code; explicit ValidationFailure(ValidationError c):std::runtime_error("native validation failed"),code(c){} };
}
