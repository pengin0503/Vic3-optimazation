# Phase 4 — 実測証拠の取得・受け入れ手順

Date: 2026-10-12 (JST)
対象: Victoria 3 Windows 1.14.5、SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。

これは次回測定の手順であり、今回測定を実行した記録ではない。現在の[監査結果](../../../research/phase4/current-gate-report.json)はblocked。ユーザーへの再承認確認は不要だが、欠落した実測bytesは必要になる。実ゲームattach code 4は未解消・未確認のまま。

まだ実ゲーム接続を確認していない場合は[first-pass手順](2026-10-12-user-game-validation-first-pass-ja.md)のA(disabled attach/stop)を先に行う。このmatrix全体を接続失敗中に取得しない。

## 1. 保存先と測定matrixを準備

既存[Windows native guide](2026-10-05-native-profiler-runtime-validation-ja.md)のLoader/DLLを使用する。Windows synthetic CTest10/10の結果は[Phase 3記録](../reports/2026-10-11-offline-native-diagnostics-phase3-ja.md)。環境を変えた場合や再現しない不具合に限り対象Windowsで再検証する。今回のPython証拠検査のために同じCIを繰り返す必要はない。

bundleを `local-data/phase4-bundle/`、測定runをその `runs/` 下へ置く。game exe/saveの原本を書き換えず、重複raw tracesやゲームバイナリを研究commitへ入れない。indexはbundle外へのpathを許さないため、検査対象は保存した証拠コピーにする。

```powershell
# $ActualPopConsolidation は実際のゲーム設定から記録する。設定自体を変更するコマンドではない。
python tools/prepare_benchmark_matrix.py local-data/phase4-bundle/runs/disabled --variant profiler-disabled --threads 12,16 --repeats 3 --no-warmup --pop-consolidation $ActualPopConsolidation
python tools/prepare_benchmark_matrix.py local-data/phase4-bundle/runs/enabled --variant profiler-enabled --threads 12,16 --repeats 3 --no-warmup --pop-consolidation $ActualPopConsolidation
```

生成物は未測定template。既定値・環境欄は現在の実設定の証拠ではない。別途[run extension template](../../../research/phase4/run-manifest.template.json)のnative/OS fieldsを使用する。日時、save hash、camera/UI、speed等は実値を記録し、unknownを0や空の成功値へ変換しない。

本測定は12/16 × disabled/enabled ×3以上。各runで同一手順のwarm-upを実施し、warm-upを本測定repeatへ混ぜない。`--no-warmup` は専用warm-upフォルダを生成しないだけで、実際のwarm-upを省く指示ではない。

実施順例: 12-D1,12-E1,12-D2,12-E2,12-D3,12-E3,16-D1,16-E1,16-D2,16-E2,16-D3,16-E3。`execution_order` は実際の一意な順序を記録。各thread条件でmodeを交互にする。12/16の設定は測定者が既存console手順で行い、profilerや監査ツールは変更しない。

## 2. 各runのidentityとattach

毎runゲームを再起動し、同じ初期save、同じcamera/UI・speed・設定・mod・区間を用いる。PIDを測定者が確認し、自動選択しない。PIDがOSで再利用されても、UTC process start timestampと組み合わせたprocess instanceは別として記録する。

- 初期exe/saveのGet-FileHash出力をUTF-8 `identity.log` へ保存し、測定開始時の確認であることを記録。
- Loader/DLLの実bytes・SHA-256、**そのbinaryを生成したcommit**、artifact/runを保存する。Profilerのsource commitを単に最新repository HEADで置き換えない。既存Windows artifactを用いる場合は `a101c56a7dcb33b9361677e99f146ae10b3ef831` がbuild provenance。
- `native_profiler`: capture_kind=`game`、mode、fresh_process、pid、process_start_utc、source_commitと各artifact IDを実値で記録。
- 実際の初期identityを確認後のみ `capture.identity_verified_at_start=true`。古いsave調査のhashだけを流用しない。

観測用Loaderの具体的なattach/targets/stopは既存guideどおり。初回disabledではmask0、その後のenabledでは全3 targets・mask7を要求し、partial targetsを合格扱いしない。

ログ保存例（変数は実際のrunで指定。ここでは実行しない）:

```powershell
& $Loader --pid $gamePid --disabled --output $Trace 2>&1 | Out-File $AttachLog -Encoding utf8
$AttachExit = $LASTEXITCODE
# enabled runでは --disabled を --targets investment,migration,employment に置換。
# 測定区間完了後:
& $Loader --stop --pid $gamePid 2>&1 | Out-File $StopLog -Encoding utf8
$StopExit = $LASTEXITCODE
```

attach exit0 / ready mask、stop exit0 / finalized logをそれぞれ残す。code 4が発生したrunは失敗のまま保持し、v2 stage/error/path/base/size/RVA/protection/bytes_readから切り分ける。失敗の後にfallback、retry、validation bypassを足さない。

