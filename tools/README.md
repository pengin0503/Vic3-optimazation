# ツール

現在のVictoria 3診断は `Invoke-Vic3Diagnostics.ps1` を固定入口として使用します。[手順・結果判定](../docs/guides/vic3-diagnostics-ja.md)を参照してください。sourceと検証済みLoaderを照合し、既定では読み取り専用診断だけを実行します。

### `map_native_callers.py`

`requirements-callgraph.txt`にある任意依存のCapstoneが必要です。指定した実行ファイルRVA 1～32件へのE8 rel32呼び出しを検索し、アンワインド範囲の境界から始めたデコードで一致を検証します。デコード不能・処理上限到達の候補は未解決のまま保持し、他の命令の内部にあるオペコードのバイト一致を拒否します。間接呼び出し元と末尾ジャンプは対象外です。

```text
python tools/map_native_callers.py <Vic3_data.zip> --target range=0x7dbaa0 --target heuristic=0x7db150 --expected-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54 --output local-data/callers.json
```

[ディスパッチの再現スクリプト](../research/recipes/reproduce_dispatch_evidence.py)で、このビルドの選定済みコールバック・ディスパッチ処理の証拠を再現できます。[結果](../research/ticktask-dispatch-static-map.md)も参照してください。

特記がなければ、リポジトリ側の研究ツールは追加依存なしのPython 3です。ローカルのVictoria 3インストールまたは提供された研究用ZIPを対象に動作します。統合入力の保存方針は、ルートREADMEと`research/input-data-manifest.md`を参照してください。

## オフラインの静的解析

### `run_static_pipeline.py`

主要な静的調査を1つのコマンドで実行します。

```text
python tools/run_static_pipeline.py C:\path\to\Vic3_data.zip out\static \
  --signature-manifest research/generated/exact-signatures-1.14.5.json
```

出力：

- `static-analysis.json`
- `static-xrefs.json`
- `ticktask-rtti.json`
- `signature-validation.json`（シグネチャのマニフェストを指定した場合）
- `summary.json`

シグネチャ検証が失敗すると、0以外の終了コードを返します。

### `analyze_vic3.py`

追加依存なしでPE・静的メタデータを抽出します。

```text
python tools/analyze_vic3.py C:\path\to\Vic3_data.zip \
  --output research/generated/static-analysis-local.json
```

抽出対象：

- SHA-256
- PEのメタデータとセクション
- インポート・エクスポートテーブル
- 埋め込まれたPDBパス
- ソースパスの文字列
- `CTickTask_*`名
- タスク・ジョブ・並列処理関連のRTTI文字列
- プロファイラー・コンソールコマンドの識別子

### `map_static_xrefs.py`

選択したASCIIアンカーを、x64のRIP相対コード参照の候補とPEの`.pdata`関数範囲に対応付けます。

```text
python tools/map_static_xrefs.py C:\path\to\Vic3_data.zip \
  --output out\static-xrefs.json
```

生のdisp32一致には誤検出があり得ます。重要な候補の意味を決める前に、実際の逆アセンブラーで検証してください。

### `map_ticktask_rtti.py`

具体的なTickTaskクラスのMSVC x64 RTTI、Complete Object Locator、仮想関数テーブルを復元します。

```text
python tools/map_ticktask_rtti.py C:\path\to\Vic3_data.zip \
  --output out\ticktask-rtti.json
```

1.14.5では具体的なTickTaskクラス258件を対応付けます。最後の仮想スロットは`task_specific_tail_vfunc`として記録し、ソースコード上のメソッド名を推測で付けません。

### `generate_signatures.py`

既知のRVA付近で、対象ビルドに限定した最短の一意なバイト範囲を生成します。

```text
python tools/generate_signatures.py C:\path\to\Vic3_data.zip \
  --target employment=0x13b8310
```

シグネチャは、実行ファイルのハッシュ一致を確認した後に使う二次検証です。バージョンをまたいで使うシグネチャではありません。

### `validate_exact_signatures.py`

対象ビルドのシグネチャマニフェストを、安全側に倒して検証します。

```text
python tools/validate_exact_signatures.py \
  C:\path\to\Vic3_data.zip \
  research/generated/exact-signatures-1.14.5.json
```

確認項目：

- 実行ファイルのSHA-256の完全一致
- 期待するRVAのパターンバイト
- `.text`内の期待出現数

### `compare_static_analysis.py`

Victoria 3の更新時に、2つのビルド解析結果を比較します。

```text
python tools/compare_static_analysis.py old.json new.json \
  --before-rtti old-rtti.json \
  --after-rtti new-rtti.json \
  --output migration.json
```

実行ファイルのハッシュが変われば、文字列やRTTIが同じに見えても、移行判断は必ず`revalidate-all-native-targets-before-enabling-hooks`（フックの有効化前にすべてのネイティブ対象を再検証）になります。

### `extract_performance_controls.py`

