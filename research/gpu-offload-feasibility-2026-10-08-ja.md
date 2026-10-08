# Victoria 3 1.14.5 — GPU offload オフライン成立性調査 (2026-10-08)

## 判定

**GPU導入による実ゲーム高速化は未実証。** 今回は実ゲームプロセス・GPU計算デバイスに触れず、(1) exact-build の静的証拠との整合、(2) 合成・整数演算カーネルの結果一致、(3) CPU単独実行時間と仮定した往復転送費用の比較を検証した。性能patch、detour、DLL注入、ゲームへの変更は0件。GPUシェーダー/カーネルの実行、PCIe帯域、GPU所要時間は**一切測定していない**。

- 対象: Victoria 3 Windows 1.14.5、`victoria3.exe` SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。今回提供された `Vic3_data.zip` 内実ファイルをストリームでSHA-256計算し照合一致。
- 既存証拠: [深いnative調査](../docs/superpowers/reports/2026-10-05-deep-native-investigation-ja.md)、[OS sampling](os-sampled-capture-2026-10-05-ja.md)、[9回反復](../docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md)。
- 実験のCPU: ホスト `AMD EPYC 9V74`、5論理CPUが見えるLinuxコンテナー (利用者の Ryzen 7 9700X ではない)、Python 3.13 / NumPy 2.3.5 / Numba 0.65.1。JITウォームアップ後11回の中央値、入力生成除外。CPUスレッド1本のJIT kernelとNumPy integer referenceの完全一致を確認。
- 実験環境: `/dev/dri`, `/dev/kfd`, `/dev/nvidia*` なし、Vulkan ICDなし、PyTorch 2.10.0+cpu で CUDA不可。GPUに実行依頼することはできない。
- 再現用ソース: [gpu_feasibility.py](experiments/gpu_offload_spike/gpu_feasibility.py)、[unit tests](experiments/gpu_offload_spike/test_gpu_feasibility.py)、[測定JSON](experiments/gpu_offload_spike/results.json)。合成研究用コードであり、Victoria 3のゲームロジック実装ではない。

## 対象と代替kernel (ゲーム内同等性を主張しない)

| 合成kernel | 演算 | 対応する検討候補 | 注意 |
|---|---|---|---|
| `pop_growth` | 整数rate計算とcap、elementwise | UpdatePopGrowthのような大量独立算術 | 実際のPOP成長式・スクリプト・順序は再現していない |
| `group_sum` | 512グループへの整数加算 | 集計・市場計算一般 | 実ゲームの市場・state数、競合率やfloatの決定性を再現しない |
| `id_lookup` | ID→tableのランダムgatherとlive-bit相当の有効判定 | 雇用、移民などのID/page解決候補 | 実オブジェクトの世代・ポインター・寿命・リセット依存を再現しない |

## 結果 (CPU合成kernel / 仮定転送モデル)

`B = H2D入力 + D2H出力` とし、理想化した転送費用 `T_transfer = B / bandwidth`。`T_cpu` はこの実験のNumba CPU kernel中央値、`T_available = T_cpu - T_transfer - T_fixed` はGPUカーネル・データ変換・結果反映・追加同期などに残された予算。転送帯域12GB/sと24GB/sは**仮定**、`T_fixed=0.1ms` も**仮定**。ゲーム環境での実測ではない。負値はその条件下でGPUカーネルが0msでもCPUより速くなれないことを意味するが、永続GPU常駐や他の条件には一般化できない。

| Kernel | 件数 | 往復MB | CPU JIT ms | 転送12GB/s ms | 残り予算12GB/s + 0.1ms | 残り予算24GB/s + 0.1ms |
|---|---:|---:|---:|---:|---:|---:|
| pop_growth | 100,000 | 1.600 | 0.1630 | 0.1333 | **-0.0703** | **-0.0037** |
| group_sum | 100,000 | 0.804 | 0.0570 | 0.0670 | **-0.1100** | **-0.0765** |
| id_lookup | 100,000 | 1.300 | 0.4707 | 0.1083 | 0.2623 | 0.3165 |
| pop_growth | 1,000,000 | 16.000 | 1.8079 | 1.3333 | 0.3746 | 1.0413 |
| group_sum | 1,000,000 | 8.004 | 0.5815 | 0.6670 | **-0.1855** | 0.1480 |
| id_lookup | 1,000,000 | 13.000 | 6.2800 | 1.0833 | 5.0967 | 5.6383 |

データ11反復中央値で、CPU上のNumPy / Numbaが全サイズ・全kernelで**完全一致**。基本単位、負値拒否、空入力・端点、入力生成の再現性を確認する5つのテストスイートが成功。GPU演算の正しさと実速度については未検証。レコード数・入力表現・転送量は自作の合成仮定であり、Vic3内部配列を直接計測したわけではない。

### 解釈

- 小さい `pop_growth` と `group_sum` は、全データ往復を前提とした例示シナリオではGPU化に不利。整数集計のGPU atomic競合などを加味すると、一般に有利という根拠はない。
- `id_lookup` はCPU合成kernelの計算が相対的に遅く、「転送後にGPUへ残る時間」が正である。ただし**GPUでランダムgatherが速い証拠ではない**。元の1.14.5はID/table/page、世代・有効性、処理順序、object寿命などの未解明事項を含む。CPUのlookup reuseやメモリ局所性改善と比較してから判断する。
- `pop_growth` の100万件以上は成立余地を排除しないが、数値式が変われば結果も変わる。まず実ゲームで独立・大量・転送可能・再現可能なkernelを特定する必要がある。
- ゲーム側の9回TickTask累計は同時実行を含むため、単一kernelを高速化した倍率から3か月経過のwall timeを予測してはいけない。critical path、GPU queue競合、CPU待ちを別測定する。

## 再実行

```sh
python -m pip install numpy numba
cd research/experiments/gpu_offload_spike
python -m unittest discover -p 'test_*.py' -v
python gpu_feasibility.py --sizes 100000 1000000 --repeats 11 --output results-new.json
```

入力は `numpy.random.default_rng(1877)` で固定。計算値・SHAは再現する一方、時間はCPU・OS・電力・負荷に依存する。コンテナーで再実行しても利用者のRX 7800 XTに関する情報は増えない。

## 次の独立検証に必要なもの

1. **GPU runtime 実測**: 利用者のWindows 11 + RX 7800 XTで、GPU compute (例: Vulkan) の合成版とCPU版を同一条件で実行。GPU kernel、H2D/D2H、pack/unpack、submit/synchronizeを個別に記録し、結果は整数exact-match。Native/ゲーム側のpatchではない別プロセスのofflineツール。最低3回、可能なら9回交互順序で測定する。
2. **ゲームへの適用可否**: 実ゲーム内の候補について、workloadサイズ/呼出頻度/CPU実費/critical path/入力のGPU常駐可能性/出力依存を観測。既存の12・16スレッドCPU profilerと同期間の証拠を優先する。
3. **正しさと安全性**: state/checksum、整数/浮動小数演算の決定性、乱数順序、worker同期、multiplayer OOS、セーブ整合性まで確認できるまで置換しない。

現時点で利用者から追加データを送ってもらう必要はない。**実GPUの計算時間を確認する段階では**、RX 7800 XTが稼働するWindows端末でオフライン計測用プログラムを実行してもらい、その出力JSONが必要。ソフトウェア/Windowsでのゲーム操作はこの調査に含めない。
