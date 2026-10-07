# B0 Offline Native Shadow Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (Native) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有fixtureだけで、exact-build locator・opaque結果の正規化・original exactly once・shadowの失効条件を検証可能にする。

**Architecture:** locatorとmanifest生成は既存Python PE解析を再利用するoffline tool。C++20 contract libraryはStage Aの所有tableとhintを使い、合成address値だけを分類する。private所有stateをborrowが保持し、shadow/固定record collectorとJSON runnerを分離する。

**Tech Stack:** C++20、CMake 3.25以上、Python 3.10以上/stdlib、既存lookup_reuse_core。追加のproduction dependencyなし。

**Spec:** `docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md`（2026-10-07書面承認済み）。

**Status:** 2026-10-07に実装・検証完了（Native/executing-plans、実装開始main `f94a2d0`）。Task 1〜4の結果、CI、未実行項目は[検証記録](../../../research/generated/lookup-reuse-contract/verification.md)を参照。owned fixture上の接続契約だけを示し、Stage Bのnative gateは未充足。

## Global Constraints

- 配置は`src/lookup_reuse_contract/`。既存`src/lookup_reuse/`の公開API・検証条件・結果形式を弱めない。
- Windows SDK、MinHook、DLL、loaderに依存しない。live process memory、detour、native ABIの実呼び出し、Task 9 loader修正、V3PF v1変更、検索省略modeを追加しない。
- default Off、追加modeはShadowだけ。元callbackは有効な呼び出しごとに必ず一回実行し、64-bit合成result値と例外を変更せず返す。
- 40-byte stride、control `+4`、uint32 key `+8`、descriptor位置`+0x10`。原本は所有してから使用する。入力spanのコピーと外部memoryのborrowを区別する。
- fixture identity/generationはprivate ownerが発行する。外部pointer/span、caller-supplied epoch、boolによる検証権限を作らない。
- Evaluate経路にheap allocation、I/O、mutex、table全体の検証を入れない。fixture/evaluator作成、scope開始、runner出力はこの経路外。
- 一つのevaluatorは一つのthreadが同期的に使用する。cross-thread共有なし。scopeをworkerに暗黙継承しない。
- 元callback throw時はguard/hintを復旧して同じ例外を伝播し、そのcallの正常return recordを作らない。
- Mismatchでsession永久停止。Off/Shadow切替・新scopeで復活させない。fault injectionはtest binary限定でproduction API/CLI/Release成果物に置かない。
- native target JSON、V3PF golden、Stage A resultsを変更しない。性能向上やnative等価性を成果として報告しない。
- TaskごとにRED→GREEN、必要な回帰検証、commit。未実行の構成をPASSと書かない。最終統合はmainへforceなし/fast-forward、PRを作らず他branchを削除しない。

## Review Focus

1. hashをテスト入力に合わせても、壊れたPE境界/rel32を受理しない。CLIは任意hashを受け取らない → Task 1。
2. sentinel/fallbackが空slotのdescriptor値と重なる場合もfixtureを拒否し、0をUnknownから変更しない → Task 2。
3. callbackが元fixture ownerを破棄してもbytesを保持し、比較をProofLostにする → Task 3。
4. Off/対象外の外側callbackからの再入と、外側が内側throwをcatchする経路でもhintを失効する → Task 3。
5. record満杯・drain・CLIの不正数値/入出力同一pathがcallback回数や保全資産を壊さない → Tasks 1/3/4。

## Files and responsibilities

