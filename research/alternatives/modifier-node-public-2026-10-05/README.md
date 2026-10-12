# 保存済みの公開ブランチ版modifier-node解析

出典：`public-architecture-static-followups-2026-10-05`のコミット`21d5fbe0adeb87ab913aec5b7d92e02807b58aef`。

以下の6ファイルは、このフォルダー内で元のリポジトリ相対パスを保持しており、当該コミットとバイト単位で一致します。通常のリポジトリパスには、作業ブランチのコミット`f2e028b56840ae96f2fc08a741331e28cd865f4c`の版を置いています。こちらは完全なグラフフィールド、入力コンテナー・RTTIの出典情報、厳密なRTTIハッシュ検証を保持します。両者は異なるグラフスキーマであり、JSONを相互に置き換えることはできません。

- `research/generated/modifier-node-followup-2026-10-05/artifact-index.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-callgraph.json`
- `research/generated/modifier-node-followup-2026-10-05/modifier-node-selected-regions.json`
- `research/modifier-node-static-analysis.md`
- `research/recipes/reproduce_modifier_node_evidence.py`
- `tests/test_modifier_node_static_followup.py`

再現するには、統合済みリポジトリの独立したコピーを用意し、これら6ファイルをリポジトリルートの対応するパスに上書きしてください。その後、保存済みのテストを`python -m unittest discover -s tests -p test_modifier_node_static_followup.py -v`で実行します。実入力を使うテストも実行する場合は、`VIC3_DATA`に完全に一致する入力ZIPを指定してください。

保存された再現スクリプトとテストは、統合済みツリーの通常の実行対象ではありません。統合コミットは公開ブランチも親として保持しています。
