# オフラインCPU研究 Phase 3 — native診断基盤の実装・検証記録

Date: 2026-10-11
Branch: `research/offline-cpu-parallelism-20261011`
Spec: [offline CPU research design](../specs/2026-10-11-offline-cpu-research-design.md)
Plan: [Phase 3 implementation plan](../plans/2026-10-11-offline-native-diagnostics-phase3.md)
Previous gate: [Phase 2 gate review](2026-10-11-offline-cpu-gate-review-ja.md)

## 結論と境界

Phase 3のオフライン実装とWindows x64 synthetic検証は完了。Windows Loader/DLLのビルド、synthetic hostへの注入、named IPCのstop subscriber、DLLのfail-closed lifecycle、MinHookの合成関数hookは検証済み。実ゲームattach、正常に有効化されたDLLセッション全体のstop/finalize、observer overhead・安定性は**未検証**。実ゲームで以前発生した `Attach failed (no retry), code 4` の原因・解消は確認できていない。今回の変更は失敗の説明と拒否条件を強化するもので、attach成功やゲーム高速化の主張ではない。

ゲームは起動せず、セーブ・ゲーム状態・スケジューラ・ロック・並列化・更新頻度を変更していない。native hook/B0のproduction実装も変更していない。追加したproduction policyにはprocess accessや新しいlive-pointer読み取りAPIがない。

## 開始時の証拠

開始時に最新mainと指定ブランチをGitHubで確認し、取得後のgit refsとも照合した。SHAは開始時の記録であり、将来固定する値ではない。

| 証拠 | 値 |
| --- | --- |
| main | `6584565f0000e56e4653274dbb7659b74806ae84` |
| 作業開始時のbranch | `d5747c716b8bbbf440fa1c695de6e94d73464d40` |
| 分岐状態 | mainより17 commits先行、behind 0 |
| 添付Vic3_data.zip SHA-256 | `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` |
| ZIP内victoria3.exe SHA-256 | `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54` |
| ローカル検証環境 | Linux、GCC 13.3.0、CMake 4.4.4、Python 3.12.14 |

ZIPはread-onlyで一覧・hashを確認し、最後に既存のexact-inputオフラインテストにも使用した。原本を書き換えていない。既存Windows host、Loader、DLL、PE resolver、buffer、Stage A/B0、generated includeを再利用した。

## 実装内容

### Loaderのmodule resolution

`ModuleResolutionPolicy.{h,cpp}` に既存チェックを小さく抽出し、Windowsの `RemoteLoadLibrary` が同じproduction policyを呼ぶ。Windows APIの収集処理・exact-build gate・injection順序を維持した。

- `Module32NextW` の失敗直後にGetLastErrorを保存。列挙が正常終端 `ERROR_NO_MORE_FILES` に達した場合だけ候補を採用する。一致moduleが1件見つかっても、途中失敗は `module_next` で拒否する。
- clean endをboolで明示し、API失敗なのにerrorが0の場合も拒否する。元のerrorを架空の番号に置換しない。
- owner pathの一意一致、image size一致、local executable/non-writable `.text`、remote exportの**16 bytes全体**のimage境界とアドレス加算overflowを確認する。
- zero remote base、短いread、byte mismatchを拒否。policy拒否の `win32_error` は0にし、古いAPIエラーを流用しない。
- diagnostics v2にlocal/remote baseとexport addressを追加。`Attach code 4` と `Gate code 4` の区別は維持する。
- fallback、再試行、protectionの緩和、validation bypassは追加していない。これらの拒否はremote allocation/write/thread作成より前にある。

### テストの不足分

以下の結果は最初のLinux検証時点。後続のWindows結果は「Windows x64最終検証」を参照。

| 対象 | 既存との重複を避けた追加検証 | この環境での結果 |
| --- | --- | --- |
| PE/export/address | section count 0/97、overlap、header内に収まらないtable、16-byte境界、zero base、overflow | owned fixtureで成功 |
| module diagnostics | partial enumeration、0/2 matches、size mismatch、short read、byte mismatch、stale error、v2 fields | production policyで成功 |
| native hook | nested correlation pairs、同一exception、Active復旧、残り1slot、timestamp失敗、pool不足、original中のstop | portable hookで成功 |
| B0 | record満杯＋inner throw＋outerの64-bit opaque return、zero drain、unique FIFOのpartial drain/refill | 成功、production変更なし |
| stop subscriber | IPC不在、mapping不足、completionなしtimeout、signaled Pending/Ready、completion後のstatus | Windows用に追加、未実行 |
| Windows integration | 既存host/InjectionProbe、wrong-process gate、API error、MinHook、DLL lifecycle | 新旧とも今回の環境では未実行 |