| unit | create paths | responsibility |
|---|---|---|
| manifest/locator | `tools/render_lookup_contract_manifest.py`, `tools/check_lookup_contract_locator.py`, `tests/test_lookup_contract_manifest.py`, `tests/test_lookup_contract_locator.py` | 正本/hash/schema確認、checked PE範囲、署名/caller検証 |
| generated manifest | `src/lookup_reuse_contract/generated/manifest_1_14_5.inc` | 正本から生成した定数。手編集禁止 |
| fixture/normalization | `src/lookup_reuse_contract/include/NativeFixture.h`, `core/NativeFixture.cpp`, `include/ResultNormalization.h`, `core/ResultNormalization.cpp`, `tests/NativeFixtureTests.cpp`, `tests/ResultNormalizationTests.cpp` | private所有state、generation/revocation、合成result→分類/slot |
| shadow/records | `src/lookup_reuse_contract/include/NativeShadow.h`, `core/NativeShadow.cpp`, `include/NativeRecords.h`, `tests/NativeShadowTests.cpp`, `tests/TestFaults.h` | callback/RAII/scope/session、固定collector、test-only seam |
| build/test support | `src/lookup_reuse_contract/CMakeLists.txt`, `tests/FixtureSupport.h` | Stage Aをsubdirectoryで参照。fixtureの手書きslot/期待値 |
| runner | `src/lookup_reuse_contract/runner/ContractRunner.h`, `ContractRunner.cpp`, `main.cpp`, `tests/VerifyContractRunner.py` | 固定seed/独立oracle、JSON/CLI。production coreだけをlink |
| CI/docs/results | `.github/workflows/lookup-reuse-contract.yml`, `src/lookup_reuse_contract/README.md`, `research/generated/lookup-reuse-contract/results.json`, `verification.md` | compiler/sanitizer検証と再現情報 |

通常は既存product codeを編集しない。Task 4だけ`README.md`/`src/README.md`に入口を追加する。各TaskはB0 READMEとverification記録を進捗に合わせて更新してよい。

## Task 1: manifest生成とoffline locator

**Files:** Files表のmanifest/locatorとgenerated manifest。生成includeのLF保持のため`.gitattributes`を追記する。

**Interfaces:** Pythonの`derive_manifest(evidence: dict, source_sha256: str) -> dict`、`render_manifest(manifest: dict) -> str`、`verify_owned_image(image: bytes, manifest: dict) -> dict`を作る。manifestのkeyはschema_version=1、manifest_source_sha256、executable_sha256、text_section、entry_rva、entry_pattern_hex、callers。callersの各要素はcaller_id、call_rva、return_rva、caller_entry_rva、allowed、pattern_hex。RVAはint、patternはhex string。実CLIは固定正本からだけmanifestを読み、`verify_exact_input(input_path: Path) -> dict`を呼ぶ。検証戻り値はschema_version=1、manifest_source_sha256、executable_sha256、entry_match_count、caller結果6件、static_only=true。

C++生成物はnamespace `lookup_contract::generated`で`CallerWitness { uint32_t caller_id, call_rva, return_rva, caller_entry_rva; bool allowed; }`、`kCallers`（6件）、`kManifestSourceSha256`、`kSchemaVersion`を出す。ID 1..4は正本のallowed順、5..6はexcluded順。unknownは0。pattern/PE metadataはPython manifestが保持する。C++はこのID/RVAを合成caller分類にだけ使い、locator成功をlive memoryの権限にしない。

- [x] **1. RED testsを書く。** `tests/test_lookup_contract_manifest.py`で正本のentry `0xf3e040`、hash、14-byte pattern、4 allowed/2 excluded、各call+5=return、metadata root begin、indexに記載のsource SHA/size、欠落/重複/schema改変、boolの型、deterministic rendering、stale `--check` failureを確認する。

```python
def test_manifest_keeps_four_allowed_two_excluded(self):
    m = derive_manifest(self.evidence, self.source_sha)
    self.assertEqual([c['call_rva'] for c in m['callers'] if c['allowed']],
                     [0x13b8632, 0x10b7db4, 0x10bd565, 0x10bd66b])
    self.assertEqual([c['call_rva'] for c in m['callers'] if not c['allowed']],
                     [0x13b847c, 0xc6b5ca])
```

locator testsに`mini_case() -> tuple[bytes, dict]`を定義する。AMD64/PE32+、`.text` RVA `0x1000`、raw pointer `0x200`、raw size `0x200`、entry `0x1020`、calls `0x1040,0x1060,0x1080,0x10a0,0x10c0,0x10e0`の小さい所有PE fixture。call signaturesは各siteのE8+signed rel32+異なる後続bytesとし、期待entry/returnはliteralにする。mini manifestだけはfixture bytesからhashを計算する。`test_mini_case_valid`はentry_match_count=1、caller結果6件、static_only=trueをassertする。