性能に関係する既知のdefine値と、同梱された周辺コメントを抽出します。

```text
python tools/extract_performance_controls.py C:\path\to\Vic3_data.zip \
  --output out\performance-controls.json
```

値は因果関係を検証するための調整項目であり、自動的な推奨設定ではありません。更新頻度、検索範囲、Pop統合の変更はシミュレーションの動作を変える可能性があります。

## ベンチマークの準備

### `prepare_benchmark_matrix.py`

未測定のものを有効な測定データとして扱わず、Phase 1の全測定条件を作成します。

```powershell
python tools/prepare_benchmark_matrix.py benchmarks/runs `
  --threads 1,2,4,6,8,12,16 `
  --repeats 3 `
  --start-date 1900-01-01 `
  --end-date 1901-01-01 `
  --save-filename heavy-save.v3 `
  --save-sha256 <64-hex-save-hash> `
  --country JAP `
  --pop-consolidation moderate_consolidation
```

既定ではスレッド数ごとにウォームアップ1回と測定3回、合計28個の測定テンプレートを作成します。

各測定には、最初は`manifest.json`ではなく`manifest.template.json`を生成します。空でない出力ディレクトリへの書き込みは拒否します。

### `finalize_benchmark_run.py`

測定で`ticktask_timings.csv`が生成された後に実行します。

```powershell
python tools/finalize_benchmark_run.py `
  benchmarks/runs/vanilla-t08-r01 `
  --wall-clock-seconds 123.456
```

`manifest.json`の作成前に、次の必須列を確認します。

- `frame`
- `task`
- `milliseconds`
- `calls`
- `longest_lock`

CSVのSHA-256、バイトサイズ、行数も記録します。

## ベンチマークの品質検査

### `check_benchmark_quality.py`

性能差を解釈する前に、測定一式を検証します。

```text
python tools/check_benchmark_quality.py benchmarks/runs \
  --matrix benchmarks/runs/matrix.json \
  --json benchmarks/quality.json \
  --markdown benchmarks/quality.md \
  --require-performance-ready
```

測定IDの重複・欠如、測定条件のスレッド数・反復数・ウォームアップの不一致、ビルド・セーブ・Pop統合の整合性、TickTask CSVの存在とSHA-256、最小反復数、経過時間の変動係数、外れ値を検査します。

`valid`は測定一式に整合性エラーがないことを意味します。`valid_for_performance_claim`はより厳しく、再現性を未評価の場合、時間のノイズや外れ値が設定したしきい値を超える場合はfalseです。そのため、単発測定を安定性の証拠として扱いません。

負荷の測定境界を確認するため、すべてのTickTask CSVについて、`frame`、`task`、`calls`列だけから決定的なフィンガープリントを作ります。フレーム数、最小・最大フレーム、ソート済み`(frame, task, calls)`の重複を含む集合のSHA-256を使います。`milliseconds`と`longest_lock`は測定値なので除外します。

スレッド数や構成の違いも含め、1つの報告内のすべての測定を最頻のフィンガープリントと比較します。同数の場合は最初の測定IDを採用します。スレッド数の比較やプロファイラー有効・無効の比較では、同じシミュレーション負荷が必要なためです。不一致の場合、測定名と両方の境界要約を含む`workload_boundary_mismatch`警告を出し、`valid_for_performance_claim`をfalseにします。

測定ごとのフィンガープリントは`workload_boundaries`に記録します。読めないCSVは`invalid_ticktask_csv`エラーです。保存済みの3か月・9回の反復測定では、他の8回より3フレーム長い`repeat-t12-r02`が検出されます。

## ベンチマークの解析

### `analyze_benchmarks.py`

```text
python tools/analyze_benchmarks.py benchmarks/runs \
  --json benchmarks/report.json \
  --markdown benchmarks/report.md
```

報告する項目：

- TickTaskの累積コスト
- 呼び出し回数
- レコードの最大時間
- 観測した最長のロック
- 測定間の変動係数
- TaskThreadCountによるスケーリング
- 後続の変更版と標準版の比較

1つの時間指標だけから因果関係を断定しません。

### `analyze_thread_scaling.py`

スレッド数増加の効果を慎重に診断します。

```text
python tools/analyze_thread_scaling.py benchmarks/report.json \
  --json benchmarks/scaling.json \
  --markdown benchmarks/scaling.md
```

出力する項目：

- TaskThreadCountを増やす各段階での追加効果
- 1スレッドの基準に対する並列効率
- アムダール則に基づく実効的な直列部分の割合
- 設定可能な頭打ちの判定

アムダール則の値は診断用です。TaskThreadCountはVictoria 3の総スレッド数ではなく、ロック・スケジューラー・メモリの影響により理想的なアムダール則の前提は成立しません。

### `triage_benchmark_targets.py`

実測の高コスト箇所と静的なTickTask RTTIマップを結び付けます。

