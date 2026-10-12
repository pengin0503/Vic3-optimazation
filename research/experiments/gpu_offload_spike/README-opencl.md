# Victoria 3 GPU処理移行の研究：単独で動作するOpenCLベンチマーク

> **2026-10-08の更新：**これは保存済みの**v1**とNumPyの比較を説明する文書です。Numbaで最適化したCPUとの比較と、RX 7800 XTでの3セッションの測定は[README-v2.md](README-v2.md)を参照してください。ゲーム性能の改善は実証していません。

**合成実験であり、Victoria 3の処理ではありません。ゲーム、セーブ、ローダー、DLL注入、ネイティブパッチ、プロセス接続は使いません。**

Issue #12では、同じWindows PC上で、独立した整数カーネルを**実機のRX 7800 XT**で実行すると、処理全体を通じてNumPyより速くなるかを調べます。PR #13のCPUのみの理論調査を引き継ぐものです。GPU演算にはVulkan compute相当の手段としてOpenCL 1.2を使い、Vulkan SDKは不要です。

## Windows 11 / RX 7800 XT

1. OpenCL対応のAMD Radeonドライバーと、Python 3.11以上のx64版をインストールします。
2. v1ベンチマークはPR #13・#14でmainに統合済みです。既存のコピーでは最新mainを取得します。

```powershell
git switch main
git pull --ff-only
```

3. リポジトリルートからPowerShellで実行します。

```powershell
cd research\experiments\gpu_offload_spike
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install numpy numba pyopencl
.\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py' -v
.\.venv\Scripts\python.exe gpu_runtime.py --list-devices --output gpu-devices.json
.\.venv\Scripts\python.exe gpu_runtime.py --sizes 100000 1000000 --repeats 9 --warmups 2 --device-substring gfx1101 --output gpu-results-local.json
```

4. レビューが必要な場合は、`gpu-results-local.json`と`gpu-devices.json`だけを共有してください。デバイス・OSの情報と合成入力のハッシュ・時間を含みますが、ゲームデータは含みません。

既定では、名前に`7800`を含むOpenCL GPUが**厳密に1台**あることを要求します。CPUドライバー、実行環境の欠如、対象の曖昧さ、カーネルのビルド失敗、結果の不一致は拒否します。名前が異なる場合は`gpu-devices.json`を確認し、一意に一致する部分文字列を指定してください。PyOpenCLだけをインストールしても、AMDドライバーやOpenCL ICDはインストールされません。

別の環境で新しいCPUのみの単体テストを実行するには`pip install numpy`で足ります。既存のPR #13のCPU研究テストには追加で`numba`が必要です。新しいテストにはGPUは不要です。対象GPUがない場合、GPUのCLIは終了コード2と`gpu_executed: false`を含むエラーJSONを返します。

## 測定するもの

- **処理：**64ビットの中間値を使う合成整数の要素別演算`pop_growth`と、ランダムなテーブル参照を使うマスク付き`id_lookup`です。実際のVictoria 3の数式・オブジェクトではありません。
- **条件：**ランダム、衝突多数、マスク付き、大きな整数の境界です。件数は100,000・1,000,000、シードは1877です。
- **cold：**各反復でCPU入力を整え、H2D転送、OpenCL実行、D2H転送、合成CPU配列コピーによる結果適用を行います。
- **resident：**測定開始前にバッファへ1回転送し、各反復で実行とD2H出力コピーを行います。H2Dの初期準備は時間から除外し、CPUへの結果適用は含みます。機会の上限を探る条件であり、初回使用を含む処理全体の性能を示すものではありません。
- `*_host_submit_ms`、`*_host_wait_ms`：OpenCLへの投入と完了待ちの前後で測ったホスト側の経過時間です。純粋なデバイス処理時間ではありません。
- `*_device_event_ms`：H2Dコピー、GPUカーネル、D2HのOpenCLイベント計測値です。**ホストとデバイスの時間は重なっているため、合計してはいけません。**
- `e2e_wall_ms`：入力準備開始から模擬的な結果適用完了までのホスト経過時間です。Python・ドライバー・待機の負荷を含み、テストデータ生成、プログラムコンパイル、GPUメモリ確保、結果検証は含みません。
- `cpu_e2e_median_ms`：同じデータをNumPyの参照処理で扱い、入力準備と結果適用コピーも含めた時間です。Victoria 3のネイティブCPU性能ではありません。
- `observed_*_device_gb_per_s`：コピーしたバイト数をデバイスイベント時間で割った値です。PCIe自体の帯域を直接測定したものではありません。

すべての反復で、型・形状も含めCPU参照結果との完全一致を検証します。不一致があれば、有効なベンチマークJSONを出さず停止します。各条件でウォームアップとcold・residentを交互に行う9回の反復を実施し、生の時間サンプルと中央値を出力します。テストの偽バックエンドは実行順序の制御だけを検証します。実測JSONで`gpu_executed`がtrueになるのは、実際のOpenCL実行器が正常に動いた場合だけです。

## 検証と制約

実装時の環境には利用できるOpenCL GPUがありませんでした。新しいCPU・制御テスト12件、両OpenCL 1.2カーネルのClang構文検査、デバイスがない場合のエラー経路を検証しました。その環境では物理GPUの処理量や実行時間を測定していません。

合成実験での速度比は、Victoria 3 1.14.5のゲーム性能改善を証明しません。ネイティブ処理の置き換えには、タスクのクリティカルパス、入力の所有権、決定的な順序、オブジェクト寿命、再現性、マルチプレイ状態の検証が引き続き必要です。

- [PyOpenCLのインストール資料](https://documen.tician.de/pyopencl/misc.html#installation)
- [OpenCLイベント計測の資料](https://github.com/KhronosGroup/OpenCL-Docs)
