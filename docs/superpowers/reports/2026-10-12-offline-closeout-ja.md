# 非ゲーム作業の限定closeout

Date: 2026-10-12 JST
Spec: [限定設計](../specs/2026-10-12-offline-closeout-design.md)
Plan: [Native実行計画](../plans/2026-10-12-offline-closeout.md)

ユーザーの「それらの作業を承認確認なしで完了」の指示に従い、既存の非ゲーム残作業を限定して実行した。ゲーム起動・追加ゲーム測定・状態変更・性能patch・main/PRへのmergeは行っていない。途中の承認確認は省略したが、既存のmain merge禁止を取り消すとは解釈しなかった。

## 完了範囲

1. Phase4 gateの拒否traceに、parserのkind/offset/count等のstructured diagnosticsを保持。truncated/dropped fixtureでRED2→GREEN33/33。拒否条件・入力保護・parser/native本体は変更しない。commit `eeba999`。
2. 現在の40 indirect instruction RVAsすべてをexact exeから追跡。宣言済みfile-backed rangeの先頭からdecodeし、直前8命令までを保存。境界・部分decode・owner曖昧性・budgetを拒否するowned tests8/8。27 memory calls、3 memory jumps、2 register calls、8 register jumps。calleeは全件unknown、dependency edges0。2回生成のbytes一致。commit `81ce447`。
3. 固定入力のowned integer recurrenceを使い、GPU常駐lifecycleの転送量条件を検証。独立Python integer oracle、入力非変更、shape/dtype、空/large-int、stage上限、host更新と中間結果参照のbatch拒否を7/7 testsで検証。36-case matrixを保存。GPU/time/bandwidth/speedupはfalse/null。commit `2c77dcd`。
4. GPU PR15の全5file差分と既存3-session分析・CIを確認。修正前snapshotのCPU/controller tests24/24、統合後GPU directory tests31/31。最終reviewで判明したH2D診断の重要指摘を修正し、GPU directory34/34成功。CPU研究ブランチへGPU branchを両parentを保持して取り込み、修正もPR15へ反映した。mainは変更せず、PR15はopenのまま。

## 証拠とモデルの意味

indirect追跡は[保存済みwitnesses](../../../research/generated/offline-closeout-2026-10-12/indirect-witnesses.json)と[限定解釈](../../../research/generated/offline-closeout-2026-10-12/README.md)にある。source JSONのowner/rangesを再利用したもので、source-level function完全性、動的callee、graph-object dataflowを認定しない。`0x7d670f`のvptr・size×4に整合する命令は、先行buffer/allocator仮説を補強するのみ。

[GPU lifecycle結果](../../../research/generated/offline-closeout-2026-10-12/resident-lifecycle.json)の1m recordsでは、入力3配列を毎stage uploadして出力をdownloadするモデルは1/4/16 stagesで16/64/256MB。最終結果だけ必要な固定入力batchは16MB。中間結果が必要ならfinal-only batch不可だが、入力をdeviceに保持しつつ毎stage出力を読む12N+4NSモデルは区別した。host入力更新がある場合の結果は模擬しておらず、固定入力recurrenceのdigestを実更新結果とみなさない。

これは転送bytesの条件付きモデルであり、OpenCLのresident pipeline実装・実GPU計測・速度改善ではない。[guide](../../../research/experiments/gpu_offload_spike/README-resident-lifecycle.md)に前提を明記。既存の実機v2では8-thread Numba CPUが96/96比較でGPUを上回り、H2D device events432/432はinvalidだった。この結果を覆したとは主張しない。実hardwareのevent原因切り分け・device pipeline性能は未検証として残る。

## 統合判断

