# Loader保留項目のオフライン完了計画

> **For agentic workers:** Use superpowers:executing-plans. Native実行、実装subagentは使わない。ユーザーはオフライン保留作業の完了を指定済み。

**Goal:** PR #18で保留した追加coverageとWindows Python fixture問題を解決する。

**Architecture:** 接続方式や安全gateは変えない。追加メモリ属性queryだけを小さなread-only関数へ抽出し、実API失敗/成功を検証する。Pure helperは成功時に自分のstage/errorを更新する。Pythonはテスト用path表現とリンク能力の前提を修正し、実際の否定検証を維持する。

**Tech Stack:** C++20 / Windows x64 / CTest / Python unittest

**Spec:** 前回の `2026-10-12-loader-readonly-byte-mismatch-design.md` とこの計画の以下の契約。最新mainは再fetch時も `321064d`、既存成果を含むPR #18 head `b4b7365` から継続する。

## 契約と制約

- `ObserveRemoteBranchRegion(HANDLE, ModuleResolutionDiagnostics&)` はByteMismatch+完全probe+Rel32Jumpの場合だけVirtualQueryEx。query関連の古い値を毎回clearし、stage/win32_error/byte証拠を変更しない。追加観測から接続を許可しない。
- `WriteModuleResolutionDiagnostics` のdecimal出力と元stream flags保持をテストする。既存実装が既に正しければテストだけ追加する。
- 各pure validation helperは成功時 `stage=None, win32_error=0` を記録する。拒否値・比較・bounds条件は維持し、呼出側が前段拒否後に進むことは許可しない。
- Windowsのfixtureにdrive colonを含む偽directoryを作らず、実際のabsolute/drive-relative/backslash拒否は全OSで実行する。JSONの相対pathはPOSIX文字列で統一する。
- linkなしでも通常pathの拒否検証は実行する。実hardlink/symlink作成に必要な能力だけが欠ける場合は、その独立testを理由付きskipとし、Linux CIで実行する。権限やsecurity設定を変更しない。
- byte hashを固定したgolden filesは改行変換を抑止する。既存hash/source blobは変更しない。
- 実ゲーム操作なし。CIは全修正・ローカル検証・review後の1 pushだけ。

## Review Focus

- query失敗が元の拒否を維持し、前回成功の属性を出さない。
- query不要のstage/entryを追加観測してしまわない。
- successful helperが古いAPI errorを残さず、拒否条件を弱めない。
- Windows fixture修正がsecurity否定テストをskipするだけの対応にならない。
- golden fileの改行対策が既存hashを変更しない。

### Task 1: Native診断の保留coverage

**Files:** Injector.h/cpp、ModuleResolutionPolicy.h/cpp、InjectorTests.cpp、ModuleResolutionTests.cpp。

**Interfaces:** `ObserveRemoteBranchRegion(HANDLE,ModuleResolutionDiagnostics&) -> void`。各helperの既存signatureは保持。

- [x] 欠けている観測関数のtestを追加し、未実装REDを確認。
- [x] 既存queryを抽出し、実invalid handle、成功→失敗→成功、query不要条件の保持をGREEN。
- [x] hex設定streamからdecimal出力・flags復元を追加検証。既存実装が通ることを確認。
- [x] 各pure helperの拒否後成功で古いstage/errorが残るREDを確認し、成功結果をclearしてGREEN。
- [x] 全Windows x64 CTestを実行してcommit。

### Task 2: Windows Python fixture

**Files:** tests/test_check_cpu_runtime_gate.py、.gitattributes。

**Interfaces:** production CPU runtime gateのsignature/判定は変更しない。test artifact pathのPOSIX表現を維持。

- [x] 前回の5 methods / 6 errorsを現在checkoutで再現。
- [x] link検証を独立化し、能力不足時のみ明示skip。通常path検証は必ず実行。
- [x] Windowsで不可能なshadow directory作成を抑止し、malicious manifestの拒否を検証。
- [x] header-only fixtureのmanifest検索pathをPOSIXに修正。
- [x] golden改行変換を.gitattributesで抑止、git blobの元bytesと既存hashを検証。
- [x] 修正対象と全Python suiteをローカル実行し、skip理由を記録してcommit。

### Task 3: 報告・PR更新・最終確認

**Files:** 日本語followup report、validation.json、guide/READMEへの導線、ローカル配布package。

- [x] 検証済みsource/binary/log hash、新旧結果、残runtime境界を保存。
- [x] 全branchの独立read-only review、重大指摘のTDD修正。
- [ ] PR #18へまとめてpushし、最終CIを1回確認。結果はPR本文へ記録し不要な再CIを避ける（外部状態のsource of truthはPR本文/checks）。
- [ ] local packageを新binary/provenanceへ更新し、CRC/内容を検証。
