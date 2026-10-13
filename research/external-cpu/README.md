# 外部CPU計測packet

2026-10-13。すべて未測定。現在の操作手順は[日本語ガイド](../../docs/guides/vic3-external-cpu-measurement-ja.md)。

- `matrix.json`: 12thread、B1/S1/S2/B2/B3/S3の順序。本計測6件。
- `run-templates/`: 既存generatorで作ったtemplate。未知のMOD/rules/speed、PID、overhead等はnull。runtimeの値を確認してからlocal copyへ記入する。
- `employment-lookup-catalog.json`: 保存済み雇用証拠から生成した2件の限定excerpt。既存42対象とは別に照合する。
- `offline-verification.json`: 添付bytesと合成workflowの今回の確認結果。実機計測ではない。
- `offline-verify-source.py.txt`: 確認に使ったLinux研究recipeの写し。製品toolではない。

recipeを再現する場合はrepoの`.superpowers/sdd/2026-10-13-external-cpu-route/verify_packet.py`へコピーし、repoの親の`project_sources/01-Vic3_data.zip`を配置して`python .superpowers/sdd/2026-10-13-external-cpu-route/verify_packet.py`を実行する。Capstone等の既存解析dependencyが必要。recipeは一時directoryで合成CSVを使い、packetのbyte不変を確認し、`offline-verification.json`を再生成する。別入力や実ゲーム結果を受け入れる汎用gateではない。

ここに実CSV/ETLを置かない。実測はGit対象外の`raw-captures/external-cpu/`へコピーしてから行う。prepared templateを`manifest.json`と呼び替えて実測済みにしない。