通常のnative CMakeはWindows x64専用のまま。`src/native/tests/offline/` はLoader/DLL/MinHookをビルドせず、共通policyと既存のowned PE/buffer/hookだけを検証する別入口。PE32+のpointer解釈に合わせ64-bit pointersを要求する。

## TDD・回帰検出の証拠

新policyはテストを先に追加し、production API未実装のREDを確認して実装した。列挙のclean endを明示するAPI追加にもRED→GREENがある。既存の正しいhook/B0に追加したcoverageは最初からGREENだったため、不必要にproductionを書き換えず、scratch内の一時的なソースコピーでテスト感度を確認した。

| 意図的な退行 | 検出したテスト／結果 |
| --- | --- |
| 16-byte image範囲検査を削除 | `ModuleResolutionTests` の末尾RVA拒否assertで非ゼロ終了 |
| 列挙途中失敗を無視 | partial enumeration拒否assertで非ゼロ終了 |
| hookのActive decrementを削除 | nested Active invariantで非ゼロ終了 |
| B0 original callbackを抑止 | `full_records_reentrant_throw_preserves_outer_bits` が失敗 |
| B0 drain順序を反転 | `zero_and_partial_drain_preserve_fifo_after_refill` が失敗 |

mutantはbuild内の一時コピーだけで、repositoryや配布物には含めていない。

最終レビューは独立したread-only reviewerを1回使用し、実装担当の委譲は行っていない。レビューでoffline CMakeの32-bit guard不足を確認。32-bitで8-byte pointerをコピーし得るため修正対象として扱い、CMakeのproject includeでpointer-size=4を模擬したconfigureをRED（受理）→GREEN（拒否）にした。これは実際の32-bitコンパイル検証ではない。通常64-bit構成・テストも再確認した。未対応のレビュー指摘はない。

## 最終ローカル検証（Windows継続前の履歴）

| 検証 | 結果 |
| --- | --- |
| `python -m unittest discover -s tests -v` | 214件中212件成功、2件skip |
| skipされたexact ZIP analyzer / locatorをVIC3_DATA指定で個別実行 | 2/2成功（約13秒）；合計214の異なるPython testsを実行して成功 |
| scheduler model unittest | 11/11成功 |
| offline native CTest | 4/4成功、warnings as errors |
| Stage A/B0 CTest | 11/11成功；B0 unitは48/48 |
| 2つのgenerated include `--check` | 成功、include変更なし |
| Linuxで通常native configure | Windows x64専用の既存gateで拒否 |
| 模擬32-bit offline configure | pointer-size guardで拒否 |
| `git diff --check` | 成功 |
| Windows native Loader/DLL CTest / 実ゲーム | **未実行・未検証** |
| B0の既存push CI | 1回・4/4 jobs成功（GCC、Clang、Clang ASan/UBSan、MSVC x64）；native Loader/DLLは対象外 |

最初のPython baselineはoptional capstone未導入で3 errors・16 skipsだった。原因は既存 `tools/requirements-callgraph.txt` の依存不足。`capstone==5.0.7` を導入すると214件・2 skipsになり、残った2件も添付ZIPで個別成功した。コードをこの依存不足に合わせて変更していない。

開発中は対象テストを中心に実行し、最後に既存suiteとgenerated checksをまとめた。レビュー修正後は影響するconfigureとsuiteだけ再確認。手動でActionsを起動・再実行していない。ただし既存 `lookup-reuse-contract.yml` が全branchの対象path pushを受け取るため、B0テストcommitの保存時に[CI run 38147618975](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38147618975)が1回自動実行され、成功していた。これはWindows Loader/DLLの検証ではない。branch制限を確認する前に保存したため、CI利用が最終確認だけにならなかった点を記録する。

再現コマンド（通常PATHにcmake/ctestがある環境）:

```sh
python -m pip install -r tools/requirements-callgraph.txt
python -m unittest discover -s tests -v
python -m unittest discover -s research/experiments/scheduler_model -p 'test_*.py'
python tools/render_native_profiler_targets.py --check
python tools/render_lookup_contract_manifest.py --check
cmake -S src/native/tests/offline -B build/native-offline
cmake --build build/native-offline --config Release
ctest --test-dir build/native-offline -C Release --output-on-failure
cmake -S src/lookup_reuse_contract -B build/contract -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/contract --config Release
ctest --test-dir build/contract -C Release --output-on-failure
```

exact-inputの2 testsを含める場合は `VIC3_DATA` に元のZIPを設定する。未設定のfull suiteでのskipを成功件数に混ぜない。

## Windows x64最終検証（2026-10-11の継続作業）

