# External CPU Route Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 既存の外部CPU計測経路を整え、次の作業をWindowsでの実測にする。

**Architecture:** 製品コードを変更せず、既存WPR profileとbenchmark/OS解析を再利用する。実測templateとrunbookを用意し、native profilerのacceptanceを独立して残す。

**Tech Stack:** Python標準ライブラリ、既存CLI、WPR/WPA、PowerShell操作例。

**Spec:** `docs/superpowers/specs/2026-10-13-external-cpu-route-design.md`

## Global Constraints

- Victoria 3 Windows 1.14.5、TaskThreadCount=12、1911-03-01→1911-06-01。
- 通常実行Bを3回、CPUサンプリングSを3回。順序はB1,S1,S2,B2,B3,S3。
- 実時間・collector overhead・現在設定は未測定/nullとし、旧値を転記しない。
- native/B0/Phase4の製品コード・判定条件・証拠は変更しない。
- 新しい収集器・一般ゲート・GPU実験・性能パッチを追加しない。
- 既存ツールによるひな形生成を実行し、成果をGitHubに保存する。実測前にmainで使えるよう文書のみのPRとして統合する。

## Review Focus

- 実測templateが空欄をvanilla/no MOD/速度5に決めつけないこと。
- marker区間を実ゲームのresume/pause境界やwall timeと誤認しないこと。
- stale CSV、別PID、ASLR base、drop/stack欠落を無視しないこと。
- 別variantのB/Sを混ぜず、quality passを同等性・速度の証明としないこと。
- 失敗・中止で記録を放置せず、別WPR sessionを停止しないこと。

### Task 1: 測定packetと候補の判断材料

**Files:** Create `research/external-cpu/{matrix.json,run-templates/*/*/manifest.template.json,employment-lookup-catalog.json,offline-verification.json,offline-verify-source.py.txt,README.md}` and `docs/superpowers/reports/2026-10-13-external-cpu-candidate-ja.md`.

**Interfaces:** Consumes existing `prepare_benchmark_matrix.create_matrix`, archive and range witnesses. Produces six unmeasured manifests with distinct B/S variants, plus candidate evidence/decision table.

- [x] 既存benchmark/normalizer/correlatorのbaseline testsを実行する。
- [x] 既存generatorでB/S各3件を生成し、実機未確認項目をnullにする。
- [x] 添付のarchive/exe hash、選択したrange bytes、既存catalogのsource hashを確認する。
- [x] 6templateの整合性と、scratchにコピーした合成CSVによるfinalize/quality/analysisを確認する。誤境界CSVの拒否も既存gateで確認する。
- [x] 成果と確認範囲を保存・commitする。

### Task 2: 操作手順と現在の入口

**Files:** Create `docs/guides/vic3-external-cpu-measurement-ja.md`; modify `README.md`, current roadmap, original native design; create completion report.

**Interfaces:** Consumes Task1 packet and existing WPR/OS CLI. Produces executable command blocks and one current entry point.

- [x] preflight、B/S、stop/abort、CSV freshness、manifest確定、提出物、採否を日本語で記す。
- [x] 現在の入口を更新し、旧native profilerが独立してblockedであることを保持する。
- [x] 文書リンク・profile/command/schema整合性を確認し、repository Python suiteを1回実行する。native buildは製品未変更のため再実行しない。
- [x] 全変更を1回だけ独立reviewし、重大指摘を修正する。
- [x] GitHubに保存・統合し、次の実測手順と残る限界を報告する。

これは研究資料・設定の変更であり、製品機能のTDD変更はない。ひな形と操作経路は実際の既存CLIへ合成データを流して確認する。Linuxでの確認をWindows runtime成功と扱わない。
