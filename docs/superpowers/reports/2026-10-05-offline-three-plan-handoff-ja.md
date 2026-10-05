# Offline 3計画完了 handoff — 2026-10-05

測定状況の更新：各3回の新しい計測は[反復ベンチマーク解析](2026-10-05-repeated-benchmark-analysis-ja.md)を参照。診断基準は12、比較対象は16。以下はオフラインツールの実装・検証記録として保持する。

## 現在地

追加ゲーム内測定を行わず、指定3計画の全11 Taskを順番に実行した。
Native / executing-plansで実装し、最後だけ別コンテキストの全体レビューを1回実施。
各コードTaskはRED→GREEN、focused test、全体test、個別commitを実施。
文書のみのTaskは計画通り、wireサイズ照合／全体testで検証した。
ゲーム挙動を変更する実装はない。次のOS export到着後はmappingの確認から分析へ進める。

- 開始時にGitHubで確認したmain: `464d37bdf36df1662ac739833dfa09d6bbcd9e23`。
- 作業ブランチ: `feat/offline-analysis-2026-10-05`。全検証後にmainへfast-forward統合済み。
  初回統合commit: `006f251da9ecb279604bc0522ae35dfa1c1381d8`（この統合確認追記より前）。
- 親設計: [native optimization design](../specs/2026-10-04-native-performance-optimization-design.md)。
- 実装・レビュー修正済みremote HEAD（handoff追加前）: `7df65d39181aacef860628904a0fa573a8614f01`。
- clone認証が使えない環境だったため、GitHub APIから固定commitのtext blobsを取得。
  改行を含めGit blob SHAで一致を確認し、Task commitを元のremote tree/親commit上へ再構成。
  ローカルsnapshotの独立した初期commitはremoteへ送っていない。

## 完了したもの

| 計画 | 成果・実入力結果 | 再開入口 |
| --- | --- | --- |
| TickTask dependency | Graph/List起点のbounded抽出、直接callとtail jump／間接site／RIP参照の分離、証拠分類、再現recipe。実入力で41 function groups、59 unresolved、dependency edges 0 | [静的証拠](../../../research/ticktask-dependency-static-map.md) |
| OS normalization/correlation | 明示mappingによるCSV取込、Decimal→integer ns、VA/base検証、quoted stack保持、hash/run gate。230 targets（224 TickTask tail groups＋既存証拠の6 overrides）、34 unresolved、範囲conflicts 0。集計はtarget/thread/event/process別、存在するmetricだけ合算 | [workflow](../../../research/os-profiling-plan.md)、[schema/template](../../../research/os-profile-normalized-schema.md) |
| Native profiler offline core | 112-byte prefix／24-byte event header、6イベントの明示payload padding、canonical target hash、reference encoder、strict parser、synthetic golden。8 records、2 threads、2 function pairs、1 wait pair、1 SchedulerDecision、1 Counter | [wire contract](../../../research/native-profiler-event-format.md)、[golden](../../../research/generated/native-profiler-v1-golden/README.md) |

「confirmed-static」は静的なidentity/range/referenceの確認を示すだけで、runtime proofではない。
親子関係のconfirmed-staticは0件。間接call、共有helper、共参照からedgeを作らない。
structural classifierは外部でレビュー済みのdataflow attestationを分類する入口であり、
現extractorはそのattestationを生成していない。将来のattestationは命令証拠と共にレビューする。

## commit記録（remote）

| Task | commit | RED / GREENの要点 |
| --- | --- | --- |
| Dependency 1 | `0846535` | missing module → hash拒否・決定的抽出・budget・call分離など4 tests |
| Dependency 2 | `424bb66` | missing classifier/renderer → 6 focused tests |
| Dependency 3 | `82df41d` | missing recipe → 3 focused tests＋exact ZIP再現 |
| OS 1 | `1320695` | missing normalizer → 8 focused tests |
| OS 2 | `03d4b12` | missing catalog → 6 focused tests、カタログ生成・hash確認 |
| OS 3 | `ddca9ab` | missing correlator → 6 focused tests |
| OS 4 | `f26595d` | proseに脆いtestを追加せず、full suiteでworkflow文書化 |
| Native 1 | `969173a` | 文書のみ、struct size 112/24と全payloadサイズを独立照合 |
| Native 2 | `38fb746` | missing codec → 3 tests（全6 payloadのliteral golden bytes） |
| Native 3 | `19292e0` | missing parser → 9 focused tests |
| Native 4 | `60b7ede` | missing committed binary → golden test、explicit regeneration、full suite |
| Final review fix | `7df65d3` | 3 regression testsのFAILを確認→修正→120 tests PASS |

レビュー指摘はImportant 2件、Critical/Minor 0件。1回の修正passで両方を解消した。

1. pairing keyへtarget_idを含め、同thread/family/correlationの別targetを独立に扱う。
2. timestamp-invalidなBegin/Endで当該pairを無効化し、thread timestampのhigh-waterを下げない。

primary goldenは修正後もbyte/JSONとも変更なし。独立レビューは過去のRED実行を
最終treeから再構成するものではなく、最終codeとfailure modesを確認した。

## 検証証拠