```python
def test_changed_call_is_rejected_after_hash_matches(self):
    image, m = mini_case()
    image = mutate_call_target(image, 0x1040)  # test helper: rel32のみ改変
    m['executable_sha256'] = hashlib.sha256(image).hexdigest()
    with self.assertRaises(ValueError):
        verify_owned_image(image, m)
```

`test_bad_hash`, `test_duplicate_entry_signature`, `test_duplicate_caller_signature`, `test_truncated_pe`, `test_raw_and_virtual_overflow`, `test_unsigned_rel32_is_not_accepted`, `test_changed_return_rva`, `test_out_of_text`, `test_same_input_output_rejected`, `test_failed_validation_does_not_write_output`も追加する。改変構造のtestsはhashを合わせて、hash gateだけの拒否でGREENにしない。
rel32検査専用caseではmini manifestの該当patternも改変bytesと一致させ、期待entryは変更せず、signature gateではなくdestination検査で拒否させる。
`test_exact_input_optional`はVIC3_DATA未設定時に明示skip、設定時は固定production manifestによるentry_match_count=1、4 allowed/2 excluded、pinned exe hashをassertする。
- [x] **2. REDを確認。** `python -m unittest discover -s tests -p 'test_lookup_contract_*.py' -v`。新module/API不在または上のassertionでFAILを確認する。
- [x] **3. 最小実装。** 正本は`research/generated/native-shadow-preparation-2026-10-07/static-evidence.json`、indexは同folderの`artifact-index.json`。schema=1、entry signatureと全6caller signature/metadata、sourceのSHA-256/sizeを検証し、署名を含む内部manifestとC++includeを同じ正本から生成する。既存`analyze_vic3.read_input/PE`を再利用するが、parser例外を明確なValueError/CLI exit 2に変換し、header/section table/raw/virtual boundsをこのtoolで追加確認する。整数演算の各結果をuint32範囲とinput lengthに照合し、RVAのzero-fillをfile-backed bytesとみなさない。entry/caller patternは重複を含め`.text`全体で一意、指定RVAで一致、callはE8/5 bytes/signed int32 rel32で同じentry、returnはcall+5を検証する。CLIにmanifest/hash置換optionを追加しない。
- [x] **4. GREENと生成物check。** 上のunittestを全PASSにし、`python tools/render_lookup_contract_manifest.py --check`をPASSにする。optional exact input検証は`python tools/check_lookup_contract_locator.py "$VIC3_DATA" --output build/lookup-contract/locator.json`。4 allowed/2 excludedとstatic_only=trueを確認する。CLIの入力はexe/ZIP/既存read_inputが対応するdirectory、出力はJSON。同一input/outputは拒否し、検証成功後だけ出力する。
- [x] **5. Commit。** `git add`はFilesで列挙したpathだけ。message: `feat: add offline lookup contract manifest and locator`。

## Task 2: 所有fixture、borrow、結果正規化

**Files:** Files表のfixture/normalization、CMake/test support、B0 README初版。

**Interfaces (namespace `lookup_contract`):**

```cpp
struct OpaqueResult { std::uint64_t value = 0; /* value equality */ };
struct NativeFixtureSpec {
    std::uint64_t mask, slot_count, table_base;
    OpaqueResult end_sentinel, fallback;
};
struct FixtureError { enum class Kind { TableValidation, AddressLayout, EpochExhausted }; Kind kind; std::optional<lookup_reuse::ViewError> table_error; };
class FixtureBorrow;  // default empty, copyable; private owning-state constructor
class OwnedNativeFixture {
public:
    static std::variant<std::unique_ptr<OwnedNativeFixture>, FixtureError>
        Create(const NativeFixtureSpec&, std::span<const std::byte> input);
    FixtureBorrow Borrow() const noexcept;
    void Revoke() noexcept;
    ~OwnedNativeFixture(); // revokes, releases its state reference
    // no copy/move, no public constructor
};
// FixtureBorrow: Valid() noexcept; Generation() noexcept; default-empty detection.
enum class ResultClass { PrimaryPositive, TailPositive, EndSentinel, Fallback, InvalidPrimaryResult, Unknown };
struct NormalizedResult { ResultClass kind; std::optional<std::size_t> slot; };
NormalizedResult NormalizeResult(const FixtureBorrow&, std::uint32_t key, OpaqueResult) noexcept;
```

