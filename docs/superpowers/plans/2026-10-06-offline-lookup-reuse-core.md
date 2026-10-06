# Offline Lookup Reuse Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有された不変の合成table上で成功slotの再利用を検証し、元検索の結果を維持するoffline shadow比較と再現可能な結果を提供する。

**Architecture:** privateな所有bytesの検証からのみviewを発行し、通常検索と1つのpositive-slot hintを独立したcoreに置く。shadow evaluatorは候補の有無によらず元callbackを1回呼び、その結果を返す。結果のJSON整形はrunnerに分離する。

**Tech Stack:** C++20、標準ライブラリ、CMake 3.25以上（本計画のbuild要件）、GCC / MSVC、CTest、既存Python unittest。coreに外部依存は追加しない。

**Spec:** `docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md`（この会話で書面承認済み）

実行方式: 既存のユーザー選択を維持し、Native / `superpowers:executing-plans`で本人が順次実装する。計画レビュー後に開始する。

**実装状況（2026-10-06 UTC）:** Task 1〜4を実装済み。基準main `788e29d`。実行記録・RED/GREEN・CI結果・計画からの差分は[verification.md](../../../research/generated/lookup-reuse-core/verification.md)を参照。テスト名の重複回避のため、Task 1の検索部分は`tail_positive_search`、Task 3のshadow版は`shadow_wrong_key_result_not_remembered`とした。boundary fixtureは4 snapshot（tail、backshift前後、mask0/最大key）。段階Bは未着手。作成基準main: `c7ec2845ff10b207e151cdb0fcc6cda938ab54e8`。日付: 2026-10-06 UTC。

## Global Constraints

- 対象は段階Aのみ。段階Bのnative adapter、DLL、detour、ゲーム内測定、性能patchは作らない。
- C++20、MSVC/GCCでbuildできるplatform-neutral static library。外部依存・ダウンロード・game SDKを不要にする。
- `src/lookup_reuse/`はWin32 API、live process memory、MinHook、profiler codecを知らない。native loader/DLLをbuildしない。
- 所有された不変bytesからのみvalidated viewを発行する。可変な外部spanへのbool certificateを認めず、所有者の破棄・move後のview使用も禁止する。
- identityは `map_id`、`storage_id`、`lifetime_epoch`、`layout_version`。epochはfixture所有者が変更・再配置・再生成で更新する。game側にこのfieldが存在すると仮定しない。
- layout_version=1、40-byte record、little-endian、control byte +4、full uint32 key +8。出力はslot index。descriptor内容は読まない。
- maskは非負の2^n-1。control=0はempty、positive controlはhomeからの非wrap probe距離+1。255を超える距離をvalidにしない。
- hintはidentity、mask、full key、primary slot indexだけ。miss、tail/padding/sentinel、invalid view、scope終了はcacheしない。
- shadowは元callbackを1回呼び、元結果をそのまま返し、例外を伝播する。mismatchでそのobserver sessionの候補計算を停止する。
- reentrancyは内側候補をbypassし外側hintを無効化する。fixed-size record/counterを使い、整形とfile I/Oはrunnerに置く。
- 初期modeはOff。Off / Shadowだけを定義する。V3PF v1、既存target ID・golden・Task 9 runtime計画は変更しない。
- 既存Pythonモデルをexpected generatorとして使わない。hand-derived配置、独立key集合、fixed seedと別のboundary fixtureを併用する。

## Review Focus

1. mask=0の1-primary-slot tableと最大uint32 keyでも、安全なhit/miss判定をする（Task 1 `one_primary_and_max_key`）。
2. primary終端からtailへの正の検索を認めても、そのtail結果をhintとして保存しない（Task 1/2 `tail_positive_never_cached`）。
3. callbackが例外を投げた後の次の呼び出しは、reentrant扱いや古いhintを引き継がない（Task 3 `exception_then_next_call`）。
4. callbackの正常戻り値が別keyのslotを指しても、戻り値を改変せずhintへ採用しない（Task 2/3 `wrong_key_result_not_remembered`）。
5. mismatch後にOff→Shadowへ切り替えても同じsessionの停止状態を解除しない（Task 3 `mode_toggle_keeps_disabled`）。

