# APIフック環境のLoader検討と読み取り専用診断の実装結果

Date: 2026-10-12 JST

**後続更新:** この報告は初回実装時の結果。保留した追加coverageとWindows Python fixtureは[オフラインfollowup](2026-10-12-loader-offline-followup-ja.md)で継続している。新しい結果・binary provenanceはfollowupとPR本文を優先する。

## 結果と範囲

実ゲームへの安全な接続方式を保証する根拠が不足するため、**不一致拒否を維持し、読み取り専用診断を実装した**。16-byte比較の削除、fallback入口への切替、第三者フック解除は行っていない。実ゲーム接続成功、Phase 4完了、CPU高速化は未確認。

Source of truthは開始時にclone/fetchしたmain `321064d479248153585c0e838f8c25836aeae783`。独立cloneの新branch `fix/loader-readonly-byte-mismatch` で作業し、既存成果・ゲーム・Workshop・元MODを保持した。Native / Superpowers systematic-debugging、brainstorming、writing-plans、executing-plans、TDD、verification-before-completionを適用。ユーザーの継続実行指定に従い、skillの追加設計承認待ちは行わなかった。

## 調査と設計

[Issue #17](https://github.com/pengin0503/Vic3-optimazation/issues/17)、[実ゲーム調査](2026-10-12-game-attach-steam-overlay-byte-mismatch-ja.md)、[first-pass guide](../guides/2026-10-12-user-game-validation-first-pass-ja.md)、Injector/ModuleResolutionPolicy/testsを精査した。PID 16352の拒否と、PID 9280のread-onlyジャンプ経路は別証拠であり、同じPIDの連続検証とは扱わない。

現行16-byte gateは、異なるコードを開始アドレスに採用しないための必要な保護。第三者detourを呼ぶ案、別API案、署名/モジュール名を許可する案、独自stub/manual map案を[設計書](../specs/2026-10-12-loader-readonly-byte-mismatch-design.md)で比較した。フック先のABI/内部状態/コード全体/変化競合まで保証できず、推測で接続を許可しない。

Microsoftの[CreateRemoteThread仕様](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createremotethread)は開始アドレスが不正でも作成成功する場合があると説明する。したがってthread作成成功自体を安全性の証拠にできない。今回の「安全根拠不足」は既存証拠と仕様に基づく判断であり、全代替方式が将来も不可能という結論ではない。

## 変更内容

- 診断v3: 両側16-byte hex、不一致の最初のoffset（0-based）/数。完全読取時のみ表示し、部分読取・再利用で古い証拠を出さない。
- handleのPIDと明示PIDを一致検証し、GetProcessTimesの開始FILETIMEを記録。API失敗/不一致は新stage `process_identity` / `process_times` で拒否。
- E9 rel32だけを符号付き/整数境界検査して最初の行先を観測する。VirtualQueryExのstate/protection/type/allocation baseと独立errorを記録。行先は注入候補にせず、元のbyte_mismatchを維持する。
- `--diagnose-loadlibrary --pid PID`: query/read権限だけで既存名前/x64/exe SHA-256 gateを通過し、診断後終了する。DLL選択、named IPC、remote allocation/write/thread、stopへ進まない。exit0は診断の入口一致だけを意味し、attach結果ではない。他のオプションとの混在は拒否する。
- 値が欠けたオプションが診断flagを値として飲み込み、通常attachへ進む不正入力も拒否する。`--`で始まるtokenを値に使わない。ファイル名がその形式なら絶対pathまたは `./` を付けたpathで指定する。
- 実ゲーム手順は[新しい診断ガイド](../guides/2026-10-12-loader-readonly-diagnosis-ja.md)に保存。旧artifact hashを今回のLoaderへ適用しない。

## ローカル検証

環境: Windows 11 `10.0.26200`、Visual Studio 18 2026 Community、MSVC `19.51.36260.0`、Windows SDK `10.0.26100.0`、x64 Release、CMake 4.2、Python 3.12.10。警告は既存の/W4 /WX等に従う。MinHookは既存pin `c3fcafdc10146beb5919319d0683e44e3c30d537` のまま。

| 検証 | 実測結果 |
| --- | --- |
| 変更前Windows x64 build / CTest | 成功、10/10 |
| Task 1 RED | NativeModuleResolutionTestsが不足するlocal_bytesログで失敗 |
| Task 1 GREEN | 1/1。全16差分位置、複数差分、部分読取/reuse、E9正負/整数境界/unknown、Issue #17 hop 0の算術 |
| Task 2 CLI RED→GREEN | 新flag未受理で失敗→受理/混在拒否を実装して1/1 |
| Task 2 identity RED→GREEN | handleと別PIDの診断を現行resolverが通すテストで失敗→一致gateを実装して1/1 |
| 変更後Windows x64 build / CTest | 成功、10/10 |
| read-only実APIとsynthetic host | query/readのみのhandleで一致診断。別のテスト専用childに合成E9を設置し、read-only診断とinjector双方がbyte_mismatchで拒否、InjectionProbe非実行。最初の行先のMEM_IMAGE属性も取得 |
| 対象外CLI / stop / 注入 | 対象外hostは診断CLIでもexit4。既存wrong-process、named IPC stop、非フックhostへのsynthetic注入も成功 |
| generated include / V3PF解析 / diff check | 成功。runtime/hook traceはsynthetic証拠のみ |
| 全branch review後の修正 | `--output --diagnose-loadlibrary --pid 123` が受理されるREDを確認。switchを値として受け取らない修正後、両順序の診断・全switch/value混在と全Windows CTestが10/10 GREEN |

ローカルbinary hash、source commit、各RED/GREEN logのhashは[validation.json](../../../research/generated/loader-readonly-diagnostics-2026-10-12/validation.json)に保存した。raw logは個人の絶対pathを含むため作業フォルダに保持する。GitHub Actionsは途中で起動せず、PR公開時の最終確認のみ使用する。最終CIのrun URL/head SHA/job結果はPR本文に日本語Markdownとして保存し、追加の文書pushによる不要な再起動を避ける。

## 全branchレビューの判定

Superpowersの独立・読み取り専用レビューでCriticalなし、Important 1件、Minor 1件を検出。Importantは診断flagが値として消費される不正入力で、失敗テストを先に確認して修正した。修正後のWindows全suiteは10/10。レビューが対象としたcommitは `63eaf5c6a151373700620032996e2e9cdc87da34`、指摘修正は `e49167320c3197ad642ae6ebaa7f632e3315e31d`。修正は新しいRED→GREENと全suiteで検証し、同じreviewを再依頼していない。

非blockingのMinorとして、追加branch query失敗時の元stage/error保持、およびhex設定したstreamのdecimal出力/flags復元の明示テストが未追加。実装をレビューした範囲では元拒否の変更を認めなかったが、失敗側の追加coverageは次回課題として残す。

レビューが判断を保留した範囲は、(1)実ゲーム/Steam互換/Phase 4/性能、(2)既存のmodule/byte/query競合と関数全体の信頼、(3)上記Python platform fixtureの修理、(4)pure helperを同じdiagnosticsで拒否後に成功再利用したときの古いstage保持。いずれも今回の成功主張に含めない。特に(4)は既存挙動でproduction wrapperが毎回resetするため今回のCLIには持ち越さない。

Python全suiteは255 testsを実行し、環境補正後も `FAILED (errors=6, skipped=6)`。異なる5 methods（1 methodで2 subtests）に残るエラーは以下。これらのtest/toolはbase mainと同一で、今回変更していない。Windows全suite成功とは扱わず、PR最終CIのUbuntu Python検証も確認する。

- `CliTests.test_refuses_index_artifact_and_hardlink_output_alias`: sandboxのhardlink作成でWinError 5。
- `InventoryTests.test_rejects_absolute_parent_and_symlink_escape`: symlink権限不足WinError 1314。
- `RuntimeTests.test_absolute_csv_cannot_read_or_overwrite_external_evidence`: Linux前提のshadow fixtureがWindows drive colonをdirectoryに含みWinError 123。
- `RuntimeTests.test_csv_drive_relative_and_backslash_paths_are_rejected`: Windows driveを含むfixtureの2 subtestsでWinError 123 / evidence root拒否ValueError。
- `RuntimeTests.test_header_only_csv_cannot_certify_measured_workload_or_overhead`: fixtureのWindows separatorによるmanifest artifact検索でStopIteration。

初回Python実行はtemp書込制限、capstone不足、golden JSONのcheckout CRLF変換により失敗。作業フォルダのTEMP/TMP、workspace限定capstone 5.0.7、git blobからのgolden復元で環境を補正した。golden内容/expected hashは変更せず、既存suiteの検証を隠していない。関係のないPhase 4 fixtureの移植修正は本PRに混ぜない。実ゲームfixture等を要求する6件のskipも合格数へ含めない。

テスト専用InjectorHostの合成E9は、そのchild自身のLoadLibraryW入口へ自己設置し、実行しないfixture。実ゲームやSteam/AMD等の第三者フックを変更する機能はproduction codeへ追加していない。これはSteamの実際の二段経路、private trampoline、ABIを再現したものではない。

## 再現コマンドと環境上の制約

```powershell
cmake -S src/native -B build/native -G 'Visual Studio 18 2026' -A x64
cmake --build build/native --config Release
ctest --test-dir build/native -C Release --output-on-failure
python tools/render_native_profiler_targets.py --check
python -m unittest discover -s tests
git diff --check
```

このsandboxではGit LFS filterとCMakeのGit submodule helperがMSYS named-object accessで失敗した。作業cloneではLFS filterを無効にしてLFS大容量archiveをpointerのまま保持し、MinHook cloneのpinを直接確認して、`-DFETCHCONTENT_SOURCE_DIR_MINHOOK=build/native/_deps/minhook-src` で同じsourceを指定した。repositoryのLFS設定、CMake、pinを変更する解決策ではない。通常環境/CIは既存FetchContentを使用する。

## 未解決事項・次の実ゲームゲート

1. 接続は未解決。診断追加はSteam等のフックを許可する変更ではなく、現条件ならexit8が継続し得る。
2. 最初のジャンプ先の属性まで。FF25/REX/他opcode、private領域の二段目、最終DLL所属・署名・設置主体を判断しない。
3. 開始時刻とPIDは採取したhandleのidentity。外部contextとの照合が必要。module snapshot/byte/queryが原子的という保証はなく、検査中・検査後の変化も未解決。
4. 両16bytes一致は完全なコード信頼証明ではない。既存の間接参照/コード全体/競合の限界を今回も残す。
5. 実ゲームのnew binary実行は未実施。次回はfresh PIDでread-only診断を1回、log/exit/context/Loader hash/sourceを採る。そこで終了し、結果を審査してから別セッションのdisabled attachを判断する。
6. disabled attach/ready mask0/stop/trace、enabled 3 targets、観測負荷、同一区間CSV/OS、反復、save/reload安定性は既存Phase 4の別ゲート。今回のoffline成功では満たさない。

## 引き継ぎ用prompt

```text
pengin0503/Vic3-optimazationの最新mainとPRのheadを取得し、Issue #17、2026-10-12-loader-readonly-byte-mismatch-ja.md、診断guide、Injector.cppを読む。安全gateを維持し、fresh PIDで採ったdiagnose-loadlibraryのv3全文・context・binary provenanceを同一processとして照合する。exit0はattach成功ではない。byte_mismatchは再試行/stop/enabledへ進まない。最初のE9行先とMEM_PRIVATE/MEM_IMAGEを観測値として扱い、フック主体や安全性を推測しない。実ゲーム接続/Phase 4/高速化は実測するまで未確認。CIは最終確認のみ。Superpowers Nativeで続行する。
```
