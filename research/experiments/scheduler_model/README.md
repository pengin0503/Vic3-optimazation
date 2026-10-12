# 合成DAGスケジューラーの比較：オフライン専用

意図的に単純化した独立の整数負荷モデルです。Victoria 3のソースコード、ゲームのジョブを再実装したもの、エンジンスケジューラーの実測ではありません。ゲーム、プロファイラーDLL、セーブ、GPU、ネイティブプロセスとの接続はありません。作業量の単位はミリ秒ではなく、CPU使用率や速度比もVictoria 3の値ではありません。

## 実行

リポジトリルートから、Python 3.11以上の標準ライブラリだけで実行します。

```sh
python -m unittest discover -s research/experiments/scheduler_model -p 'test_*.py' -v
python research/experiments/scheduler_model/compare_schedulers.py research/experiments/scheduler_model/example-workload.json --output local-data/synthetic-scheduler-comparison.json
```

JSON入力は`format_version:1`、空でない`tasks`、重複しない正の`worker_counts`、非負整数の`dispatch_cost_units`を含みます。メモリと処理量を制限するため、最大4,096タスク、構成ごとに最大256ワーカー、各タスク・投入処理の作業量は最大1,000,000,000単位を受け付けます。

各タスクには、一意で空でない`id`、正の整数`work_units`、重複のない`depends_on` ID一覧が必要です。存在しないIDや循環は認めません。不正な入力は終了コード2で終了し、既存出力を置き換えません。再現性のため、出力に入力の生バイト列のSHA-256を保存します。

## 方式と前提

- **ready：**実行中のタスクを中断しないイベントシミュレーションです。前提タスクが完了したら、実行可能な次のタスクを、空いている最小インデックスのワーカーへ投入します。複数タスクが実行可能なら入力順を優先します。各タスクの投入コストは、そのワーカーを占有します。
- **layer-barrier：**最長の前提タスク経路の深さで層を分け、各層の後で全体を待ち合わせる仮想方式です。Victoria 3がこの方式を使うと仮定してはいけません。
- 共有状態の競合、キャッシュ効果、メモリ帯域の制限、スケジューラーの起床、タスク移動、グラフ構築コスト、OSによる実行中断、UI描画、動的なタスクグラフ変更は模擬しません。
- `idealized_lower_bound_units = max(ceil(total useful work/workers), longest useful-work dependency path)`で、各タスクの投入負荷を除外します。このモデルの理想的な数学上の下限であり、実行時間の推定ではありません。
- `useful_utilization = total useful work / (workers × synthetic makespan)`、`worker_idle_units = workers × makespan - useful_work - dispatch_overhead`です。投入処理の負荷は有用な作業量に含めません。
- すべての出力オブジェクトに`synthetic_only: true`を含め、実ゲームから`candidate_dependency_edges`のグラフを推定しません。

## 合成例の結果

例には独立した8単位のジョブ1件と、2→3→1単位の連鎖があります。投入コストはタスクごとに1単位です。

| ワーカー数 | 理想的な下限（作業量のみ） | readyの完了までの時間単位 | layer-barrierの完了までの時間単位 |
| ---: | ---: | ---: | ---: |
| 1 | 14 | 18 | 18 |
| 2 | 8 | 9 | 15 |
| 4 | 8 | 9 | 15 |
| 8 | 8 | 9 | 15 |
| 12 | 8 | 9 | 15 |
| 16 | 8 | 9 | 15 |

この入力は、並列化の効果が頭打ちになる例を示します。Victoria 3に同じDAG、投入コスト、全体の待ち合わせ、特定のCPU使用率があることを証明しません。実際の適用判断には、同期したRunning・Ready・WaitingのOSトレース、正確なゲームタスクの証拠、ネイティブプロファイラーの観測負荷検証、状態の決定性、再現できる経過時間が必要です。

[上位仕様](../../../docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md)と[計画](../../../docs/superpowers/plans/2026-10-11-synthetic-scheduler-comparison.md)を参照してください。