---

## File mapと実行上の前提

| ファイル | 責務 / 初出task |
|---|---|
| `src/lookup_reuse/CMakeLists.txt` | 独立static lib、tests、runner、CTest登録 / 1, 4 |
| `src/lookup_reuse/include/TableView.h`, `core/TableView.cpp` | ownership、typed validation、bounded slot読み取り、通常検索 / 1 |
| `src/lookup_reuse/include/PositiveSlotHint.h`, `core/PositiveSlotHint.cpp` | 1つの成功locationの検証と消去 / 2 |
| `src/lookup_reuse/include/ShadowComparison.h`, `core/ShadowComparison.cpp` | original callback、scope、再入、比較statusとcounts / 3 |
| `src/lookup_reuse/tests/TestSupport.h`, `tests/TestMain.cpp` | throwing CHECK、名前指定実行、hand-derived raw fixture生成 / 1 |
| `src/lookup_reuse/tests/TableViewTests.cpp`, `tests/PositiveSlotHintTests.cpp`, `tests/ShadowComparisonTests.cpp` | 各契約のテスト / 1, 2, 3 |
| `src/lookup_reuse/runner/OfflineRunner.h`, `runner/OfflineRunner.cpp`, `runner/main.cpp` | fixed-seed differential比較、standalone JSON / 4 |
| `src/lookup_reuse/tests/OfflineRunnerTests.cpp`, `tests/VerifyRunner.py` | runnerの集計・再現性・CLI境界 / 4 |
| `src/lookup_reuse/README.md`, `src/README.md`, `README.md` | build/run手順と段階A完了境界 / 4 |
| `.github/workflows/lookup-reuse-core.yml` | ubuntu-24.04 GCC / windows-2022 MSVC Release検証 / 4 |
| `research/generated/lookup-reuse-core/results.json`, `verification.md` | 実際に生成した合成結果、環境・commands・skip / 4 |

既存 `.github/workflows/tests.yml` はPython jobを維持する。build出力はgit対象外の `build/lookup-reuse/`。新規C++テストは標準`assert`に頼らず、Releaseでも失敗するCHECKを使う。test executableは `--filter <exact-name>` と `--list` を持ち、存在しないfilterは非0終了する。

承認後、using-git-worktreesを読み、GitHubの最新mainから隔離branch/workspaceを用意する。connectorのみでcheckoutできない場合は、正確なcommitのtext filesを取得して隔離workspaceを構成し、GitHubのbranch/tree/commit/ref APIで同等のcommit単位を維持する。認証を推測したcloneやforce pushは行わない。

以下のcommandsはrepository rootから実行する。CMakeが利用できる標準経路:

```bash
cmake -S src/lookup_reuse -B build/lookup-reuse -DCMAKE_BUILD_TYPE=Release
cmake --build build/lookup-reuse --config Release
ctest --test-dir build/lookup-reuse -C Release --output-on-failure
```

現scratchにはGCC 13.3.0があるがCMakeはない。ダウンロードできない環境では、各taskのRED/GREENを次の直接buildで検証する（初出済みsourceだけを明示してもよい）。CMake検証はCIで別途確認し、未確認なら完了報告に残す。

```bash
mkdir -p build/lookup-reuse
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests src/lookup_reuse/core/*.cpp src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests
build/lookup-reuse/lookup_reuse_tests
```

## Task 1: 所有tableと通常の正の検索

**Files:** File mapのTableView、TestSupport、TestMain、TableViewTests、CMakeListsを作成。

**Interfaces (namespace `lookup_reuse`):**

