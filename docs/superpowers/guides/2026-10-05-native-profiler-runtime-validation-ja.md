# Read-only native profiler: Windows 実ゲーム検証

対象は Victoria 3 Windows **1.14.5**、実行ファイル SHA-256 は
`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54` のみ。
この実装は計測用であり、軽量化パッチではない。Task 10 以降、Task 11/12 は未実装。

## ビルド

Visual Studio 2022 の C++ Desktop workload、CMake 3.25 以上、Python 3 が必要。
実行端末には Visual C++ 2022 x64 runtime が必要（DLL は共有 CRT）。MinHook は
CMake が固定コミットから取得する。DLL/exe は `build/native/Release` に生成される。

```powershell
python tools/render_native_profiler_targets.py --check
cmake -S src/native -B build/native -A x64
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
```

GitHub Actions の `native-profiler-validation` artifact にもテスト済みの DLL/exe と
合成 trace が入る。CRT dependency の判断根拠:
https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-disablethreadlibrarycalls

## 初回は disabled mode

1. Victoria 3 を通常起動し、対象セーブを読み込んで一時停止する。
2. Task Manager の詳細画面で **自分で PID を確認**する。
3. 実行ファイルの hash を保存する。PID/パスは自動選択されない。

```powershell
Get-FileHash '実際のゲームパス\binaries\victoria3.exe' -Algorithm SHA256
.\build\native\Release\Vic3OptimizationLoader.exe --pid 12345 --disabled --output 'C:\Vic3Captures\disabled-01.v3pf'
```

`12345` を確認した PID に、output を実在する書き込み可能なフォルダ内の未使用ファイル名に置換する。
loader の標準出力・標準エラーも保存する。disabled では DLL 独自の hash/PE/signature/vtable
検証と trace 診断を実行し、**hook は 0 本**。対応 build であっても署名不一致は診断に記録される。
未知 build は loader が remote allocation/write/thread の前に拒否し、DLL 側も独立して拒否する。

停止:

```powershell
.\build\native\Release\Vic3OptimizationLoader.exe --stop --pid 12345
```

停止後は DLL、元関数 trampoline、固定バッファをプロセス終了まで保持する。再 attach や
別 capture には **ゲームを再起動**する。stop timeout、hook disable failure、trace I/O failure は
正常終了として扱わず、ログと未完の trace を保存する。inject timeout の場合は、ゲームで
まだ参照され得る DLL-path 領域を解放せず終了する。retry やアドレス fallback は行わない。

## 3 つの observation hook

ゲームを再起動して PID を取り直す。

```powershell
.\build\native\Release\Vic3OptimizationLoader.exe --pid 12346 --targets investment,migration,employment --output 'C:\Vic3Captures\enabled-01.v3pf'
```

対象は HandleAutonomousInvestment、ProcessEconomicMigration、UpdateEmployment の
TickTask tail anchor だけ。ABI は `void(void*, void*)`。引数を変更せず original を 1 回呼ぶ。
通常 return 以外の End は生成せず、例外を捕捉・変換しない。
既定は全指定対象の validation が必要。明示 `--allow-partial-targets` の場合のみ、合格した
対象に限定する。初回の合格判定は全 3 本を要求する。mask は investment=1、migration=2、employment=4。

`.text` 内の一意署名と slot 6 の両方を検証する。 writable section、ambiguous signature、
推測 RVA は使わない。hot hook 内に heap allocation / file I/O / formatting / mutex / blocking wait はない。
64 個 × 1024 slots の固定 pool が満杯の場合は telemetry を drop する。

## Trace 確認

**stop 完了後**に parser を実行する。

```powershell
python tools/parse_native_profiler_trace.py 'C:\Vic3Captures\enabled-01.v3pf' --output 'C:\Vic3Captures\enabled-01-parsed.json' --expected-executable-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54
Get-FileHash 'C:\Vic3Captures\enabled-01.v3pf' -Algorithm SHA256
```

確認する項目:

- header/build IDs/target-table hash が valid、segment が complete。
- enabled mask が 7、各 target の Begin/End が存在する。
- unexplained broken pairs、sequence gaps、negative/cross-thread pairs がない。
- total_dropped_events と Counter に出る buffer exhaustion を記録する。
- 異常 return、overflow、停止途中の未完 End は理由を調査し、成功した計測として無条件に採用しない。

## Observer overhead の実測

診断 baseline は **12 threads**、比較用は **16 threads**。profiler は thread 数を変更しない。
Threading.TaskThreadCount を変更する場合は測定者がゲーム標準 console で設定する。

同じ重いセーブ、同じ camera/UI、同じ 3 か月区間で、各条件に warm-up と 3 回以上の本測定を行う。
ゲーム再起動から同じ初期状態で、disabled / enabled の順序を交互にする。
可能なら vanilla（DLL 未ロード）も対照として保存し、DLL の存在自体の overhead と hook overhead を分ける。

各 run に保存:

