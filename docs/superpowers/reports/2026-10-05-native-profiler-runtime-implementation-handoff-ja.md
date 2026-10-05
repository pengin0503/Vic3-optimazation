# Read-only native profiler implementation handoff

## 範囲

既存ブランチ `claude/vic3-native-profiler-tasks-suugii`、checkpoint `9def074` から
runtime 計画 Task 3–8 を実装。開始時 main `7f2c577` は checkpoint の祖先で behind=0。
Task 1 `7dcf8b5` / Task 2 `9def074` を再実装していない。

- Task 3: BCrypt SHA-256、checked PE32+/AMD64 metadata、readable/executable `.text` scan、一意 match、vtable slot 6。
- Task 4: V3PF v1 explicit serialization、960-byte Python golden 完全一致、64×1024 固定 SPSC pool、writer thread 専用 I/O。
- Task 5: versioned shared config、loader lock 外の initialize/flush、disabled/no-hook、ready/stop/stopped events。
- Task 6: 3 tail anchors、original exactly once、引数保持、通常 return 後の End、drop/exhaustion 時の継続、MinHook backend。
- Task 7: explicit PID、Victoria filename/architecture/on-disk hash gate、LoadLibraryW path だけ remote write、ready handshake。
- Task 8: Ubuntu Python job 維持、windows-2022 x64 Release build/CTest/codegen/parser compatibility、operator guide。

## 検証の区別

Linux で Python 全 142 tests、target generation --check、diff --check を実施。
Linux g++ で platform-independent resolver/format/buffer/config/hook/CLI tests を実施。
Windows 専用 BCrypt、module page checks、DLL lifecycle、real MinHook fixture、helper process injection は
Windows CI で確認する。実行履歴 URL と結果は、この報告の末尾に追記する。
実ゲームの測定は未実施。Task 9 完了や性能改善を意味しない。

## 設計上の判断

- Task 2 scaffold の static CRT は DisableThreadLibraryCalls と不整合のため shared CRT に変更。
  Visual C++ x64 runtime の依存を operator guide に明記。
- Linux core test を補助検証として実行し、Windows test の代替としては数えない。
- remote LoadLibrary thread timeout は path を解放せずプロセス終了まで残す。未完の読み込みを
  壊さず、retry/fallback はしない。
- stop では hooks を disable し、実行中 detour の通常 return を control thread が最大 30 秒待つ。
  game thread は待たせない。trampoline と backing pool は process lifetime 保持し、DLL を unload しない。
- partial validation は explicit option のみ。unsupported global build は必ず 0 hooks。

## 未検証

実ゲーム 1.14.5 での独立 hash/PE/signature/vtable 検証、全 3 hook の経路、trace pairing、
built-in CSV との相関、12/16 threads の observer overhead、長時間実行・セーブ確認。
手順: [Windows 実ゲーム検証](../guides/2026-10-05-native-profiler-runtime-validation-ja.md)。

Task 8 で停止。scheduler/worker count/cadence/lock/計算省略/forced parallelization の変更、
Task 10 以降、Task 11/12 の最適化パッチは未実装。