- `TableIdentity { uint64_t map_id, storage_id, lifetime_epoch; uint32_t layout_version; }`、`SlotRecord { uint8_t control; uint32_t key; }`。
- `using SearchResult = std::optional<size_t>;`。nulloptは `NoPositiveResult`。返されたindexはdescriptor pointerではない。
- `enum class ViewError { UnsupportedLayout, InvalidMask, SizeOverflow, TruncatedSpan, InvalidControl, DuplicateKey, UnreachableKey };`。
- `OwnedTableFixture::Create(TableIdentity, uint64_t mask, uint64_t slot_count, std::span<const std::byte>) -> std::variant<std::unique_ptr<OwnedTableFixture>, ViewError>`。
- fixtureはcopy/move不可、bytesをprivateにcopy所有し構築後変更不可。`const ValidatedTableView& OwnedTableFixture::View() const noexcept`。viewもcopy/move不可、constructorはprivateでfixtureだけが作成できる。ownerの生存期間内だけ借用する。
- view: `Identity() -> TableIdentity`, `Mask() -> uint64_t`, `PrimaryCount() -> size_t`, `SlotCount() -> size_t`, `Slot(size_t) -> std::optional<SlotRecord>`、全てconst noexcept。範囲外Slotはnullopt。raw bytesの可変参照は公開しない。
- `HashKey(uint32_t) noexcept -> uint32_t`、`ReferencePositiveSearch(const ValidatedTableView&, uint32_t) noexcept -> SearchResult`。
- test support: `RegisterTest(const char* name, void (*test)()) -> void` と `CHECK(bool)`、`RawSlots(size_t) -> std::vector<std::byte>`、`PutSlot(vector<byte>&, size_t, uint8_t control, uint32_t key) -> void`、`MakeFixture(TableIdentity,uint64_t mask,const vector<byte>&) -> unique_ptr<OwnedTableFixture>`（invalidならtest failure）。これらはtest専用。

- [x] **Step 1: TableViewTestsにfailing testsを書く。** 下の固定配置をそのまま使う。raw bytesの生成はPutSlotで指定値を置くだけとし、reference/hashで期待slotを生成しない。

```cpp
// mask=7, slots=10; control is home-distance + 1
PutSlot(raw, 5, 1, 0); PutSlot(raw, 6, 2, 8);
CHECK(ReferencePositiveSearch(fixture->View(), 0) == SearchResult{5});
CHECK(ReferencePositiveSearch(fixture->View(), 8) == SearchResult{6});
CHECK(!ReferencePositiveSearch(fixture->View(), 16));
// test: tail_positive_never_cached (Task 1: search portion)
PutSlot(tail_raw, 7, 1, 2); PutSlot(tail_raw, 8, 2, 10);
CHECK(ReferencePositiveSearch(tail_fixture->View(), 10) == SearchResult{8});
// test: one_primary_and_max_key; mask=0, slots=2, slot0=(1, UINT32_MAX)
CHECK(ReferencePositiveSearch(one->View(), UINT32_MAX) == SearchResult{0});
CHECK(!ReferencePositiveSearch(one->View(), 0));
```

さらに名前付きtests `invalid_layout_mask_size`（version=2、mask=6、mask=UINT64_MAX、slot_count=UINT64_MAX、39-byte recordを拒否）、`invalid_duplicate_distance_reachability`（同じfull key二重、key0@slot6/control1、key8@slot6/control2でslot5 emptyを拒否）、`control_distance_overflow`（mask0でhome0からindex255にkeyを配置したcontrol255を拒否）、`borrow_is_immutable`（元span変更後もowned copyが不変、fixture/viewがcopy/move不可のstatic_assert）を追加する。mask0でslots1がoccupiedの入力は末尾emptyが欠けるtruncated tailとして拒否する。