`FixtureBorrow`が持つprivate `shared_ptr<FixtureState>`はimmutable bytes、Stage A owner、spec、private generation、revoked flagを保持する。raw Viewへのaccessはnormalizer/shadowのfriend/private経路だけ。public Validは状態の照会であり、boolからborrowを作るconstructorはない。borrowがcallback終了までstateをpinするため、owner破棄後もdanglingにならない。全操作は同じthreadの同期使用。

- [x] **1. RED testsとbuild targetを用意。** B0 CMakeは`enable_testing()`と`add_subdirectory(../lookup_reuse stage-a)`で既存target `lookup_reuse_core`を参照する。B0 `lookup_contract_core`、`lookup_contract_tests`を作る。Releaseでも消えない既存`tests/TestSupport.h`/`TestMain.cpp`を別test executableで再利用し、Stage Aのsourceを編集しない。

`MakeFixedFixture() -> unique_ptr<OwnedNativeFixture>`をFixtureSupport.hに作る。mask=7、10 slots、base=`0x1000`、sentinel=`0x8000`、fallback=`0x9000`。手書き配置はkey0@5/control1、key8@6/control2、key2@7/control1、key10@8/control2。他slotはempty。独立vectorを以下に固定する。

```cpp
LOOKUP_TEST(primary_tail_unknown_vectors) {
    auto f = MakeFixedFixture(); auto b = f->Borrow();
    CHECK(NormalizeResult(b, 0, {0x10d8}).slot == std::optional<std::size_t>{5});
    CHECK(NormalizeResult(b, 2, {0x1128}).kind == ResultClass::PrimaryPositive);
    CHECK(NormalizeResult(b, 10, {0x1150}).kind == ResultClass::TailPositive);
    CHECK(NormalizeResult(b, 0, {0}).kind == ResultClass::Unknown);
    CHECK(NormalizeResult(b, 0, {0x10d9}).kind == ResultClass::Unknown);
}
```

別fixture mask=0/2 slots/key=`UINT32_MAX`@0/control1でfirst-primary=`0x1010`を確認。空slotに古いkeyを残した`0x1010`/key0とwrong-keyの`0x10d8`/key8はInvalidPrimaryResult。tail内のempty/wrong-keyはUnknown。sentinel/fallback classification、copy後にinput変更しても結果不変、宣言値重複/0/全descriptor位置との衝突、base/offset/size overflow、invalid signed-mask表現、既存ViewError拒否を試す。
- [x] **2. REDを確認。** `cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON`、`cmake --build build/lookup-contract --config Release`。まず新API未実装によるcompile/link/test FAILを記録する。
- [x] **3. 最小実装。** inputをprivate copyし、そのcopyから既存`OwnedTableFixture::Create`を呼ぶ。呼び出し側のidentityは受け取らず、process内のprivate monotonic generationをCASで発行し、上限到達時はwrap前にEpochExhausted。map_id/storage_id/lifetime_epochはこのunique generation、layout_versionはStage Aの1とする。generationの状態は公開せず、overflow試験だけTask 3のtest専用guardを使う。maskはnative signed int32で非負に表現可能な範囲に制限する。

合成addressはuint64演算だけ。base+40*slot_countと各descriptor offsetのoverflowを検査し、sentinel/fallbackは非zero・互いに異なる・**emptyを含む全slotのdescriptor値と非衝突**を要求する。NormalizeResultは借用が無効ならUnknown/slotなし、borrowが有効なら表の6分類だけを返す。slotを返すのはPrimaryPositive/TailPositiveだけ。base未満、descriptor offset未満、misaligned、span外をdereferenceなしで拒否する。constructor検証に失敗したstateを返さない。
- [x] **4. GREEN。** `ctest --test-dir build/lookup-contract -C Release --output-on-failure`で新testsとStage A testsをPASSにする。新fixture・borrowをraw pointer/spanや任意identityから構築できないcompile-time assertion、同base/bytesの再生成でgenerationが異なることも確認する。
- [x] **5. Commit。** message: `feat: add owned native-shaped fixtures and result normalization`。

## Task 3: original exactly once、scope/session、固定record

**Files:** Files表のshadow/records、TestFaults、NativeFixture.cpp/CMakeをtest variant対応に追記。

