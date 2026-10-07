// Must not compile: production OfflineNativeShadow has no fault members, even
// for code that declares the friend type itself.
#include "NativeShadow.h"

namespace lookup_contract::testing {
struct FaultAccess {
    static void Override(OfflineNativeShadow& shadow) { shadow.fault_candidate_override_ = 1; }
};
}  // namespace lookup_contract::testing

int main() { return 0; }
