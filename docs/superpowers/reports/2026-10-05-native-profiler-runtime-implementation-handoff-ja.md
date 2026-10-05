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

Linux で添付の `Vic3_data` archive を `VIC3_DATA` に指定して Python 142/142 tests 成功（skip なし）。
`python tools/render_native_profiler_targets.py --check`、`git diff --check` および checkpoint からの全差分 check 成功。
Linux g++ で platform-independent resolver/format/buffer/config/hook/CLI tests を実施。
Windows 専用 BCrypt、module page checks、DLL lifecycle、real MinHook fixture、helper process injection を
実際の `windows-2022` GitHub Actions で確認済み。Linux の結果から推測していない。
[成功 run 37388845680](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37388845680)
（commit `5cbea38561f8ec593d7dfd6a47767e348c544688`）で Ubuntu Python / Windows native とも成功。

Windows 実行コマンド:

```text
cmake -S src/native -B build/native -A x64
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
```

CTest は 8/8 成功。ターゲット include 再生成チェック、runtime/hook の V3PF を既存 Python parser で読む
互換性テスト、および parser CLI の JSON 出力も成功。EXE/DLL/trace/JSON/CTest log を CI artifact に保存。
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
- 計画中の parser CLI コマンドには既存の必須 `--output` がなかったため、CI/guide に JSON 出力先を追加。
  parser の interface は変更していない。

## 未検証

実ゲーム 1.14.5 での独立 hash/PE/signature/vtable 検証、全 3 hook の経路、trace pairing、
built-in CSV との相関、12/16 threads の observer overhead、長時間実行・セーブ確認。
手順: [Windows 実ゲーム検証](../guides/2026-10-05-native-profiler-runtime-validation-ja.md)。

Task 8 で停止。scheduler/worker count/cadence/lock/計算省略/forced parallelization の変更、
Task 10 以降、Task 11/12 の最適化パッチは未実装。

## 最終レビューと RED → GREEN

独立した最終コードレビューは Critical 0 / Important 2 / Minor 0。Important 2 件を修正し、
Windows 上の回帰テストで確認した。

1. `Stopped` event の通知だけで成功と判定していた loader stop を修正。
   shared mapping を保持し、terminal status が `Stopped` の場合だけ成功とする。
   `StopFailed` / `TraceFailed` を実際の Windows named IPC で試験済み。
2. `noexcept` 初期化中の `ObjectName` allocation / `ReadSharedConfig` allocation failure が
   game process を terminate し得た経路を修正。すべての runtime setup を catch 境界内へ移し、
   helper の例外を caller へ伝播する。fault injection は test binary のみに存在する。
   [RED run 37388243445](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37388243445)
   で NativeRuntimeTests の異常終了 `0xc0000409` を再現し、
   [GREEN run 37388585872](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37388585872)
   で CTest 8/8 を確認。

Windows checkout の generated include CRLF による `--check` failure は `.gitattributes` の `eol=lf` で修正。
GREEN run 37388585872 の最終 parser CLI failure は必須 `--output` の不足が原因で、
出力先を指定した run 37388845680 で workflow 全体が成功した。

## ブランチへ push 済みの commit

| Task | Commit | 内容 |
|---|---|---|
| 3 | `dc4c8ca01b71a610862f80e57d6adee9a8ed5f81` | fail-closed target resolution |
| 4 | `0d6dbefcfb1f24442043611fea2115414a330f93` | V3PF writer / fixed buffers |
| 5 | `ac08d186d78f8bbb335f9bdab26ebbb7ca51bd84` | DLL lifecycle / disabled mode |
| 6 | `620bb405530bf514b71c0921f4c7ee59acf82c83` | 3 observation-only tail anchors |
| 7 | `0ba8f122f54596e5189f516a6fd546888253f96b` | exact-build explicit PID loader |
| 8 | `fe3e19a921c4de7aad4fa748dcb1ce2aff1b3808` | Windows CI / operator documentation |

追加の回帰・修正 commit:

- `4533024f81c242bbda841498f6119ad442940b65`: initialization allocation failure RED test。
- `372e950329cb9fee0b2e04fc2a9250e04214f2b4`: generated include の Windows LF 保持。
- `3623d15179a9a6355d92d724b6f4a0671a39f27d`: stop status / initialization catch 修正。
- `5cbea38561f8ec593d7dfd6a47767e348c544688`: parser CLI の必須出力先指定。

## 次の実ゲーム検証

1. exact Windows 1.14.5 で disabled/no-hook mode を実行し、hash/PE/signature/vtable と lifecycle を確認。
2. 3 targets だけを有効化し、ABI、original exactly once、通常 return、stop 中の active call を確認。
3. trace の Begin/End pairing、drop count と built-in CSV の相関を確認。
   tail-anchor duration は TickTask 全体時間ではなく、残りの tail execution 区間として扱う。
4. 同じ workload で未 attach / disabled / enabled を比較し、12/16 threads の observer overhead を測定。
5. 長時間実行、ロード/セーブ、例外・unwinding、ゲーム状態の一致を確認する。

これらは未検証のため、実ゲームでの安全性・測定妥当性・性能改善を認定していない。
