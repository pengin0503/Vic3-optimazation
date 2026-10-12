# Loader読み取り専用診断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. ユーザー指定によりNativeで実行し、subagent-driven-developmentは使用しない。

**Goal:** APIフックによる拒否を維持し、同じPIDの不一致証拠を注入せず取得する。

**Architecture:** Pure policyが固定長byte比較とE9の観測値を生成する。Windows adapterはidentityと追加queryを収集する。CLIは既存build gate後にread-only診断だけの経路へ分岐する。

**Tech Stack:** C++20 / Windows x64 / CMake / CTest / Python unittest

**Spec:** `docs/superpowers/specs/2026-10-12-loader-readonly-byte-mismatch-design.md`

## Global Constraints

- 16-byte比較・PE/module/protection/build gateを維持し、第三者フックを解除/回避しない。
- 診断modeはquery/readのみ、named IPC・remote allocation/write/thread/stopは行わない。
- 完全読取時のみbyte配列を公開し、診断観測を許可根拠にしない。
- 実ゲーム接続・Phase 4・性能向上は実測なしに成功扱いしない。
- GitHub Actionsは最終確認のみ。途中はローカルTDD。

## Review Focus

- read-only CLIのオプション混在を拒否し、通常attach経路へ流れないこと。
- 部分読取やdiagnostics再利用で古いbyte証拠を出さないこと。
- E9負変位と整数境界でwrapしないこと。
- identityと追加queryが元のAPI error/rejectionを偽装しないこと。
- 同一handle/PID保護と対象外CLI拒否が維持されること。

### Task 1: Pure byte診断

**Files:** `src/native/loader/ModuleResolutionDiagnostics.h`, `ModuleResolutionPolicy.cpp`, `src/native/tests/ModuleResolutionTests.cpp`

**Interfaces:** Consumes `ValidateRemoteExportRead(local,remote,bytes_read,d)`。Produces v3診断、probe_available、固定長byte配列、first_mismatch/mismatch_count、E9観測target。

- [ ] Step 1: ログにlocal/remote bytes、不一致位置、E9行先が必要なテストを先に追加。
- [ ] Step 2: NativeModuleResolutionTestsを実行し、現行ログ不足でFAILを確認。
- [ ] Step 3: 完全読取時の証拠、reset、符号付きE9境界検査、v3書式を実装。
- [ ] Step 4: 全16位置、複数差分、部分読取、reuse、未知形式、整数境界を追加しGREEN。
- [ ] Step 5: 差分検査とcommit。

### Task 2: Windows adapterとCLI

**Files:** `src/native/loader/Injector.h`, `Injector.cpp`, `Main.cpp`, `src/native/tests/InjectorTests.cpp`

**Interfaces:** Consumes Task 1 diagnostics。Produces `DiagnoseLoadLibraryForValidatedProcess(HANDLE,DWORD,ModuleResolutionDiagnostics&) -> bool` とexclusive CLI flag。

- [ ] Step 1: CLI flagのparser受理/混在拒否を先に追加し、FAILを確認。
- [ ] Step 2: exclusive parser、read-only権限/早期分岐、共用resolverを実装してGREEN。
- [ ] Step 3: handle/PID不一致を先にテストし、現行resolverの不足でFAILを確認。
- [ ] Step 4: GetProcessId/GetProcessTimes gate、FILETIME記録、追加queryを実装してGREEN。
- [ ] Step 5: real read-only handleの成功/拒否、対象外CLI、既存synthetic injection/stopを検証。
- [ ] Step 6: Windows Release buildと全CTest、Python suite、generated include check、diff checkを実行してcommit。

### Task 3: 日本語報告と最終確認

**Files:** 日本語reports/guides、既存first-pass guideの導線。

**Interfaces:** Consumes Task 1/2のログ/CLIと検証結果。Produces 次回read-only実ゲーム手順、未解決事項、PR。

- [ ] Step 1: base/変更内容/RED→GREEN/Windows環境/limitationsを保存。
- [ ] Step 2: 新binaryのprovenance/hashと診断だけのコマンドを記載。旧artifact hashを新binaryに適用しない。
- [ ] Step 3: 全branch reviewを依頼し、重大な指摘を修正・検証。
- [ ] Step 4: 新branchをpush、PRを作成。PRの最終CIを一度確認し、結果を保存する。