[継続計画](../plans/2026-10-11-native-windows-offline-validation.md)に沿って、既存 `tests.yml` のWindows jobを `.github/workflows/native-validation.yml` へそのまま抽出した。既存main/PR/manual入口は再利用呼び出しに変え、研究branchにはnative関連pathだけのpush入口を追加した。ドキュメント更新は対象外。Python/B0を重複してCI実行するためのPRは作成していない。native production・テスト・generated include・exact-build gate・MinHook pinに追加変更はない。

| 証拠 | 結果 |
| --- | --- |
| 開始時main / branch | `6584565f0000e56e4653274dbb7659b74806ae84` / `0b9aa43fb728d323f9253002fb3cee17c8f09856`（最新fetch、clean） |
| 検証commit | `a101c56a7dcb33b9361677e99f146ae10b3ef831` |
| 最終CI | [run 38148690363](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363)、attempt 1、1 job成功、再実行なし |
| 環境 | Windows 2022、Visual Studio 17 2022、MSVC 19.44.35229.0、Python 3.13.16、x64 Release |
| configure / build | 成功；first-partyは既存 `/W4 /WX /permissive-` を維持 |
| native CTest | **10/10成功、skip 0**、0.28秒（合成テスト時間でありゲーム性能ではない） |
| V3PF parser CLI | runtime-format / hook-formatの2本とも成功 |
| ローカルCI設定検証 | actionlint 1.7.12成功、抽出jobのbaseline完全一致、branch/path/permission構造確認成功 |
| generated checks / diff check | 両include `--check` と `git diff --check` 成功 |

CTestの実行証拠はjob logとartifactの `Testing/Temporary/LastTest.log` で照合した。Windowsビルドでは `_WIN32` 内のAPI/IPC/MinHook処理も実行され、portable testsのみの成功ではない。

| 実行テスト | 確認範囲 |
| --- | --- |
| NativeResolverTests | owned PEとtarget拒否、Windows SHA-256実装 |
| NativeFormatTests | Python golden bytesとの一致、合成V3PF出力 |
| NativeBufferTests | overflow・pool不足・SPSC順序 |
| NativePythonCompatibility | runtime-formatのPython parse |
| NativeRuntimeTests | config、allocation failure境界、DLL loadと独立validation拒否（ValidationFailed / enabled mask 0） |
| NativeHookTests | original exactly once・arguments・exception・drops、MinHookのcreate/enable/disable/remove/shutdown |
| NativeHookFailureTests | 再入・exception identity・partial drops・original実行中stop |
| NativeHookPythonCompatibility | hook-formatのPython parse |
| NativeModuleResolutionTests | owned PE/export境界、列挙途中失敗、size/read/bytes不一致の拒否 |
| NativeInjectorTests | real named IPCのstop失敗/timeout/terminal status、wrong-process CLI拒否、snapshot/query失敗、synthetic hostへのInjectionProbe注入成功 |

### Artifactとprovenance

[保存artifact 11706440529](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363/artifacts/11706440529)のZIPを取得し、APIのdigestと実bytesのSHA-256一致を確認した。サイズ89,625 bytes、保存期限2027-01-09（GitHubの期限付きartifact）。配布・ゲーム導入は行っていない。

| ファイル | SHA-256 |
| --- | --- |
| artifact ZIP | `2aa26f369f4a91590d694e4228b41052e63dc82b00467ea39555c973c594799c` |
| Vic3OptimizationLoader.exe | `2abbfcd6e1dcb69a967b3e9a24f7e9270e080767f24a364741636d90f34770bc` |
| Vic3OptimizationProfiler.dll | `39d14473352914bc51d2eb015d3c053604d6f5be45ad058f27402b7ece5e790d` |
| Testing/Temporary/LastTest.log | `29103111efbdff765a7422f9081cbae6c008ec4ac884c5a29b2af4e60c25e6fd` |
| runtime-format.v3pf | `928d1a2d7b46aed32fe98ad39fced603d26c1d0c82d12f7bfa6a642650279cd6` |
| hook-format.v3pf | `5ea576bc90e0243af516133c1a270ca6c3d6e3e56db886511f503b978d595c18` |

両parsed JSONは `header_valid=true`、`segment_complete=true`、diagnostics空、2 events / 1 function pair / drops 0。header内のexact executable hashとtarget table hashは**fixture metadata**であり、ゲームを実行した証拠ではない。追加の異常系は個別CTestのassertで検証しており、この2本のtraceにすべて含まれるわけではない。

### 継続分の最終レビュー

独立したread-only reviewerを1回使用し、CI抽出・routing・failure propagation・Windows条件付きtests・artifact・記録を確認した。reviewerもrun/job証拠をread-onlyで照合した。Critical/Important/Minorの指摘は0、実装の委譲・再レビュー・CI再実行はなし。