- [x] **Step 2: 直接GCC buildを実行してREDを確認する。** Expected: TableView APIが未定義でcompile非0。TestMain/TestSupport/CMake scaffoldingを用意した後は、宣言だけのstubがtyped error/nulloptを返す状態で `--filter one_primary_and_max_key` がCHECK failureになることも確認する。失敗が環境依存だけならREDと扱わない。
- [x] **Step 3: 上記APIをTableView.h/.cppへ実装する。** FNVは初期値 `0x811c9dc5`、multiplier `0x01000193`、keyの4-byte little-endian、uint32 wrap。mask+1、slot_count×40をchecked算術してcopy前にサイズ検査する。各occupied keyのhome、非wrap距離+1とcontrolを照合し、独立した逐次検証で通常検索の停止条件より前に到達可能か調べる。full keyの一意性、primary数以上のspan、全occupied probe後のempty terminatorを検査する。validatorが未validated viewを作る循環を避ける。typed errorは上記の列挙順で最初の該当原因を返す。lookupはslot/control/spanを境界検査して停止し、fallbackを再現しない。
- [x] **Step 4: Release buildと全TableView testsを実行する。** Expected: 全PASS、未知filterは非0。CMake使用可能ならCTestもPASS。
- [x] **Step 5: Task 1のfilesをcommitする。** Message: `feat: add owned validated offline lookup tables`。RED/GREEN commandsと実出力を作業記録へ残す。

## Task 2: 1つのpositive-slot hint

**Files:** PositiveSlotHint.h/.cpp、PositiveSlotHintTests.cppを作成。CMakeのsources/tests登録を追加。

**Interfaces:** Task 1のview/SearchResultを消費する。`PositiveSlotHint::Try(const ValidatedTableView&, uint32_t) noexcept -> SearchResult`（nulloptはNeedsOriginal）、`Remember(const ValidatedTableView&, uint32_t, SearchResult) noexcept -> void`、`Clear() noexcept -> void`。保持値はidentity/mask/key/indexとoccupied boolだけ。Tryは通常検索を呼ばない。

- [x] **Step 1: failing hint testsを書く。**

```cpp
// test: repeat_hit_avoids_reference; fixture key0@5, key8@6
CHECK(!hint.Try(view, 8));
hint.Remember(view, 8, SearchResult{6});
CHECK(hint.Try(view, 8) == SearchResult{6});
CHECK(!hint.Try(view, 0));
// test: tail_positive_never_cached
hint.Remember(tail_view, 10, SearchResult{8});
CHECK(!hint.Try(tail_view, 10));
// test: wrong_key_result_not_remembered
hint.Remember(view, 8, SearchResult{5});
CHECK(!hint.Try(view, 8));
```

`identity_and_mask_changes`はmap/storage/epochをそれぞれ変えた新snapshot、mask15の新snapshotでNeedsOriginalを確認する。layout2はview生成失敗をTask1で確認し、hintをClearするcaller経路をTask3で確認する。`backshift_and_slot_reuse`はkey0削除後key8@5/control1へ再配置、別snapshotでslot6に別full keyを置き、旧hintが使われないことと再Remember後の正しいslotを確認する。再生成のtest builderはepochを増やし、mutableなviewを作らない。`full_key_and_uncacheable`は低24bitが同じ別key、nullopt、span外index、empty slot、Clearを確認する。

- [x] **Step 2: buildして `--filter repeat_hit_avoids_reference` をRED確認する。** Expected: Tryが常にnulloptのstubで2つ目のCHECKがFAIL。
- [x] **Step 3: Try/Remember/Clearを実装する。** Tryはidentity/mask/fullkey/primary boundsと現在のSlotのcontrol/keyを確認する。Rememberは先にClearし、元のpositive indexがprimary内かつ現在slotのfull key/control一致の場合だけ保存する。tailを検索できることとhint適格性を混同しない。旧view/bytes/pointerは保存しない。
- [x] **Step 4: Release buildとTableView+hint全testsを実行する。** Expected: 全PASS。4回同じkeyをcore callerがTry→必要時のみReference→Rememberで扱うtestではsearch counter=1、各slot=6。shadow testとは別のtestである。
- [x] **Step 5: Task 2をcommitする。** Message: `feat: validate a single positive lookup slot hint`。