**Interfaces:**

```cpp
enum class NativeMode { Off, Shadow };
enum class NativeStatus { Equal, Mismatch, NoCandidate, Skipped };
enum class NativeSkip { None, Off, SessionDisabled, Reentrant, MissingScope,
    CallerExcluded, MissingFixture, ProofLost, TailPositive, EndSentinel,
    Fallback, InvalidPrimaryResult, UnknownResult };
struct OpaqueOriginal { void* context; OpaqueResult (*invoke)(void*, std::uint32_t); };
struct NativeRecord {
    std::uint32_t version, caller_id, key;
    std::uint64_t session_id, scope_id;
    NativeStatus status; NativeSkip reason;
    std::optional<ResultClass> result_class;
    std::optional<std::size_t> candidate_slot, original_slot;
    OpaqueResult original;
};
inline constexpr std::size_t kNativeSkipCount = 13, kResultClassCount = 6;
struct NativeCounters {
    std::uint64_t original_calls = 0, candidate_attempts = 0, candidate_hits = 0,
        equal = 0, mismatch = 0, no_candidate = 0, reentrant_calls = 0,
        exception_calls = 0, dropped_records = 0;
    std::array<std::uint64_t, kNativeSkipCount> skipped_by_reason{};
    std::array<std::uint64_t, kResultClassCount> result_class_counts{};
};
class OfflineNativeShadow {
public:
    OfflineNativeShadow(); // private unique session_id; initially Off
    void SetMode(NativeMode) noexcept;
    NativeMode Mode() const noexcept;
    bool SessionDisabled() const noexcept;
    OpaqueResult Evaluate(FixtureBorrow, std::uint32_t key,
        std::uint32_t return_rva, OpaqueOriginal original);
    std::optional<NativeRecord> LastRecord() const noexcept;
    const NativeCounters& Counters() const noexcept;
    std::size_t DrainRecords(std::span<NativeRecord> output) noexcept;
    // noncopyable/nonmovable
};
class NativeScope { public: explicit NativeScope(OfflineNativeShadow&); ~NativeScope(); /* no copy/move */ };
```

return_rvaはfixtureが供給する合成値であり、実return address取得ではない。caller_idをgenerated tableから引き、ID 1..4だけ比較対象とする。unknown/excludedはCallerExcluded。正規化を行わなかったrecordのresult_classはnullopt、正規化して不明だった場合はUnknown。

- [x] **1. RED tests。** `test_original_once_all_modes_and_skips`で各NativeSkipとUnknown/0/UINT64_MAXの戻り値保持、invoke回数を確認。`test_primary_warm_then_equal`では同scope内のkey0/`0x13b8637`/元結果`0x10d8`を2回呼び、NoCandidate→Equal、両方original一回、candidate slot=5とする。`test_revoked_during_callback`と次のowner破棄を含める。

```cpp
LOOKUP_TEST(owner_destroyed_in_callback_is_proof_lost) {
    auto f = MakeFixedFixture(); auto b = f->Borrow();
    OfflineNativeShadow s; s.SetMode(NativeMode::Shadow); NativeScope scope(s);
    // test helper callback: calls++, f.reset(), returns OpaqueResult{0x10d8}
    CHECK(s.Evaluate(b, 0, 0x13b8637, DestroyOwnerOriginal(f)).value == 0x10d8);
    CHECK(s.Counters().original_calls == 1);
    CHECK(s.LastRecord()->reason == NativeSkip::ProofLost);
    CHECK(!b.Valid());  // bytes remain owned by b; no dangling access
}
```

`test_off_outer_reentry_invalidates`, `test_excluded_outer_reentry_invalidates`、`test_inner_throw_caught_by_outer`、`test_same_exception_propagates`（exception_ptrを比較）、`test_scope_boundaries_and_nested_rejection`、`test_mode_roundtrip_during_callback_invalidates`、`test_scope_replaced_during_callback_invalidates`、`test_other_evaluator_does_not_inherit_scope`、`test_address_reuse_has_no_candidate`を作る。getter/record/countの独立assertionでhintを誤記憶していないことを次callから確認する。