```text
python tools/triage_benchmark_targets.py \
  benchmarks/report.json \
  out/static/ticktask-rtti.json \
  --threads 8 \
  --json benchmarks/native-targets.json \
  --markdown benchmarks/native-targets.md
```

`UpdateEmployment`などの測定行を、取得できる場合は具体的なTickTaskクラスと静的なネイティブ末尾関数アンカーに変換します。

ベンチマーク後の解析対象を絞るものであり、パッチの安全性を認定するものではありません。

## テスト

リポジトリのテスト一式を実行します。

```text
python -m unittest discover -s tests -v
```

ローカルの1.14.5入力を使う任意の統合テスト：

```powershell
$env:VIC3_DATA = "C:\path\to\Vic3_data.zip"
python -m unittest discover -s tests -v
```

GitHub Actionsは任意依存の呼び出しグラフ解析ライブラリをインストールし、mainへのpushとプルリクエストで単体テストを実行します。バイナリを使う統合テストには、ローカルで提供する`VIC3_DATA`入力が必要です。

## 2026-10-05：元資料に基づく追加調査

`map_ticktask_rtti.py`は最初の断片を`tail_runtime_function`として保持し、ルートの3要素、連鎖した断片、互いに重ならない範囲、バイト数、不正メタデータの明示的な状態を含む`tail_function_group`を追加します。共有アンワインドレコードを理由に無関係な関数をまとめません。範囲重複、循環、不正・切り詰められた連鎖は安全側に倒して拒否します。

ベンチマーク・スケーリング形式v2では、変動係数が不明な場合に`noisy=null`を使います。`repeatability_assessed`には3件以上の観測と利用可能な変動係数が必要で、低い変動係数は統計的有意性を意味しません。変動係数が不明な古い報告から頭打ちを確定できません。過去のJSONは変更せず、更新するには生CSVから再実行します。

任意の`map_hotspot_calls.py`は、選択したRTTIアンカーから範囲を限定した静的候補グラフを作り、実行ファイルとRTTIの両方のハッシュで保護します。このツール用に`python -m pip install -r tools/requirements-callgraph.txt`を実行してください。

直接呼び出し、末尾ジャンプ候補、コードアドレス候補、参照された呼び出し可能な仮想関数スロット、未解決の間接位置を区別します。これはメタデータ範囲を線形にデコードする処理であり、実行時の到達可能性やタスク依存関係の復元ではありません。

コマンドと検証は[続行報告](../docs/superpowers/reports/2026-10-05-source-backed-continuation-ja.md)を参照してください。

## TickTaskの依存関係の証拠

`map_ticktask_dependencies.analyze_dependency_evidence`は、1.14.5の完全に一致するハッシュと、Graph/Listの検証済みアンワインドグループを使います。深さは最大3、関数は最大256、グループごとに最大64 KiBです。直接呼び出し、末尾ジャンプ、間接位置、RIP相対参照を分けて保持します。呼び出しや共有ヘルパーは、タスク依存関係の証拠ではありません。

## OSプロファイルCSVの正規化

`python tools/normalize_os_profile.py EXPORT.csv --mapping MAPPING.json --run-id RUN --source TOOL --output PROFILE.json`

`research/os-profile-normalized-schema.md`を参照してください。すべての時間列には明示的な単位が必要です。エクスポート列は測定者が指定し、推測しません。

`python tools/correlate_os_profile.py PROFILE.json --catalog research/generated/native-target-catalog-1.14.5.json --expected-run-id RUN --output CORRELATION.json --markdown CORRELATION.md`

範囲は半開区間です。基準アドレスの欠如、不正なアドレス、異なるモジュール、一致なし、曖昧な重複も報告します。曖昧な行はどの対象にも加算しません。観測された指標だけを合計し、`metric_observations`で各指標の取得範囲を示します。結果は静的アドレスの対応関係であり、ロックやクリティカルパスの因果関係ではありません。

実エクスポートの全手順は`research/os-profiling-plan.md`にあります。対応付けテンプレートには置換用の仮値があり、ベンダー検証済みではありません。測定マニフェストを保持し、不一致・不正・曖昧な行を確認してください。

## ネイティブプロファイラーの参照パーサー（オフライン専用）

`python tools/parse_native_profiler_trace.py TRACE.bin --expected-executable-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54 --output PARSED.json`

ヘッダー・ビルド・対象メタデータは安全側に倒して検証し、未知の種類は読み飛ばして報告し、不正なレコード境界ではその区間の解析を停止します。CLIの終了コードが0でも、スレッド内の開始・終了の対応付け診断、連番の欠落、破棄イベント数を確認する必要があります。0は有効なヘッダーと完全な区間を意味します。

`duration_ns_floor`はQPCを整数変換して切り捨てた値で、`duration_qpc`が正式な値です。Pythonコーデックはテストデータ生成器であり、高頻度処理向けの書き込み実装やC++リングバッファの証明ではありません。
