# GPU合成ベンチマークv2：9700Xの最適化CPU処理とRX 7800 XTの比較

これは**合成データによるオフラインのマイクロベンチマーク**です。Victoria 3のコード変更、プロファイラー、ゲーム内の高速化測定ではありません。v1で報告した合成実験の3.72～9.46倍という速度比は、NumPyとの比較だけであり、GPUへの処理移行の根拠には適しません。

## v2の目的

- CPUの比較対象をNumPy、**Numba JITで融合した直列ループ**、**Numba JITで融合した並列ループ**に分け、OpenCLカーネルと同じ合成整数演算を行います。
- CPU・GPUとも、**cold**（CPUでの入力準備・コピー後に処理）と**resident**（準備済み入力の再利用）を測定します。residentのGPU入力は事前転送済みで、入力転送コストを除外しますが、D2H転送は残ります。residentのCPUも入力準備を除外します。
- 各条件内でCPU・GPUのサンプルを交互に取得し、実行方式とモードの順序を入れ替えます。JITコンパイル、デバイスのメモリ確保、GPUへの事前転送は時間測定の前に行います。
- 反復ごとにGPU・CPU結果の完全一致を検証します。GPU出力のSHA-256、参照出力のSHA-256、GPU検証に成功した反復数を独立して記録します。ハッシュ計算はGPU処理の計測区間外で行います。
- コピーが0バイトより大きいのにOpenCLのH2Dイベント時間が0の場合、無料の転送ではなく**無効な計測**です。JSONには実測したホスト側の投入・待機時間と`h2d.event_status`を残し、すべてのデバイスイベントが正になるまでH2Dのデバイス帯域を`null`にします。
- 監査のため、`session_id`、ドライバー・ソフトウェアのバージョン、各測定の生サンプル、Numbaスレッド数、比較比率を記録します。スキーマはv2です。v1の実行入口と既存の結果フィールドは維持しています。

### H2Dのコピーごとの診断強化（2026-10-12）

各生サンプルは`h2d_device_event_durations_ms`と`h2d_copy_bytes`を保持します。合計が正というだけでは不十分です。0・負・非有限の時間、コピー数・バイト総量の不一致、コピーごとの計測値の欠如があれば、帯域はnullのままです。合計しかない過去のデータでは、個々のコピーの有効性を確認できません。

`zero_duration_events`は影響を受けた反復数、`zero_duration_copy_events`は確認できた0時間のコピー数です。計測値がない場合はnullです。residentで転送がないイベントは対象外です。共通の実行器はv1フィールドを削除せずにこれらを追加しますが、ドライバーの修正や実PCIe帯域の証明ではありません。既存の実機結果の全0時間イベントは、引き続き無効です。

**制約：**Numba JITのマイクロベンチマークはNumPyより適切なCPU比較対象ですが、最適化したネイティブC++や実際のVictoria 3のCPU負荷ではありません。カーネル・データの分離、スケジューリング・依存関係、セーブの決定性、クリティカルパス、ゲームの経過時間、実PCIe帯域は未測定です。ゲーム速度に関する断定はできません。

## Windows PowerShell / RX 7800 XT

統合済みの最新mainを既存のコピーで取得し、実行します。

```powershell
cd $HOME\Desktop\Vic3-optimazation
git fetch origin
git switch main
git pull --ff-only
cd research\experiments\gpu_offload_spike
.\.venv\Scripts\python.exe -m pip install --upgrade numpy numba pyopencl
.\.venv\Scripts\python.exe -m unittest discover -p "test_*.py" -v
```

まだ`.venv`がない場合は、パッケージのインストール前に`py -3 -m venv .venv`で作成してください。

**独立したベンチマークプロセスを3セッション**実行します。ユーザーの環境でのOpenCLデバイス名は`gfx1101`で、v2の既定値です。必要なら`--device-substring`で変更します。

```powershell
1..3 | ForEach-Object {
    .\.venv\Scripts\python.exe gpu_runtime_v2.py --sizes 100000 1000000 --repeats 9 --warmups 2 --numba-threads 8 --device-substring gfx1101 --session-id "session-$_" --output "gpu-results-v2-session-$_.json"
    if ($LASTEXITCODE -ne 0) { throw "GPU benchmark session $_ failed" }
}
```

確認するファイルは`gpu-results-v2-session-1.json`、`gpu-results-v2-session-2.json`、`gpu-results-v2-session-3.json`です。ゲームログ、実行ファイル、セーブなどのVictoria 3データは不要です。

## 出力の読み方

条件が一致するcold CPU・cold GPU、またはresident CPU・resident GPUの比率を使います。

- `modes.cold.ratio_vs_numba_serial_cpu_cold`
- `modes.cold.ratio_vs_numba_parallel_cpu_cold`
- `modes.resident.ratio_vs_numba_serial_cpu_resident`
- `modes.resident.ratio_vs_numba_parallel_cpu_resident`

比率 = CPU中央値 / GPU中央値です。1より大きければ、その合成条件ではGPUが速いことを示します。`numba_threads: 8`はNumba並列ワーカーの要求スレッド数であり、CPUの物理コア数を変えません。

`h2d.host_phase_median_ms`は、転送区間の投入から待機完了までの経過時間です。`h2d.zero_duration_events`は、コピー量が0でないのにGPUイベント時間が0という無効な計測を記録します。AMDの過去のv1結果では、H2Dデバイスイベント時間はすべて0でした。v2は原因が解消したとは扱いません。イベント計測の意味や、ドライバーによるホスト側の一時保持が原因の可能性があり、実GPUでの追加診断が必要です。このホスト時間は、純粋なPCIe転送時間とは限りません。

`gpu_output_sha256`は、毎反復でGPUから返された配列から計測後に求めます。期待値は同じ行の`reference_output_sha256`です。データ、型、形状のいずれかが異なれば、成功結果を返さず、終了コード2と`status=error`で失敗します。

このベンチマークはVictoria 3を検証・高速化しません。次の開発条件は、1.14.5のクリティカルパスから、GPUで安全に処理できる有意なネイティブタスクを独立して復元することです。
