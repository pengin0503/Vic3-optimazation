# ベンチマーク

小さなベンチマークのメタデータと、そこから作成した報告を保存するディレクトリです。

生のゲームバイナリ、セーブ、ETLトレースなど、大きなものや権利上の制約がある記録はここにコミットしません。

## 測定ごとの構成

各測定は次の構成を使います。

```text
runs/<run-id>/
  manifest.json
  ticktask_timings.csv
```

`manifest.example.json`からマニフェストを作成し、`research/profiling-plan.md`の手順に従ってください。

すべての測定を解析するコマンドは次のとおりです。

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```