## 3. 区間、CSV、V3PF、OS evidence

同じゲーム日付だけでなく、CSVのframe/task/calls全体を一致させる。保存済み12_r2の余分な3 framesは自動補正しない。CSVをtrimして実測wall timeを対応させたことにもせず、完全一致runを取り直すか比較対象外とする。

停止・capture確定後の、そのrunに属する `ticktask_timings.csv` を保存する。古いlive CSVは使わない。

```powershell
python tools/finalize_benchmark_run.py $RunDirectory --wall-clock-seconds $MeasuredSeconds
```

**finalizeがcapture blockを生成した後**に、identity_verified_at_startとnative/OS extensionを実際の証拠から追加する。既存finalizerはcaptureを置き換えるため、先に追加したidentity flagが保持されると思わない。

raw V3PFとそのSHA-256を保存し、既存parserで検査する。disabled traceはhookなし、enabledは3 targetのfunction pairsが必要。今回の保守的gateはdrop/diagnosticsを自動受理しない。dropが説明可能でも、その説明を保存して別途分析し、診断を削除して通さない。tail-anchor時間はtask全体inclusive時間ではなく、CSVとの1:1一致を仮定しない。

OSは同じrun・同じ実測区間で採取し、raw trace・loss statistics・正確なresume/pause境界・clock alignmentの証拠を保存する。既存 `normalize_os_profile.py` / `correlate_os_profile.py` は明示mapping、units、run IDで再利用する。未知のvendor列名を推定しない。

`os_capture` は実際のtrace/boundary artifact、begin_ns/end_ns、exact_boundaries、clock_alignment_verified、Running/Ready/Waitingの取得有無、dropped_events/lost_buffersを記録する。外側の手動marker envelopeだけをexactとしない。CPU sampleがない時間をReady/Waitingとみなさず、各thread stateを裏付けるexport/traceを使う。この監査ツール自体はETLをdecodeせず、stateやclock alignmentの宣言の真偽は分析記録で確認する。

## 4. bundleをindex化して分析

[index template](../../../research/phase4/runtime-evidence-index.template.json)をbundleへコピーし、各artifactの `id/path/sha256/kind/role/notes` を記入する。pathはbundle rootからのforward-slash相対path。すべてのmanifest、CSV、identity/attach/stop logs、V3PF、OS/boundary evidence、Loader/DLLとreview filesをindex化する。

roleは `run_manifest`, `ticktask_csv`, `identity_log`, `attach_log`, `stop_log`, `native_trace`, `os_trace`, `boundary_log`, `loader_binary`, `profiler_binary`, `review`。過去・合成sourceは別kindとし、実ゲームで採取したものだけgameと宣言する。この宣言は認証ではなく、取得provenanceの責任を明確にするための記録。

4つのreviewをMarkdown等で保存する:

| Review key | 必要な判断 |
| --- | --- |
| native_csv_relationship | 3 anchorsとCSVのcounts/timingの関係、scopeと未観測領域、pair/dropの説明 |
| observer_overhead | 12/16それぞれの交互反復、disabled/enabledの差とばらつき、実測ノイズとの比較 |
| os_running_ready_waiting | 実区間・clockの対応、各thread state、loss、CPU/wait/critical-pathへの推論の限界 |
| save_stability | 長時間運用、初期/終了/再loadの証拠、状態/checksumの検証方法と結果 |

初期save hashの一致だけでsave stabilityを合格にしない。終了saveの実bytes・再load結果と比較方法を記録する。保存形式のメタデータ等も含むraw hashの一致/不一致だけで、simulation semanticsを断定しない。

review entryは `artifact_id`, `accepted`, `run_ids`, `notes`, `evidence_sha256`。run IDsは本測定すべてと完全一致。evidence_sha256は**全non-review artifacts**のID→digest map。raw bytesが変わればreviewも更新する。acceptedは分析で判断した結果であり、追加のユーザー承認待ちを作る欄ではない。根拠が不十分ならfalse/nullを維持する。

```powershell
python tools/check_cpu_runtime_gate.py local-data/phase4-bundle/evidence-index.json --root local-data/phase4-bundle --output local-data/phase4-runtime-report.json
$GateExit = $LASTEXITCODE
```

出力はsource `runs/` の外へ置く。exit0=ready_for_review、1=blocked、2=invalid。exit2では以前のreportが残り得るため、exit codeを無視して古い結果を読むことはしない。

完全・比較可能な組でのみoverheadの中央値比とbaseline CVが出る。固定の許容閾値は捏造せず、実測ばらつき・順序・区間・observerの影響をreviewする。`ready_for_review` は書類・整合性の機械的検査であって、実ゲーム実行の認証、causalityの証明、性能改善patchの許可ではない。Phase 4のruntime acceptanceとStage B/Task 11/12のsemantic gateは別に判断する。