| 項目 | 内容 |
| --- | --- |
| identity | run ID、game/save hash、profiler build/commit |
| configuration | PID、12/16 threads、disabled/enabled、指定・有効 target mask |
| workload | start/end 日付、CSV frame min/max/count、(frame,task,calls) fingerprint |
| timing | wall-clock duration、built-in `ticktask_timings.csv` |
| trace | stop 結果、V3PF、SHA-256、drop/exhaustion/parse diagnostics |
| context | camera/UI、speed、warm-up、実施順序、必要なら OS CPU/wait trace |

`tools/check_benchmark_quality.py` で workload_boundary_mismatch がある比較は性能主張に使わない。
既存 `12_r2` の 3-frame 延長を完全一致の対照として扱わない。
**tail-anchor duration は TickTask 全体 inclusive cost ではない**。callbacks/jobs を含む CSV の
ランキング・calls と照合するが、時間やイベント数の 1:1 一致を仮定しない。

## Task 9 の実ゲーム合格条件

1. 非対応実行ファイルへの attach が非ゼロ終了し、remote write / injection を行わない。
2. 対応 1.14.5 で loader と DLL の validation が成功する。
3. 全 3 hook の parseable trace が得られ、説明できない broken pair がない。
4. built-in TickTask counts/timing と native events の関係を説明できる。
5. 同一 workload 境界の反復で enabled-vs-disabled overhead とばらつきを測り、observer overhead が
   ベンチマークで識別できるノイズより小さいことを確認する。
6. ゲーム状態変更がないことをコード確認と長時間実行・セーブ確認で検証する。

合成 CTest/CI の成功だけでは、この合格条件は満たさない。性能改善率はまだ主張できない。

## Attach code 4 の切り分け

`Attach failed (no retry), code 4` は LoadLibraryW の module resolution failure。
`Unsupported process/build ... Gate code: 4` とは別の表示である。
この失敗経路は exact-build gate 通過後、remote allocation/write/thread 作成より前で終了する。

Phase 3診断版 loader は続けて `Module resolution diagnostics v2` を出力する。
`stage` は失敗した条件、`win32_error` は失敗した Win32 API 直後のエラー番号。
比較検証だけの不一致では `win32_error=0` とし、古い GetLastError 値を流用しない。

| stage | 調査対象 |
| --- | --- |
| export_lookup / owner_lookup | local LoadLibraryW export / owner module |
| local_pe / local_address / local_text / local_path | local module PE / export RVA / executable .text / module path |
| snapshot / module_first | explicit PID の module snapshot / enumeration API |
| module_next | module列挙途中のAPI失敗。1件一致が見つかっていても拒否 |
| module_match / module_size / remote_address | owner module path の一意一致 / image size / checked offset |
| remote_query / remote_protection | remote memory query / committed executable-read protection |
| remote_read / byte_mismatch | 16-byte 読み取り / local export bytes との一致 |

`owner_path`、local/remote base・export address・size、export RVA、matches、bytes_read、remote state/protection、
`pe_error` もログへ保存する。code 4 だけで OS バージョンやセキュリティ製品を原因と断定しない。
診断追加で address fallback、retry、validation bypass は行わない。

module列挙は `ERROR_NO_MORE_FILES` の正常終端だけを受理する。remote address検査は
16 bytes全体のimage境界とアドレスoverflowも含める。オフラインで拒否経路が通っても、
以前の実ゲーム `Attach code 4` が解決したとは扱わない。

## ゲーム起動前に可能なPhase 3検証

Windows x64の上記native CTestには `NativeModuleResolutionTests` と
`NativeHookFailureTests`、IPC不在・stop timeout・signaled Pending/Readyを拒否する
拡張 `NativeInjectorTests` が含まれる。[run 38148690363](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363)でx64 Release build・10/10 CTestsと2本のtrace parseが成功した。named IPC、synthetic host注入、DLLのValidationFailed経路とMinHookを確認済み。実ゲームattachや正常に有効化されたDLLセッション全体のstop/finalizeは未検証。

既存 `tests.yml` は共有Windows jobを呼ぶ。`native-validation.yml` の研究branch pushはnative関連pathに限定し、ドキュメント更新では実行しない。手動実行入口も保持する。CI runnerと異なるWindows環境への導入や再現しない障害では、上記configure/build/CTestを対象環境で確認する。

Windowsがない場合のowned fixture検証:

```sh
cmake -S src/native/tests/offline -B build/native-offline
cmake --build build/native-offline --config Release
ctest --test-dir build/native-offline -C Release --output-on-failure
```

64-bit pointersが必要。この入口はWindows API、DLL、MinHook、named IPCや実際の
game attach/stopを検証しない。今回の実行範囲と未検証条件は
[Phase 3記録](../reports/2026-10-11-offline-native-diagnostics-phase3-ja.md)を参照。

## Phase 4 evidence handoff

次回の測定・provenance記録には[Phase 4手順](2026-10-12-phase4-runtime-evidence-handoff-ja.md)を併用する。既存Loader/DLL・Windows synthetic結果を再利用し、実ゲームacceptanceは欠落した実capture・同期CSV/OS・observer overhead・save stabilityが揃うまでblocked。
