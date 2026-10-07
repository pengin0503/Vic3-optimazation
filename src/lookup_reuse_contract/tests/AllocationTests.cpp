// Evaluate / NormalizeResult / record collection must not allocate. The
// global operator new is replaced in this test executable only and counts
// allocations while a window is open. Fixtures, the evaluator and the scope
// are created before the window.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <new>
#include <vector>

#include "FixtureSupport.h"
#include "NativeShadow.h"
#include "ResultNormalization.h"
#include "TestSupport.h"

namespace {

bool g_counting = false;
std::size_t g_allocations = 0;

void* CountedAllocate(std::size_t size) {
    if (g_counting) {
        ++g_allocations;
    }
    if (void* p = std::malloc(size == 0 ? 1 : size)) {
        return p;
    }
    throw std::bad_alloc();
}

}  // namespace

void* operator new(std::size_t size) { return CountedAllocate(size); }
void* operator new[](std::size_t size) { return CountedAllocate(size); }
void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }

using namespace lookup_contract;
using namespace lookup_contract::test;

namespace {

struct Fixed {
    std::uint64_t value;
    int calls = 0;
};

OpaqueResult Invoke(void* context, std::uint32_t) {
    auto* f = static_cast<Fixed*>(context);
    ++f->calls;
    return OpaqueResult{f->value};
}

struct Reentering {
    OfflineNativeShadow* shadow;
    FixtureBorrow borrow;
    Fixed* inner;
};

OpaqueResult InvokeReentering(void* context, std::uint32_t) {
    auto* r = static_cast<Reentering*>(context);
    r->shadow->Evaluate(r->borrow, 0, 0x13b8637, OpaqueOriginal{r->inner, &Invoke});
    return OpaqueResult{0x10d8};
}

}  // namespace

LOOKUP_TEST(allocation_counter_sees_heap_use) {
    g_allocations = 0;
    g_counting = true;
    auto p = std::make_unique<int>(1);
    g_counting = false;
    CHECK(g_allocations == 1);
}

LOOKUP_TEST(evaluate_path_does_not_allocate) {
    auto fixture = MakeFixedFixture();
    const FixtureBorrow borrow = fixture->Borrow();
    auto shadow = std::make_unique<OfflineNativeShadow>();
    shadow->SetMode(NativeMode::Shadow);
    auto scope = std::make_unique<NativeScope>(*shadow);
    std::vector<NativeRecord> out(kNativeRecordCapacity);
    Fixed key0{0x10d8};
    Fixed tail{0x1150};
    Fixed unknown{0};
    Fixed inner{0x10d8};
    Reentering reentering{shadow.get(), borrow, &inner};

    g_allocations = 0;
    g_counting = true;
    for (int i = 0; i < 3; ++i) {
        shadow->Evaluate(borrow, 0, 0x13b8637, OpaqueOriginal{&key0, &Invoke});    // NoCandidate, Equal
        shadow->Evaluate(borrow, 10, 0x13b8637, OpaqueOriginal{&tail, &Invoke});   // TailPositive skip
        shadow->Evaluate(borrow, 0, 0x13b8481, OpaqueOriginal{&unknown, &Invoke}); // excluded caller
        shadow->Evaluate(borrow, 0, 0x13b8637, OpaqueOriginal{&reentering, &InvokeReentering});
        (void)NormalizeResult(borrow, 0, OpaqueResult{0x10d8});
        (void)shadow->LastRecord();
    }
    const std::size_t drained = shadow->DrainRecords(out);
    g_counting = false;

    CHECK(g_allocations == 0);
    CHECK(drained == 15);  // per iteration: four outer calls and one inner call
    CHECK(key0.calls == 3);
    CHECK(inner.calls == 3);
}