## Task 3: 元結果を維持するoffline shadow observer

**Files:** ShadowComparison.h/.cpp、ShadowComparisonTests.cppを作成。CMake登録追加。

**Interfaces:**

- Task 1/2のview、SearchResult、hintを消費する。
- `enum class ObserverMode { Off, Shadow };`、`enum class ComparisonStatus { NoCandidate, Equal, Mismatch, Skipped };`。
- `enum class SkipReason { None, Off, MissingView, MissingScope, Reentrant, SessionDisabled };`。
- `OriginalLookup { void* context; SearchResult (*invoke)(void*, uint32_t); }`。invokeはnon-nullというAPI前提。std::functionを使わない。
- `ComparisonRecord { ComparisonStatus status; SkipReason reason; SearchResult candidate, original; }`。固定値だけ。
- `ObserverCounters`: uint64の `observed_calls, candidate_attempts, candidate_hits, equal, mismatch, fallback_or_no_positive, reentrant_bypass, dropped_records` とSkipReason別の固定長 `skipped_by_reason`。
- `OfflineShadowEvaluator`: default Off、新instanceだけがsession停止をresetする。`SetMode(ObserverMode) noexcept -> void`、`Evaluate(const ValidatedTableView* nullable_view, uint32_t key, OriginalLookup) -> SearchResult`、`LastRecord() const noexcept -> ComparisonRecord`、`Counters() const noexcept -> const ObserverCounters&`。
- `ObserverScope(OfflineShadowEvaluator&)`はcopy/move不可。constructor/destructorでhintをClearしscopeを開始/終了する。nested scopeは禁止、再入は同じscope内のEvaluate再帰で検証する。Evaluateは1-thread/session、同期callbackのみというoffline契約。

- [x] **Step 1: failing shadow testsを書く。**

```cpp
// test: shadow_original_once_and_return; mode Shadow, active scope, key8
CHECK(eval.Evaluate(&view, 8, original) == SearchResult{6});
CHECK(eval.LastRecord().status == ComparisonStatus::NoCandidate);
CHECK(eval.Evaluate(&view, 8, original) == SearchResult{6});
CHECK(eval.LastRecord().status == ComparisonStatus::Equal);
CHECK(original_calls == 2);
CHECK(eval.Counters().candidate_hits == 1);
// test: mismatch_disables; original changes result to nullopt on third call
CHECK(!eval.Evaluate(&view, 8, changed_original));
CHECK(eval.LastRecord().status == ComparisonStatus::Mismatch);
CHECK(eval.Counters().mismatch == 1);
```

追加tests: `exception_then_next_call`は元callbackの固有exceptionを捕捉し、次回はNoCandidate、callback回数=試行数を確認する。`reentrant_bypasses_and_invalidates_outer`はinnerにも元callback1回、reentrant_bypass=1、inner Skipped/Reentrant、outerは比較せずSkipped/Reentrant、次の呼び出しもNoCandidate。`off_missing_view_scope`はそれぞれ元callback1回とSkippedを確認し、invalid layoutのCreate失敗をnullptr経路へ渡す。`wrong_key_result_not_remembered`は元結果slot5をそのまま返すが次回もNoCandidate。`mode_toggle_keeps_disabled`はmismatch後のOff→ShadowがSkipped/SessionDisabled、hint復活無し。`scope_end_and_miss`は新scopeでNoCandidate、missを毎回元callbackへ渡すことを確認する。

