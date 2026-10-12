# Victoria 3 1.14.5 — 追加ゲーム内測定なしの CPU 最適化研究設計

Date: 2026-10-11
Parent design: [2026-10-04 native performance optimization](2026-10-04-native-performance-optimization-design.md)
Target repository: `pengin0503/Vic3-optimazation`

## Objective and boundary

新規ゲーム内計測なしで、既存の exact-build 静的解析・保存済み計測証拠とオフライン fixture を利用し、CPU 並列化の可能性を判断するための証拠・検証基盤を改善する。成功条件は **次に調査すべき命令と残る検証条件を再現可能に提示すること** であり、CPU 使用率の上昇や実ゲーム高速化は成功条件に含めない。

対象 Victoria 3 Windows 1.14.5、`victoria3.exe` SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。対象が異なる場合は fail-closed。承認済みゲーム内容・セーブ・更新頻度を変更しない方針を維持する。

Baseline: 2026-10-05 の 9 本の実測における 8/12/16 task threads の平均 wall time は 37.043/34.517/34.777 秒。16 で使用率が増えても速度は伸びていない。スレッドを増やすだけの対策を採用しない。

## Non-goals

- 実ゲームのシミュレーション計算、同期、スケジューラ、フレーム進行、メモリ領域を変更するパッチの実装・配布・有効化。
- 静的 call graph、サンプル数、合成実験の結果を runtime critical path、lock contention、FPS、最適化倍率として表記。
- 既存の Stage A/B0 shadow、native profiler、OS normalizer、GPU offload spike を新規に作り直す。
- CI 用 GitHub Actions を通常の開発途中に多用すること。ローカル検証優先、最終確認だけCI利用候補とする。

## Workstreams and interfaces

### 1. TickTask 依存の静的証拠を強化

既存 `research/generated/ticktask-dependencies-1.14.5.json` (`format_version=1`) を入力する読み取り専用トリアージを追加する。追加コードは元の `map_ticktask_dependencies.py` の出力構造を変更しない。関数の `ranges` に命令RVAが含まれるときだけ既知関数に帰属させる。未解決理由、original RVA、原本 hash、担当関数の有無を記録する。直接call/共有helper/RIP参照から TickTask parent-child edge を捏造しない。再現可能な JSON を作る。後続の深い追跡では machine-code dataflow が得られたときだけ構造関係を再評価する。

### 2. スケジューラ・CPU アルゴリズムの synthetic probe

既存の worker/range runner/heuristic 調査を入力に、独立した所有データでワーク分割・同期方式の実験を設計する。モデルの task weights、dependencies、mutations は合成条件であることをすべての出力に残す。仕事量が不均衡な case、serial bottleneck、barrier overhead、worker overhead を分離して比較する。ゲーム処理の分割可能性や速度向上を主張しない。

### 3. ネイティブ観測と lookup shadow のオフライン接続検証

既存 `src/native/` の synthetic Windows host と `src/lookup_reuse_contract/` を再利用。loader error stage、target match拒否、元 callback exactly once、再入、opaque return、buffer drop、stop を既存テストと重複しない不足caseに限定して拡張。ゲームの live pointer を新たに読み取るAPIは設けない。Windows x64 のみの統合試験が未実行なら未検証のまま記録する。

### 4. 実測受け入れ前の証拠 gate

オフライン証拠の provenance、source build、target、missing windows runtime/profiler/wait evidence、仮説と反証条件を追跡する。新規実測が得られた際に 12/16 matched boundary、observer overhead、Running/Ready/Waiting、game-save checksum を追跡できる handoff を作る。未測定欄をゼロとみなさない。

## First increment: structural gap triage

CLI: `python tools/triage_ticktask_unresolved.py INPUT.json --output OUTPUT.json`

Pure interface: `build_triage(document: dict) -> dict`。入力 format version と exact executable hash、`functions` / `unresolved` / `candidate_dependency_edges` の型と RVA / ranges を検証し、異常なら ValueError。JSON の既知 `unresolved` entries を変更せずに保持し、`analysis_category` と `owner_function_rva` (または null) を付加する。

Categories:
- `indirect_dispatch`: `indirect_call_or_jump`
- `metadata_or_decode`: `no_unwind_metadata`, `incomplete_decode`
- `bounded_expansion`: `depth_budget`, `function_budget`, `byte_budget`
- `identity`: `ambiguous_ticktask_identity`, `unmapped_ticktask_identity`
- `structural_dataflow`: `parent_child_dataflow_not_reconstructed`
- `other`: unknown reason (元の文字列を必ず保存)

Owner は検証済みの半開 `[begin_rva,end_rva)` 範囲を含む場合だけ出力。重複 owner は未知扱いとし、`ownership_ambiguous` を明示。範囲外の RVA や単なる E8 target を勝手に関数へ割り当てない。元 `candidate_dependency_edges` は結果を作るために利用せず、`input_dependency_edges` 件数をレポートする。全 `work_items` に `runtime_verified: false` を明記する。順位は reason による **研究作業分類のみ**。runtime 費用や CPU 使用率の順位ではない。

## Verification and safety gates

- TDD: missing function に対する失敗試験 → 実装 → focused suite → existing Python tests when accessible.
- 空配列、malformed JSON、wrong version/hash、無効RVA、overlap/duplicate owner、unknown reason を回帰検証。
- same input → byte-identical `json.dumps(..., sort_keys=True, indent=2)`、出力先だけ変更し原本は上書きしない。
- local synthetic test pass と exact-exe/native game validation は区別して報告する。
- 次段階の game patch は Task 9 profiler attach/overhead/OS critical-path evidence と semantic proof が揃うまで禁止。

## Source of truth

- `research/ticktask-dependency-static-map.md` (41 groups, 0 confirmed edges, unresolved list)
- `research/deep-scheduler-synchronization-2026-10-05-ja.md` (同期経路の分類)
- `docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md`
- `docs/superpowers/reports/2026-10-07-native-shadow-preparation-ja.md`
- `src/README.md` と `research/os-sampled-capture-2026-10-05-ja.md`

Status: first increment implementation scoped; remaining workstreams retain their own evidence gates. No performance change authorized.

## Phase 4 offline handoff status

[証拠gate実装・監査記録](../reports/2026-10-12-cpu-runtime-evidence-gate-ja.md)と[次回実測手順](../guides/2026-10-12-phase4-runtime-evidence-handoff-ja.md)を追加した。オフライン準備は完了、実ゲームruntime acceptanceは未達。追加測定を行わず、未知のoverhead・同期OS states・save stabilityを成功扱いしない。