- 開始時latest main `6584565`、CPU `c02bea7`、GPU `db78b1e` をfetchした。
- PR15の既存CIは [GPU CPU-only run37763172082](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37763172082) と [tests run37763171961](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37763171961)、いずれもdb78b1eでsuccess。新しいCPU研究HEADのCI成功と混同しない。
- 最初の取り込みはPR15全5filesがbyte-identicalだった。H2D修正後はshared executor/v2/tests/README-v2の5filesが修正済みPR15 branchとbyte-identical。CPU研究とのconflictなし。ローカル統合treeを検証した。mainへのmerge/PR close・Issue close・releaseは行わない。
- raw GPU hardware JSONの再提出は求めず、Issue12に保存済みの分析・hash・scopeを使用した。今回raw JSON自体を再検算したという主張はしない。
- native/B0を変更せず、そのローカルsuiteや古いCIを意図的に再実行していない。H2D修正をPR15へ最終pushした際のみ、既存PR workflowが自動起動した。[GPU CPU-only CI38197634810](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38197634810) と [tests38197634869](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38197634869) は修正head `cc5302a4ab374381a7236fa77555f09a625847fe` でsuccess。再run/dispatchは0。CPU研究HEAD全体のCI成功や実GPU成功と混同しない。全体Task9の実ゲームacceptanceやTask11/12の性能patch gateは未達。

## 検証結果

| 検証 | 結果と範囲 |
| --- | --- |
| repository Python | exact ZIP指定、255/255成功、skip0。最終material fix後16.121s |
| PR15 source snapshot | CPU/controller24/24成功 |
| 統合GPU directory | 既存・v2・lifecycle・H2D回帰合計34/34成功 |
| native/lookup generator | 両`--check`一致 |
| static生成 | 40/40 sites、2出力bytes一致 |
| lifecycle生成 | 36cases、gpu_executed=false、timing/bandwidth/speedup null |
| Phase4現行inventory | 13/13 hash-valid、game native captures0、blocked、overhead nullを維持 |
| 原ZIP | 添付SHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` 不変 |

Linux専用venv: Python3.12、NumPy2.3.5、Numba0.68.0、Capstone5.0.7。初回static GREEN試行はsystem PythonにCapstoneがなくerrors8、systematic-debuggingで依存不足と確認し、宣言済みdependencyをvenvへ導入して再検証した。productを弱める修正はしていない。

Windowsにおける今回のcloseout code実行、実GPUのresident pipeline、game接続・enabled stop/finalize、実測overhead、同期OS states、長時間save/reloadは未検証。元Phase3のWindows synthetic CTest10/10は再利用した既存証拠である。

## 判断記録

- main merge禁止を維持し、統合はresearch branchに限定。誤ればmainへの統合が先送りになるが、意図しないmain mutationを避ける。
- GPUは利用可能hostに合わせたlifecycle/equality/byte probeを完了範囲とする。誤ればhardware pipeline実装の完了が残るため、その範囲を未実装・未検証と明記。
- static調査は既存40sitesで終了する。誤れば未追跡graph dataflowが残るため、unknownを確定へ変更しない。

## 最終review

Native/executing-plansで自分が実装し、fresh-context gpt-6-astra reviewerを最後に1回だけ使用。Critical0、Important1、Minor1。Importantは、shared executorでH2D eventを合算してからv2でvalidityを判断し、一部zero eventがpositive sumに隠れて不正な帯域を計算する問題。

実event durationを読むproduction helperと、混在zero・missing/malformed・negative/nonfinite copy profilesの回帰を追加。RED6 failuresを確認し、per-copy durationsとcopy bytesをraw sampleへ保持。全copyが正で、長さ・byte総量・duration総量も一致する場合のみ帯域を計算する。aggregate-only legacy profileは未知扱い。GPU34/34、exact-input repo255/255が成功。修正はCPU `75a73c9`、PR15 `cc5302a` に保存。PR15修正をCPUへ取り込む2回目のmerge `b341f6e` はsource bytesを変更せず、両系統のhistoryを保持した。再reviewは行わない。

Minorは保留: generated witness READMEのshell redirectionは事前にlocal-dataがあることを仮定する。再現時は `mkdir -p local-data` を先に実行するか、既存buildディレクトリへ出力する。extractor自身はstdout-onlyで正常であり、入力は書き換えない。

reviewerが判断しなかった範囲は維持: 宣言済みstatic ownershipはsource-level認証ではなく、lifecycleは固定入力CPUモデルのみ。fake-controller testsはhardware evidenceではなく、game/hardware/performanceの合格を認定しない。誤れば広いsemantic/hardware検証が残るため、その代償を明示してunknown/false/nullを維持した。remote mainは最終fetchで別途確認する。

最終保存対象は本report、[更新roadmap](../guides/2026-10-12-project-roadmap-ja.md)、専用計画。scratch reviewer/dependency workspaceは成果保存後に削除するが、公開commit・証拠・hostの元checkoutは保持する。