- [x] **Step 2: buildして `--filter shadow_original_once_and_return` をRED確認する。** Expected: callbackだけを呼ぶstubでEqualのCHECKがFAIL。元結果を返さないstubにしない。
- [x] **Step 3: evaluatorとRAII scopeを実装する。** candidateは元callback前に取得し、元callbackをexactly once実行する。例外時はhintとin-call状態をRAIIで消して例外をそのまま伝播する。再入時は内側候補をbypassし、外側に固定boolで失効を通知する。戻ったouterは候補を比較/再保存しない。候補があり比較可能ならEqual/Mismatch、候補無しはNoCandidate、証拠/scope/mode不足はSkipped。正常戻り値は改変しない。mismatch後はそのsessionをdisableし、SetModeでも復帰しない。
- [x] **Step 4: countersのテストを実行する。** observed_callsは例外含む全Evaluate入場、candidate_attemptsはShadow・scope・validview・非再入・未disableのTry実行、candidate_hitsはTry成功、equal/mismatchは比較完了のみ。fallback_or_no_positiveは正常nullopt、skipはreason別、reentrant_bypassはinner入場。例外は正常recordを偽造しない。LastRecordは最後に完了した呼び出しの値であり、outer完了がinner recordを上書きする。fixed recordのみなのでdropped_records=0。全Release testsがPASS、hit数と比較完了数が再入ケースで異なることを確認する。
- [x] **Step 5: Task 3をcommitする。** Message: `feat: compare offline lookup hints without replacing original results`。

## Task 4: 再現可能なdifferential runnerと受け入れ

**Files:** File mapのrunner、OfflineRunnerTests、README群、専用workflow、generated結果/verificationを作成・更新。CMakeにrunnerを追加。

**Interfaces:** Task 1–3を使用。`RunConfig { uint32_t seed = 20261007; size_t rebuilds = 1000; }`、`RunSummary { RunConfig config; uint64_t fixture_count, query_count, core_hits, reference_calls, membership_mismatches, slot_mismatches; ObserverCounters observer; }`。`RunOffline(const RunConfig&) -> RunSummary`、`WriteJson(const RunSummary&, std::ostream&) -> void` をOfflineRunner.h/.cppに置く。coreにはrunner headerをincludeしない。

CLI: `lookup_reuse_runner --seed 20261007 --rebuilds 1000 --output <path>`。unsigned decimal厳密parse、overflow・負値・unknown option・rebuilds=0を拒否して非0。mismatch>0も非0、I/O failure非0。stdoutを使う場合だけoutputを省略可。

- [x] **Step 1: OfflineRunnerTestsへfailing testsを書く。**

```cpp
// test: repeatable_and_independent_membership
auto a = RunOffline(RunConfig{20261007, 1000});
auto b = RunOffline(RunConfig{20261007, 1000});
CHECK(a.query_count == b.query_count);
CHECK(a.membership_mismatches == 0);
CHECK(a.slot_mismatches == 0);
CHECK(a.core_hits > 0);
CHECK(a.observer.observed_calls > 0);
CHECK(a.observer.dropped_records == 0);
```

`json_roundtrip_and_cli_rejection`は生成JSONをPython標準jsonで読み、schema_version=1、seed=20261007、rebuilds=1000、全required counts、`scope="offline-synthetic"` を確認する。CLIの `--seed -1`、`--seed 4294967296`、`--rebuilds 0`、unknown option、書けないoutputを非0で確認する（CTestがPython interpreterを見つけた場合のみこのCLI検査を登録し、無い場合は明示skip）。`boundary_fixtures_independent_of_seed`はTask1/2のtail/backshift/max-keyを固定して通常検索・hint・shadowで検証する。

- [x] **Step 2: runner stubで `--filter repeatable_and_independent_membership` をRED確認する。** Expected: core_hits=0のCHECKがFAIL。
- [x] **Step 3: runnerを実装する。** std::mt19937の生出力と明示したmodulo選択を使い、実装依存のuniform_int_distributionによるfixture差を避ける。mask7/15/31を巡回し、1–16個のunique full uint32 keysを独立std::setに保持する。runner専用のRobin-Hood insertionがraw recordsを作り、validatorへ渡す。通常検索/validatorを使って期待存在集合を生成しない。probe用tailはoccupied後のemptyを含むだけ確保する。fixture再生成ごとにopaque storage_id/epochを増やす。present/absent queryと4回同key queryを生成し、referenceの存在判定を独立setへ、coreのslotをreferenceへ比較する。shadowは同fixtureを読む元callbackを毎回呼ぶ。old Python sourceはimport/移植しない。結果のquery数は実測した生成数を保存し、旧モデルの25,676に合わせない。
- [x] **Step 4: JSON出力とCLIを実装し、fixed runを生成する。** JSONはschema/config/countsとoffline適用範囲を含み、Skipped理由別数を出す。serializer/stream/動的fixture構築はrunnerのみ。証拠のverification.mdへ実compiler・OS・commands・exitcode・fixture/query数・skipとgit基準を書き、未実行をPASS扱いしない。

