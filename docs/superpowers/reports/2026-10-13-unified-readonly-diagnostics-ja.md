# 診断結果と接続policyの分離・固定手順

2026-10-13 JST。開始時main: `b8cfa3d293edfdc48d5079e1dba45ec334e2c0a3`。ユーザーは診断結果の分離、固定手順、原因追跡の設計を承認し、ローカル検証・最終CI・main mergeまでを指示した。サブエージェントは使用していない。

## 原因と変更

同じexact exe/Loaderを使ったPID14956と24516の保存済みcontext/logを照合。両方で同じ16-byte差分、first_mismatch0、mismatch_count5、byte_mismatchを確認。identity/FILETIMEは一致した。API読取は成功しており、Git index欠落やPowerShellの起動時刻gateとは別の問題である。今回のログには最初の行先のMEM_PRIVATE/RWX属性までがあり、過去PIDのSteam所属証拠を今回の原因証明へ流用しない。

旧native APIは診断収集の成否と入口比較結果を同じboolで返していた。`LoadLibraryDiagnosis {complete,entry_matches}` を導入し、完全な不一致診断はcomplete=true / entry_matches=falseにする。CLIは収集完了時exit0、不完全時exit8と、独立したdiagnosis/entry/connection結果を出す。接続primitiveの16-byte比較と不一致時のallocation/write/thread前拒否は保持した。

診断だけに有限のread-only E9追跡を追加。最大4行先、循環/overflow/未知命令/領域bounds/API失敗で停止する。一意のmodule snapshotに含まれる場合だけ所属pathを記録し、観測を信頼認定や実行候補へ昇格しない。古いchain/query結果をclearし、primary stage/error/byteを保持する。

main内の固定入口 `tools/Invoke-Vic3Diagnostics.ps1` と[現在のガイド](../../guides/vic3-diagnostics-ja.md)へ手順を統一。commit専用build、非空の全CTest、Loader hashのprovenance、catalogのexe hash、process identity、attempt重複拒否、GUIDごとの証拠保存を一緒に検証する。日時付き配布パス・固定Loader hash・script開始時刻gateは現在の操作手順から除去した。元のclone、LFS、既存build、測定証拠は保護して別cloneで実装した。

## 検証

変更前のWindows x64 CTestは10/10。未実装の分類/decoder/結果型を呼ぶ回帰テストを追加し、期待どおりのcompile REDを確認。その後GREEN。PowerShell moduleの未存在RED後、Windows PowerShell5.1でworkflowの結果整合・FILETIME精度・process instance・source/provenance/binary改変・ゼロtest拒否を検証した。

Windows adapterは所有するchild/selfのfixtureだけで、入口一致/変更、read-only handle、module所属、private E9 chain、cycle、hop budget、NOACCESS、invalid handle、stale resetを検証。既存のinjectorテストではmodified entryが接続拒否となりInjectionProbeが実行されないことを保持した。実ゲームへの新しい診断、注入、attach、stop、enabled計測は今回実行していない。

最終ローカル検証とCIの詳細はPR本文/checksと保存したvalidationをsource of truthにする。結果保存のためだけの追加pushでCIを再起動しない。

最終ローカル検証: Windows x64 Release CTest **11/11**（PowerShell workflowを追加）、Windows PowerShell5.1のworkflow **14 cases**、Python **257 tests / errors=0 / failures=0 / skipped=3**、generated include照合、diff check成功。skipはVIC3_DATA未指定のintegration2件とWindows symlink権限不足1件。通常path・hardlink・外部証拠保護は実行済み。

初回Python suiteはcapstone未導入でerrors11 / skipped17。そのログを保全し、pinされたcapstone5.0.7を作業用dependency folderへ導入して上記の結果を再検証した。新しいPowerShellテストはCTest起動時に標準Utility functionを見つけられない失敗を検出し、呼出スクリプトとmoduleの標準依存を明示して修正した。これらの失敗をCIへ持ち込まずローカルで解決した。

## 未解決

第三者detourがある実ゲームへの安全な接続方式は未確立。今回の修正は診断の契約・再現性・手順分散を解決し、接続拒否原因の追加観測を可能にする。byte_mismatchそのものを消したりIssue #17の接続問題を解消したりしたとは扱わず、Issue #17はopenのままにする。実ゲーム接続・Phase4・CPU高速化は未確認。