`test_mismatch_disables_until_new_evaluator`は温まったcandidateをtest専用seamでslot6に差し替え、originalはslot5のままとする。Mismatch、Off→Shadow、新scopeでもSessionDisabled、新evaluatorのみNoCandidateを確認。`test_record_full_and_drain`は256件の正常call後に257件目だけdrop、original_calls=257、dropped_records=1、LastRecordは257件目、drain後は再び記録可能を確認する。
- [x] **2. REDを確認。** `lookup_contract_tests --filter primary_warm_then_equal`等、登録した実名で実行し、未実装の状態管理/契約によりFAILになることを記録する。
- [x] **3. 最小実装。** 最初に全callのdepth guardを設定し、再入は外側を失効する。許可されたcallだけ既存`PositiveSlotHint::Try`を呼ぶ。callback後に同じborrowのgeneration/revocation、outer-invalidatedを再確認する。scope/modeの変更はcallback中に元へ戻っても失効とする。mode OffならOff、scope変更ならMissingScope、modeだけ変化してShadowへ戻ったらProofLostでskipする。候補計算にReferencePositiveSearchを呼ばない。sourceの§6優先順位を守り、再入の失効は理由順位と独立に行う。

PrimaryPositiveのみslot比較/Remember。NoCandidateは古いhintをclearして有効元slotをRemember。全Skipped/Mismatch/throwはclear。exceptionはRAIIでcleanupして再throwし、callback retryはしない。新scope IDはevaluator内のmonotonic counterで発行し、上限前にconstructorでoverflow_error、新session IDもprivate allocatorでwrapを拒否する。

固定容量256のcollectorはevaluator内部array。満杯ではcounterだけ増やし、LastRecord/returnは通常通り更新。DrainRecordsは呼び出しの外で同threadから使う。counterとrecord更新はnoexcept、uint64 counterはwrapせず飽和させる。正常call数とthrow数を区別し、result-class counterは実際に正規化したcallだけ増やす。

CMakeは同じB0 core sourceから`lookup_contract_core`（production）と`lookup_contract_test_core`を別にbuildする。`LOOKUP_CONTRACT_TESTING=1`はtest_coreとunit executableの両方だけに設定し、headerのclass定義とlibraryの定義を一致させる。private fault code/アクセスはguard内だけ、headerは`tests/TestFaults.h`に置く。fixture generation上限とcandidate比較前の差し替えを試す。unit executableはtest_coreだけ、runnerはproduction coreだけにlinkし、両variantを同じexecutableに混ぜない。
- [x] **4. GREEN。** 全CTest PASS。test用global operator new counterで、事前作成したthrowしないallocation-free callbackのEvaluate/正規化/collector経路のallocationが0であることを確認する。ASanでowner破棄/再入を試す。production runner側ではfault header/APIが使えないことをCMakeのcompile-negative checkとsource guardで確認する。I/O/mutex/full-validation呼び出しがEvaluateにないことをレビューする。
- [x] **5. Commit。** message: `feat: add opaque-result offline shadow contract and fixed records`。

## Task 4: 独立oracle runner、CLI、CI、検証記録

**Files:** Files表のrunner/CI/docs/results、B0 CMake、README.md/src/README.mdの入口。

**Interfaces (namespace `lookup_contract::runner`):** `RunConfig { uint32_t seed=20261007; size_t rebuilds=1000; }`、`RunSummary`（config、boundary_fixture_count、fixture_count、query_count、oracle_mismatches、NativeCounters、caller ID別call/compare/skip、all_game_gates_met=false）、`RunContract(const RunConfig&) -> RunSummary`、`WriteJson(const RunSummary&, ostream&) -> void`、`Passed(const RunSummary&) noexcept -> bool`。fixture builderのplacement mapが期待slotを記録し、callbackはそのmapから合成addressを返す。normalizer/Stage A searchを期待slot計算の唯一の方法にしない。