```bash
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/*.cpp -o build/lookup-reuse/lookup_reuse_runner
build/lookup-reuse/lookup_reuse_runner --seed 20261007 --rebuilds 1000 --output research/generated/lookup-reuse-core/results.json
python -m json.tool research/generated/lookup-reuse-core/results.json
```

- [x] **Step 5: 専用CIとbuild/readmeを完成する。** workflowはubuntu-24.04/windows-2022 matrix、既存と同じactions/checkout@v4を使い、Release configure/build/CTestとfixed runnerを実行する。Windows executable pathは `build/lookup-reuse/Release/`、Linuxは `build/lookup-reuse/`。core test用CMakeへPythonが見つかった時だけJSON/CLI CTestを登録する。この検査のため `src/lookup_reuse/tests/VerifyRunner.py`（Python stdlibのみ、引数はrunner executable path）を追加する。READMEはGCC/MSVC commands、ownership/scoping、mode、合成結果の限界を説明し、段階Bの未達条件をspecへリンクする。
- [x] **Step 6: 最終verificationを実行する。** Task4以降の直接test buildは前掲GCC commandへ `-Isrc/lookup_reuse/runner src/lookup_reuse/runner/OfflineRunner.cpp` を追加してlinkし、`python src/lookup_reuse/tests/VerifyRunner.py build/lookup-reuse/lookup_reuse_runner` を実行する。Release core全tests、runner、JSON/CLI検査、`python -m unittest discover -s tests -v`。CIでGCC/MSVC双方の結果を確認できた場合のみ双方PASSと書く。CMake無しなら直接GCC結果とCI未確認を区別する。必要dependency不足による既存Python test skip/failureは件数と原因を残す。V3PF goldenが変わっていないことをgit diffで確認する。
- [x] **Step 7: 最終handoffをcommitする。** Message: `feat: add reproducible offline lookup reuse verification`。requesting-code-reviewとverification-before-completionを適用し、承認済みNative方式の最終reviewを行う。finishing-a-development-branchで統合方法を判断する。段階Aの完了、実際のtests、native未達条件を報告する。速度改善率やgame内の安全性はこの合成結果から主張しない。

## Self-reviewとhandoff

- spec §1–4/11: Scope、File map、Task4のhandoffに対応。native条件の実装は含めない。
- spec §5: Task1のownership・型・bounds・unique/control/reachability検証。§6: Task2の適格性と消去。
- spec §7/9: Task3の元callback/例外/再入/比較とcounts、Task4の独立JSON。native-only lifetime/sidecar/停止条件は段階Bへ留保する。
- spec §10: Task1–3の固定boundaryとTask4の独立set/fixed-seed、Release/Python/CI検証。
- Review Focusの5件は各owner taskの名前付きtestへ割り当て済み。新しいviewやhintが旧owner pointerを保持しないことをreviewする。
- API型はSearchResult=optional slotで統一し、callback戻り値とcandidateを別に記録する。mode切替によるsession disable解除は認めない。
- 実装時にspec契約を満たせないことが判明したら、native前提を追加せず、具体的な矛盾と選択肢を提示する。

本計画は段階Aとして実装済み。実際に実行したcommandsと結果は[verification.md](../../../research/generated/lookup-reuse-core/verification.md)に記録した。合成結果は速度改善やnative等価性の証拠ではない。
