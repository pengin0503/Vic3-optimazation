# 外部CPU計測経路のオフライン準備完了

2026-10-13 JST。開始main: `e738fa52c25760d57479d7ff7304f4209882d387`。

## 成果

自作DLLの接続成功を候補選定の必須条件から外し、既存WPR/WPAとTickTask CSVを主経路にした。[日本語の次の実測手順](../../guides/vic3-external-cpu-measurement-ja.md)、[設計](../specs/2026-10-13-external-cpu-route-design.md)、[計画](../plans/2026-10-13-external-cpu-route.md)、[候補の採否](2026-10-13-external-cpu-candidate-ja.md)、[測定packet](../../../research/external-cpu/README.md)を保存した。

12threadで通常B3回・CPU Sampled S3回、順序B1/S1/S2/B2/B3/S3。まずB1/S1の収集成立を確認する。新たな収集器、product gate、GPU実験、全面decompile、性能patchは追加しない。Lookup core/contract、Loader、native profiler、Phase4 gateの製品コードと既存の受け入れ条件は変更しない。

## 確認した範囲

| 確認 | 結果 |
| --- | --- |
| 開始baseline | benchmark4・normalizer8・correlator6、計18件成功 |
| 添付archive | `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`一致、8,104 ZIP entriesをread-onlyで確認 |
| exact exe / 雇用証拠 | exe hash一致、13範囲hashと7 direct edges一致 |
| 既存catalog | 42対象のsource/range hash一致 |
| 補助catalog | 既存42対象にないlookup/fallback限定excerpt2件。全関数の復元とは扱わない |
| 合成OS入力 | 両catalog別々に88境界sample一致、別module2行除外、曖昧性0 |
| template / benchmark経路 | 6件未測定/nullを確認。scratch合成入力でfinalize→quality→analysis、2variantへ分離 |
| 不正なCSV | 変更したCSV hashの拒否、正しいhashへ更新した場合もworkload境界差でperformance-readyを拒否（CLI exit3） |
| repository Python | `VIC3_DATA=<添付ZIP> python -m unittest discover -s tests -v`、257/257成功、skip0、22.278秒 |
| 相対file links | 新入口と関連文書で73件のリンク先が存在（最終修正前） |

確認の研究recipeと結果は`research/external-cpu/offline-verify-source.py.txt` / `offline-verification.json`にある。合成CSVの10/11秒はscratchの動作確認入力であり、実測templateやゲーム性能結果へ保存していない。

scratch確認の初回は、既存quality toolの`workload_boundary_mismatch`をerrorと想定してassertが失敗した。ソースを確認し、実際はwarningかつperformance-ready=falseであると特定した。scratch assertionを既存契約へ修正し、正しいhashの境界不一致が`--require-performance-ready`でexit3になることも確認した。製品を弱める変更はない。

Python3.11、Capstone5.0.7を使用。製品/native code未変更のためC++再build・Windows CIの再実行は不要と判断し、ローカルsuiteを最終確認に使用した。WPR custom profile・CLIの公開仕様と旧実機証拠を参照したが、今回の環境はLinuxであり、Windows PowerShell/WPR開始・停止・actual exportは今回未実行。

## 残る実測と将来作業

次の前提はWindows game machineでのB1/S1。settings、同save/期間、collectorなし/ありの条件、CSV freshness、process identity、保存後drop/stack coverage、境界の根拠を確認する。成立したら残り4回を採取する。markerの外側区間はgameの実時間ではない。

今回の測定準備に、追加のオフライン製品実装は残していない。一方、プロジェクト全体では実測結果の分析、候補選定、必要なABI/table寿命/並行アクセス確認、個別性能patchの設計・実装、安全な適用、実時間A/B、長時間save/reloadが残る。これらが「実測だけで完了する」とは報告しない。

性能patch0、実ゲーム接続の成功未確認、measured speedup/observer overhead=null。Issue #17、native Phase4のblocked、GPU結果はそのまま。外部経路へ移ったことをnative acceptance達成や検索bypass承認と扱わない。

## 最終レビュー

最初の独立reviewはモデル利用制限で中断したが、計測後metadataを古い`$manifest`で上書きする問題を指摘した。CSV保存前と最終確定前にdiskの最新版を読み直し、metadataレビューとfinalizeを分離して修正した。既存finalizerが操作者の`os_capture`情報を保持することも合成入力で確認した。

利用可能な別reviewerが全変更とその修正を確認し、Critical0、Important1、Minor1を報告。ImportantはWindows PowerShell 5.1のANSI既定読込みによる日本語UTF-8破損で、全JSON`Get-Content`へ`-Encoding UTF8`を明示した。旧roadmapのPhase4計測への無限定誘導は、今回の主目的に対して外部経路を止め得るためImportant相当と再評価し、native専用と明記して修正した。保留したminorはない。

Windows PowerShell/WPR実行、実WPA export/stack品質、実game測定はreview対象でも未実行の限界として維持する。最終修正は文書のみで、製品suiteの再実行や追加reviewは行わない。最終の差分・リンク・UTF-8指定・template状態を確認した。GitHubの`research/external-measurement-route-20261013`からmainへの文書/packet PRとして保存する。追加のCIを手動起動せず、文書のみの最終commitには`[skip ci]`を付ける。これは既存の257件と合成検証を再利用する判断であり、CI成功やWindows実行を主張するものではない。