- [x] **1. RED tests。** `VerifyContractRunner.py`で同seedの2回のJSON内容一致、全4allowedと2excluded caller coverage、6結果分類の固定boundary coverage、opaque returnのoracle_mismatches=0、集計counterとcallback総数の整合、default Off、queue drop/drainの固定caseを確認する。production runnerではforced mismatchを使わず、unit testのMismatch証拠と区別する。`--help`/正常CLI、unknown option、重複option、seed<0/>UINT32_MAX、rebuilds=0/>100000、欠けたoutput/値、不正数値、書き込み不能pathは明確なnonzero exitを確認する。
- [x] **2. REDを確認。** `python src/lookup_reuse_contract/tests/VerifyContractRunner.py build/lookup-contract/lookup_contract_runner`（WindowsではRelease/exe）。新CLI/集計未実装によるFAILを残す。
- [x] **3. 最小実装。** 境界fixtureはseed非依存、random生成は独自固定PRNGを使い、標準distributionやpointer値/hash-map iteration順に依存しない。生成ごとに同じnumeric baseを再使用してidentity失効を検査する。通常primaryを温める反復とtail/sentinel/fallback/Unknown/invalid-result、Off/対象外/再入/ProofLostを含める。CLIは`--seed N --rebuilds N --output PATH`、default値はRunConfig、seedは0..UINT32_MAX、rebuildsは1..100000。JSONキー順/改行を固定し、session/generationはrun内ordinalへ正規化してprocess間の再現性を保つ。live locator結果は別JSONであり、runnerのall_game_gates_metをtrueにしない。

専用CIはubuntu-24.04 GCC Release、Clang Release、Clang ASan+UBSan、およびwindows-2022 MSVC x64 Release。warnings-as-errorsを有効化し、codegen --check、新しいPython unit（`-p 'test_lookup_contract_*.py'`）、B0 CTest、fresh JSONとcommit済みJSON内容比較を実行する。既存Python全testsは従来のtests workflowが依存をinstallして実行し、ローカルでも既存`tools/requirements-callgraph.txt`を使って実行する。Linuxはbyte一致も確認。path filterにB0 source/results、Stage A source、両manifest/locator tool・新Python tests・正本、専用workflowを含める。実exeをCIに持ち込まず、VIC3_DATA optional testは未設定時に明示skipする。
- [x] **4. GREENと最終検証。** 次のcommand/結果を`research/generated/lookup-reuse-contract/verification.md`に保存し、testsが拾うfaultを確認する。test fileを行動と同じbodyに書き直してGREENにしない。

```bash
python -m unittest discover -s tests -v
python tools/render_lookup_contract_manifest.py --check
python tools/render_native_profiler_targets.py --check
cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/lookup-contract --config Release
ctest --test-dir build/lookup-contract -C Release --output-on-failure
build/lookup-contract/lookup_contract_runner --seed 20261007 --rebuilds 1000 --output build/lookup-contract/results.json
python src/lookup_reuse_contract/tests/VerifyContractRunner.py build/lookup-contract/lookup_contract_runner --expected research/generated/lookup-reuse-contract/results.json
git diff --check
```

初回expected resultsはfixed-seed runnerで生成し、検証した数値だけcommitする。Clangは別build dirで`-DCMAKE_CXX_COMPILER=clang++`、sanitizerはさらに`-DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'`。Windowsは`-A x64`/`--config Release`/`ctest -C Release`とexe pathを使う。専用CIの4構成と既存Windows native CIを実際に確認する。実装開始mainからのdiffでV3PF golden/target JSON/Stage Aコード/resultsが無変更であることを確認する。添付ZIPを利用できる場合はlocatorをexact exeでも検証し、CLI outputのhash/6callers/static_onlyを確認する。
- [x] **5. Commitとhandoff。** message: `test: add reproducible lookup contract runner and cross-platform CI`。設計/計画の状態とcheckboxを実際の結果に合わせて更新する。レビュー指摘のうちB0 scope内だけ解決し、Critical/Important残件なし、検証完了後に最新mainを取り込みforceなしでfast-forward統合する。報告はcommit、CI links、再現command、不一致/skip/drop/coverage、未実行構成と残るnative gateを含める。

## Self-review mapping

spec §1/2/9 → Global Constraints/Task 4 docs、§3 → Task 1、§4/5 → Task 2とTask 3 owner破棄試験、§6/7 → Task 3/4、§8 → 全Tasks。元callbackの引数/結果/例外、各skip、全4caller/2excluded、production fault seamの不在は明示testsで固定する。B0は一つのoffline接続契約であり、Task 9/live adapterはこの計画に混ぜない。