- `VIC3_DATA=../project_sources/01-Vic3_data.zip python -m unittest discover -s tests -v`
  → **120 tests、failure/error/skipすべて0**。通常の入力なし実行では既存binary test 1件だけskip。
- Capstone `5.0.7`を既存requirementsから導入。新規OS/native codec/parserは標準libraryのみ。
- 添付ZIP: SHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`、
  124,462,636 bytes。mainの正式Git LFS pointerと一致。
- executable: SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。
- `validate_exact_signatures.py`を実ZIPと既存exact-signaturesに実行 → hash一致、**18/18 targets OK**。
- dependency recipeを異なる出力先へ2回実行 → 全生成fileがbyte一致。レビューでも独立再現一致。
- catalog CLI再生成 → committed JSONとbyte一致。全overrideの出典artifact SHA一致。
- golden recipeを異なる出力先へ2回実行 → binary／JSON／hash index一致。
- synthetic CSVでnormalize→catalog correlationのCLIを通し、decimal comma・quoted stack・
  Decimal時刻・decimal VA・target hit・CPU合算を検証。normalizer出力も2回byte一致。
- native parser CLIの出力 → committed golden JSONとbyte一致。
- main統合後のローカル実入力suiteも120/120成功。初回統合commitの
  [GitHub Actions](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37273985844)もsuccess。
- GitHub feature treeの全local blobsが一致し、省略して取得しなかった**43個のraw/large blobs**は
  元mainのSHAのまま保持。handoff前のremote treeは211 blobs、差異0。
- 既存親設計・3計画・wire contractとの整合性をレビュー。広範なsimulation decompileなし。

| committed artifact | SHA-256 |
| --- | --- |
| ticktask-dependencies-1.14.5.json | `6dee83e98fbf33fc6b3eabcbb7770fd50af953e3f21fee0cdf666d08069d8fd4` |
| native-target-catalog-1.14.5.json | `156ab83fb7625cd1a5146d9ff215eae05d55fd6e8abac59702e68740487c0cba` |
| trace-v1.bin | `1ef7ae4eb884f1f5e2682fa57726ed5d964a42563cf4da3233a5cd8c3f183dd2` |
| trace-v1.json | `10b44dae632490a7c0af1c800a7de4147fea45080d28d771b9c80c7477b51be3` |

## 再現と次の入力

正式LFS入力を取得できる環境では:

```bash
git lfs pull --include=input-data/Vic3_data.zip
export VIC3_DATA=input-data/Vic3_data.zip
python research/recipes/reproduce_ticktask_dependency_evidence.py --output local-data/ticktask-dependency-reproduction
python research/recipes/reproduce_native_profiler_golden.py --output local-data/native-profiler-golden
python -m unittest discover -s tests -v
```

dependency recipeはexe hashが一致する既存RTTIを再利用し、不一致／不足なら実binaryから再生成。
出力JSON／Markdown／artifact-indexは`--output`の下。committed top-level artifactはそのJSONのcopy。
完全なOS commandsとmapping templateは上のworkflowリンクを参照。実exportの列名／unit／module baseを
確認してmappingを作成し、run manifestのrun_id/hashを使用する。小さな実export fixtureを受領後、
vendor mappingのintegrationを追加できる。synthetic dataを実測値として使用しない。

## unresolved・今回確定していないこと

- Task parent/child object dataflow、runtime dependency/reachability、critical path、lock causality、
  性能改善率は未確定。59 unresolvedの理由とRVAは生成JSON／静的証拠noteに保存。
- 34 TickTask classesはambiguous/unresolved function metadataとしてcatalogから除外。
  missing metadataを隣接範囲や名前から補っていない。
- WPA/uProfの実export schemaと実traceによるcorrelationは未検証。列名をvendor既定として固定していない。
- runtime native writer、C++ ring-bufferのcorrectness/overhead、loader/injection/detour/wait hook、
  scheduler/worker/chunk override、Employment parallelization、lock removal、state write、patchは未実装。
- 次の実測gateは既存の8/12/16 threadの追加反復と同期OS trace。今回のoffline scopeに残Taskはない。

## 判断とその制約

- APIによるcommit再構成: clone不能でも元main ancestryと未取得入力を保持するため。
  誤りならpublication mismatchになるため、tree/blob SHA一致を統合gateにした。
- 当初のauthor-review案は撤回し、executing-plans通り最終reviewerを1回使用した。
  実装Taskのsubagent展開はしていない。
- 未指定payload padding／UTF-8 canonical JSON／metadata gateをwire文書で固定した。
  将来C++ writerはこのlayoutに合わせる必要がある。
- vendor fixture不足はmapping workflowで受け入れ準備まで進める判断。実exportでmappingの修正が必要になり得る。
- runtime proof・ring-buffer実装は範囲外として保留。follow-upの実測gateは残る。
- structural attestationの真偽は外部レビューの責務。誤用なら将来callerが静的証拠を過大評価し得る。
- RED履歴はsessionで確認し上表へ記録。最終treeだけでは過去のFAILは再現できない。
- remote保全はreviewerの判定外として、上記全blob照合で独立検証した。

Deferred minors: なし。READMEはこのhandoffへの入口だけを置き換え、過去reportは履歴として保持。
