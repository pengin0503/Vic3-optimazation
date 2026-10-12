# ネイティブソース

Victoria 3 Windows 1.14.5向けの**Task 9：読み取り専用ネイティブ計測の試作**は実装済みです。実ゲームへの接続、観測負荷、安定性の検証は未完了です。以下の操作ガイドとローダー診断を参照してください。

Task 9の着手条件は、反復ベンチマークの基準測定とPR #11のOSサンプリング・ネイティブ実行の証拠により満たされました。承認済みの実行時計測計画と関連資料は次のとおりです。

- [実行時計測の計画](../docs/superpowers/plans/2026-10-05-read-only-native-profiler-runtime.md)
- [実行時計測の対象](../research/native-profiler-runtime-targets-1.14.5.json)
- [フックのABI](../research/native-profiler-hook-abi-1.14.5.md)
- [イベント形式](../research/native-profiler-event-format.md)

最初のネイティブ構成要素は、対象ビルドに限定した接続ローダーと観測専用のプロファイラーDLLです。未対応のビルドは、安全側に倒して拒否する必要があります。

## 構成

- `native/CMakeLists.txt`：Windows x64専用です。他の環境では明確なメッセージで構成処理を停止します。C++20と共有CRTを使用します。MinHookはCMakeの`FetchContent`でコミット`c3fcafdc10146beb5919319d0683e44e3c30d537`を取得し、ソースからビルドします。第三者のバイナリは同梱しません。ライセンスは`third_party/licenses/MinHook.txt`です。
- `native/generated/targets_1_14_5.inc`：生成ファイルのため手編集しません。`python tools/render_native_profiler_targets.py`で再生成できます。`--check`はコミット済みファイルが古い場合に失敗します。維持する元データは`research/native-profiler-runtime-targets-1.14.5.json`のみです。生成ツールは、固定した3つの末尾アンカー以外、6以外のスロット、一意でない宣言済み一致件数、不正な16進範囲、矛盾するシグネチャオフセットを拒否します。

ゲーム状態を変更する最適化パッチ、スケジューラーの上書き、ロックの除去、更新頻度の変更、根拠のない並列化をここに追加してはいけません。Task 11・12には、Task 9の実行時観測負荷・相関と、CPU処理・待機・クリティカルパスに関する残りの証拠が必要です。

## オフライン検索再利用コア（`src/lookup_reuse/`）

[`lookup_reuse/`](lookup_reuse/README.md)は、独立したプラットフォーム共通のC++20静的ライブラリ、テスト、オフライン実行ツールです。[検索再利用・シャドウ比較の設計](../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)のStage Aにあたります。所有する不変の合成テーブルだけを扱い、シャドウモードでも元の検索を必ず呼びます。最適化モードはありません。ネイティブローダー、DLL、フック、実プロセスメモリ、V3PF v1プロファイラー形式をビルド・操作せず、Task 9の実行時計測計画には含まれません。ネイティブ側のシャドウ比較（Stage B）には、設計の第8節に記載した証拠が引き続き必要です。

## オフラインのネイティブシャドウ契約（`src/lookup_reuse_contract/`）

[`lookup_reuse_contract/`](lookup_reuse_contract/README.md)は[オフラインのネイティブシャドウ契約設計](../docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md)のB0です。Stage A上に構築した、プラットフォーム共通のC++20ライブラリ、テスト、固定シードの実行ツールです。対象ビルドに限定したオフラインの位置特定、ネイティブ構造に似せた所有テストデータ、不透明な結果値の正規化、元の処理を厳密に1回呼ぶシャドウ比較を扱います。実プロセスメモリの読み取り、フックの導入、ローダー・DLL・V3PF形式の変更は行わず、Stage Bのネイティブ処理の着手条件を満たすものではありません。

## 読み取り専用ネイティブ実行部（`src/native/`）

`native/`に、完全に一致するVictoria 3 1.14.5向けの読み取り専用試作を実装しています。Visual Studio 2022・x64・Releaseで構成、ビルド、CTestを実行してください。共有CRTを使うため、Visual C++ 2022 x64ランタイムが必要です。

ローダーは`--pid`を必須とし、未知のビルドをDLL注入前に拒否します。DLLは独立した検証の完了後だけ3つの末尾アンカーを観測し、`--disabled`ではフック数が0になります。終了には`--stop --pid`を使います。DLLとトランポリンはプロセス終了まで保持し、再測定はゲーム再起動から行います。[操作ガイド](../docs/superpowers/guides/2026-10-05-native-profiler-runtime-validation-ja.md)と[実装の引き継ぎ](../docs/superpowers/reports/2026-10-05-native-profiler-runtime-implementation-handoff-ja.md)を参照してください。

ローダー診断は[モジュール解決の診断記録](../docs/superpowers/reports/2026-10-06-loader-module-resolution-diagnostics-ja.md)を参照してください。合成テスト用ホストへの接続成功は、実ゲームへの接続成功を証明しません。

Phase 3では[オフラインのモジュール・エクスポート検証規則と失敗時の回帰テスト](../docs/superpowers/reports/2026-10-11-offline-native-diagnostics-phase3-ja.md)を追加しました。診断v2は不完全なモジュール列挙を拒否し、DLL注入前にエクスポート先の16バイト全体を検証します。[実行38148690363](https://github.com/pengin0503/Vic3-optimazation/actions/runs/38148690363)でWindows x64 Releaseビルドと合成CTest全10件が成功しました。名前付きIPC、既存ホストへのDLL注入、安全側に倒すDLLのライフサイクル、MinHookを含みます。実ゲーム接続時のコード4と、DLLを完全に有効化したセッションの停止・終了処理は未検証です。Windowsジョブは`tests.yml`と`native-validation.yml`で共有し、研究ブランチへのpushではネイティブ関連のパスが変わった場合だけ実行します。

所有するPE・モジュール・バッファ・フックのテストは、ゲーム、Windowsローダー・DLL、MinHookなしで、64ビット環境から個別に実行できます。

```sh
cmake -S src/native/tests/offline -B build/native-offline
cmake --build build/native-offline --config Release
ctest --test-dir build/native-offline -C Release --output-on-failure
```

この実行方法は、`src/native`のWindows x64 CTestや実ゲームの検証条件を代替しません。

Phase 4では読み取り専用の[実行時証拠の監査ツールと引き継ぎ](../docs/superpowers/reports/2026-10-12-cpu-runtime-evidence-gate-ja.md)を追加しました。現在の13成果物の一覧は出典を検証できますが、ゲームのネイティブ記録は0件です。実行時の受け入れ判定は未達で、観測負荷はnullのままです。[記録手順](../docs/superpowers/guides/2026-10-12-phase4-runtime-evidence-handoff-ja.md)を参照してください。準備完了の判定は整合性の検査であり、性能パッチの許可ではありません。

[非ゲーム作業の完了記録](../docs/superpowers/reports/2026-10-12-offline-closeout-ja.md)には、パーサーの構造化された拒否診断、間接命令40件すべての証拠、明示的に未測定としたGPUライフサイクルの転送量モデルを保存しています。現在の成果にはGPU v2とH2Dのコピーごとの診断修正も含みます。[全体ロードマップ](../docs/superpowers/guides/2026-10-12-project-roadmap-ja.md)を参照してください。ゲーム・ネイティブ性能の証拠条件は統合後も変わりません。
