# Phase 4 — オフライン証拠gateと実測handoff

Date: 2026-10-12 (JST)

**オフライン実装は完了。実ゲームのruntime acceptanceはblocked。** ゲームを起動せず、追加測定・状態変更・性能patch・mainへのmergeは行っていない。

設計: [親設計](../specs/2026-10-11-offline-cpu-research-design.md)、[Phase 4 contract](../specs/2026-10-12-cpu-runtime-evidence-gate-design.md)。実行: [専用計画](../plans/2026-10-12-cpu-runtime-evidence-gate.md)、Native / executing-plans、TDD、verification-before-completion。実装subagentは使用せず、最後のfresh reviewのみ別contextで行う。

## 実装と監査

`tools/check_cpu_runtime_gate.py` は既存benchmark quality checker、V3PF parser、exact target rendererを再利用する。root内のraw bytes、hash、分類、run manifestを検査し、12/16 × disabled/enabled ×各3回以上、交互順序、fresh process、初期exe/save identity、同一設定・完全一致CSV境界、全3 native targets、attach/stop、OS境界・state・loss、4分析reviewを要求する。reviewは全non-review artifactのhashに結び付く。

出力は入力を変更せずatomicに保存する。path escape、symlink escape、入力とのhard-link alias、runディレクトリ内出力を拒否する。exit0はready_for_review、1はblocked、2はinvalid。exit2で古いreportが残る場合があるのでexit code確認が必要。readyはゲーム実行の認証や性能patch許可ではなく、`performance_patch_authorized=false` を維持する。

[現行index](../../../research/phase4/current-evidence-index.json)と[監査結果](../../../research/phase4/current-gate-report.json)は13/13 artifactのbytes/hashを確認。static4、historical6、synthetic3、game0。runtime capture0、5requirementsはmissing、overheadはnull。2回の出力bytesは一致した。未知の値を0や成功へ置換していない。

提供ZIPのSHA-256は `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`。8,104 entriesにV3PF/ETLはない。exe identityは対象build `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54` と照合。これは現在のゲームrunの証拠ではない。

## 検証

| 検査 | 結果・範囲 |
| --- | --- |
| 新規gate unittest | 32/32。schema/provenance、正の架空fixture、native/CSV/OS/review拒否、CLI・atomic出力・入力保護。各追加behaviorはRED→GREEN |
| 関連quality/parser含むfocused suite | 53/53 |
| repository Python suite | 246件、244成功・2 skip。skipはoptional exact-input integrationで、今回の成功には数えない |
| scheduler model | 11/11 |
| native/lookup generated include | `--check`で一致 |
| 現行audit | exit1、blocked、2回bytes一致 |
| Windows native synthetic | 既存[run 38148690363](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363)、x64 Release CTest10/10・V3PF parser2 captures。Phase 4で再実行していない |

今回のPython変更はLinuxで検証した。Windows上のPhase 4 Python実行は未検証。hash固定JSONとsource artifactには限定的な`-text`指定を加え、checkout時の改行変換を防ぐ。Windowsゲームの正常attach/stop/finalize、observer overhead、per-thread stateや長時間save semanticsは今回のテスト成功から推定しない。

## 既存証拠の限界と次回測定条件

- 旧8/12/16 repeatsの平均wall timeは37.043 /34.517 /34.777秒。12_r2には余分な3 frames・198 records・57 cumulative TickTask msがあり、実測wall timeを補正しない。完全一致境界runは8=3、12=2、16=3で、disabled/enabled比較もない。
- 旧OS captureは外側の手動marker envelope。同期CSVは欠落し、過去のlive CSVは別run。Running/Ready/Waitingやcritical pathをそのまま確定できない。
- 初期saveの回収hashは長時間運用・終了save・再load時の状態安定性を証明しない。
- synthetic Windows成功とgolden V3PFはgame captureに分類しない。実ゲームAttach failed code4は未解消・未確認。現在の資料から性能patch対象は0件。

次にruntime acceptanceへ進むには対象Windowsゲームで、初期exe/saveを確認し、毎run fresh processで12/16 × disabled/enabled ×各3回以上を交互に取得する。同一設定・warm-up・完全一致CSV境界、全3targetsのpaired V3PF、成功attach/stop/finalize、正確な区間とclockで対応したRunning/Ready/Waiting・loss、長時間save/reloadの証拠を保存する。nativeとCSVのscope、overhead対ノイズ、OS状態、save stabilityの4分析を実bytesに結び付ける。[未記入templateと測定手順](../guides/2026-10-12-phase4-runtime-evidence-handoff-ja.md)を用い、欠落を承認や推定で埋めない。

## 保存と判断

開始時にlatest main `6584565` と作業branch `a194c9d` をfetchして確認した。provenance taskは `8ee6333`、runtime gate taskは `0c7c16a`。handoff/reportはこのファイルを含む最終commitで保存する。mainへmergeしない。

判断: 既存の追加測定禁止とアクセス可能なgame host/実captureがない条件を維持し、Phase 4のオフライン準備を完了した。runtime acceptanceまで完了したと扱う判断はしない。誤れば未実証のruntime・性能gateを合格扱いする危険がある。

## Final reviewと限定した未検証範囲

fresh contextのgpt-6-astraで1回reviewした。Critical0、Important3: CSV absolute pathの検査/読み込み不一致と入力overwrite、native diagnostic counterの見落とし、header-only CSVによる空workload合格。4回帰testsでREDを確認し、CSV fieldをjoin前に検査してCLIの入力保護にも適用、production counter1/3/4の非zero値を構造化して拒否、空の本測定境界を拒否した。修正後gate32/32、全体246件中244成功・2 optional skips。修正は `2bf6510`。再reviewやCI再実行は行わない。

Minor1件は保留: parserの拒否diagnosticsはgate reportでgeneric messageになる。元V3PFは保持・indexされ、standalone parserでは詳細を取得できる。runtime合格判断を緩める問題ではない。

判断として残した範囲:
- operatorのgame provenance宣言の認証は行わない。誤ればgame originの過大評価になるため、readyは整合性検査に限定。
- ETL decode・clock alignment・save semanticsは分析reviewに残す。誤れば状態安定性/causalityの過大評価になるため、flagsや初期hashだけから結論を出さない。
- 実game attach、overhead許容性、性能変更許可は未検証。誤れば安全性/性能の過大評価になるため、runtime gate blocked・patch許可falseを維持。
- WindowsのPhase 4 Python実行は未検証。誤ればplatform差の見落としになるため、Linuxテストと改行checkout simulationの範囲を明記。

Linux gitでcore.autocrlf=true/core.eol=crlfを指定したcheckout simulationは、indexされたtext artifacts11/11のhashを保持した。これはWindows runtime検証ではない。対象Markdownのlocal links36件が解決し、diff --checkで問題なし。