判断記録（reviewの対象外範囲）:

- 実ゲーム挙動: 成功へ拡張せず未検証を維持。誤認すればruntime gateを誤って通すため、attach/stop/overheadを実ゲーム条件として残す。
- 他のWindows build/security environment: このCI環境だけの証拠。別環境での失敗を否定できないので、対象環境のCTestとdiagnosticsを必要条件として残す。
- 既存Phase 3 productionの再レビュー: 前回の独立レビューとテストを保持し、今回変更したCI/記録のみをレビュー。既存不具合の再発見を保証しない。
- branch protection/required check名との互換性: 今回はmainにmergeせず、既存設定を変更しない。entry pointsは構造検証し、研究branchの直接pushを実行確認した。将来mergeを行う場合は再利用jobのcheck名とrequired checksを確認する。誤りがあればmerge gateが期待どおりにならない可能性がある。

### 残るWindows／実ゲーム条件

synthetic hostではmodule owner/path/size、remote memory protection/read、実LoadLibrary注入の正常経路が通った。policy拒否はowned fixtures、APIエラーは既存hostのinvalid PID/handleで確認した。remote processで途中列挙失敗・module mismatchを強制するfault injection、別Windows build/security environmentでの成功は未検証。

`NativeRuntimeTests` はDLLが未知hostを拒否する経路を確認する。exactゲームを受理して3 targetsを有効化し、writerを含む正常セッション全体をstop/finalizeする経路は今回の証拠に含めない。既存MinHookテストで合成関数hookの停止・除去が通っても、この境界は変わらない。実ゲーム `Attach failed (no retry), code 4` の原因・解消は依然未確認。

判断記録: 承認済み設計と専用checkoutを継続し、CI設定は構造検証とWindows最終gateで確認した。ゲームコードや低影響設定を写すunit testsは増やしていない。誤りがあればworkflow routing失敗として扱い、Windows成功を主張しない。無関係なLinux full suiteは再実行せず、以前の結果を履歴として保持したため、新たなLinux全体の成功とは主張しない。branch保持・main非mergeは既存指示どおり。

## 保存commit

以下はGitHub上の正規commit。既存17 commitsを親履歴として保持し、指定branchだけをfast-forward更新した。mainへのmergeやPR作成はしていない。

| 内容 | Commit |
| --- | --- |
| Phase 3専用計画 | `35c79a759e32a30822f13c6cf7b0b42cfb9ca714` |
| module/export診断とfail-closed | `e0e964cc71635a0a7643b4b600242c34e26fa344` |
| stop/hook/B0異常系回帰 | `428164402a4bfe84e4b7f794ff82f100ee8653c7` |
| offline 32-bit構成拒否 | `715139d4f902a2507b8aec982d9a39dc01a037f5` |
| 本記録・案内の初回更新 | `67ad236277d19555895ae7e9aef652126fe6cd4e` |
| Windows最終検証のCI再利用入口 | `a101c56a7dcb33b9361677e99f146ae10b3ef831` |
| Windows結果の記録 | 本ファイルの継続更新commitを参照 |

## 残る検証と次のゲーム内測定条件

**ゲームなし**のWindows x64 configure/build/CTestは上記CIで完了した。10/10成功には `NativeModuleResolutionTests`、`NativeHookFailureTests`、拡張 `NativeInjectorTests` が含まれる。正常に有効化されたDLLセッション全体の停止待ち・writer finalizeと、各実ゲーム条件は未検証のまま残る。

Windows synthetic testsが通っても、以前のゲームattach code 4が解決したことにはならない。次に必要な実ゲーム検証:

1. exact 1.14.5の新規プロセスでdisabled attachを実行し、Loader/DLLの独立validation、v2 diagnostics、stop結果を保存する。code 4が出ればstage・error・path・size・RVA・address・protection・bytes_readを根拠に切り分ける。
2. 再起動したプロセスで3 targetsすべてを検証し、parseable V3PF、説明可能なBegin/Endとdrops、正常stop/finalizeを確認する。部分target成功を全体成功としない。
3. 同一save/hash・camera/UI・完全一致run境界・warm-upと反復を揃え、12/16 threadsのdisabled/enabled observer overheadを比較する。
4. 同期したper-thread Running/Ready/Waiting、CPU/wait trace、built-in CSVとの関係、長時間安定性とセーブ確認を得る。

CPU負荷の原因判断、実際のcritical path、scheduler/lookup/GPUの性能パッチを検討する段階に進む場合は、この実測が必要。offline fixture成功だけでPhase 4やStage Bのgateを満たしたことにはしない。詳細は[実ゲーム検証ガイド](../guides/2026-10-05-native-profiler-runtime-validation-ja.md)。
