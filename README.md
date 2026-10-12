# Vic3-optimazation

Victoria 3のシミュレーション性能を、通常のスクリプトやdefineの調整を超えて改善するための研究プロジェクトです。

プロジェクト全体の状況は[2026-10-12のロードマップ](docs/superpowers/guides/2026-10-12-project-roadmap-ja.md)と[非ゲーム作業の完了記録](docs/superpowers/reports/2026-10-12-offline-closeout-ja.md)を参照してください。現在の成果にはオフラインCPU研究、GPU v2、診断修正を含みます。過去の進捗より新しい報告を優先してください。実ゲームへの接続、観測負荷、同期した実行時証拠の受け入れ判定、ネイティブ処理の高速化は引き続き未検証です。

実ゲーム検証は[最初の検証手順](docs/superpowers/guides/2026-10-12-user-game-validation-first-pass-ja.md)から始めてください。

Issue #17のLoadLibraryW不一致に対し、fail-closedを維持した[読み取り専用診断](docs/superpowers/guides/2026-10-12-loader-readonly-diagnosis-ja.md)を追加しました。[方式比較・実装結果](docs/superpowers/reports/2026-10-12-loader-readonly-byte-mismatch-ja.md)を参照し、次回は注入せず同じPIDの証拠を取得してください。接続成功は未確認です。

## 追加測定なしで進めるCPU研究（2026-10-11）

[オフラインCPU研究の仕様](docs/superpowers/specs/2026-10-11-offline-cpu-research-design.md)、[TickTask調査の引き継ぎ](docs/superpowers/reports/2026-10-11-offline-cpu-research-handoff-ja.md)、[証拠ゲートのレビュー](docs/superpowers/reports/2026-10-11-offline-cpu-gate-review-ja.md)に、読み取り専用の研究を記録しています。[未解決の依存関係を分類するツール](tools/triage_ticktask_unresolved.py)と[単独で動作する合成DAGスケジューラー実験](research/experiments/scheduler_model/README.md)は、ゲームを起動せずに実行できます。いずれも研究の補助であり、ネイティブ処理の最適化、ゲームのCPU使用率の変化、ゲームの高速化を実証したものではありません。初期の個別検証ではTickTask分類7件、合成スケジューラー11件のテストが成功しました。その後の検証状況は上記の新しい報告を参照してください。

## 現在の状態

[追加測定なしでの雇用処理の検索再利用調査（2026-10-07）](docs/superpowers/reports/2026-10-07-offline-employment-optimization-ja.md)では、同一項目のID配列検索箇所を4か所に拡張し、処理前のリセット順序と代替経路の初期化を維持したうえで、検証済みの正のスロット位置を記憶する方式を使い捨ての合成モデルで調べました。モデルの9件のテストと25,676回の比較は研究上の証拠であり、ゲームの最適化、ネイティブ処理との同等性、高速化は実証していません。

[検索再利用・シャドウ比較の設計](docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)はユーザー承認済みです。[Stage Aの実装計画](docs/superpowers/plans/2026-10-06-offline-lookup-reuse-core.md)に沿って、移植可能なオフラインコアを[`src/lookup_reuse/`](src/lookup_reuse/README.md)に実装しました。所有・検証済みの合成テーブル、1件の正のスロット位置ヒント、元の検索を必ず呼び、その結果を返すシャドウ評価器を備えます。固定シードの実行（[結果](research/generated/lookup-reuse-core/results.json)、[検証記録](research/generated/lookup-reuse-core/verification.md)）では、2,004個の合成スナップショットと32,948件の検索で、存在判定・スロット・シャドウ比較の不一致は0件でした。これは合成検索の件数であり、処理時間でも、ネイティブ処理との同等性やゲーム高速化の証拠でもありません。ネイティブ側のシャドウ比較には、対象、ABI、寿命、プロファイラーの観測負荷に関する証拠が必要です。この設計は検索の省略や最適化モードを許可していません。

[Stage Bの準備とゲートレビュー（2026-10-07）](docs/superpowers/reports/2026-10-07-native-shadow-preparation-ja.md)では、対象ビルドに限定した検索入口のシグネチャ、呼び出し元・戻り先4か所の証拠、対象外の呼び出し元2か所、範囲を限定して再現できる静的証拠を追加しました。当時のレビューに登場する別のネイティブ実行ブランチは、その後mainに統合されています（[ブランチ統合記録](docs/superpowers/reports/2026-10-07-branch-integration-ja.md)）。実テーブルの寿命、ワーカーのスコープ、実ゲームでの動作検証が未解決のため、ネイティブ側のシャドウ比較は引き続き着手条件を満たしていません。

[B0オフライン接続契約の設計](docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md)は承認済みで、[4タスクの実装計画](docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md)を[`src/lookup_reuse_contract/`](src/lookup_reuse_contract/README.md)に実装しています。オフラインの位置特定、所有するテスト用データと不透明な結果値の正規化、元の処理を厳密に1回呼ぶシャドウ比較、固定シードの実行ツール、GCC・Clang・MSVCのCIを含みます。[B0の検証記録](research/generated/lookup-reuse-contract/verification.md)を参照してください。B0の検証対象は所有するテスト用データのみであり、ネイティブ処理の着手条件を満たすものではありません。

測定結果の入口は[反復ベンチマーク分析（2026-10-05）](docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md)です。次のネイティブ最適化調査には[詳細調査と引き継ぎ](docs/superpowers/reports/2026-10-05-deep-native-investigation-ja.md)を参照してください。対象ビルドに限定した経済処理の候補6件、分類済みの同期処理の証拠、一次資料8件、再現手順を追加していますが、実行時のボトルネックや高速化はまだ実証していません。

[最初のOS記録の試行](research/os-capture-attempt-2026-10-05-ja.md)では、37.53秒の記録と対応する368フレームのTickTask CSVを保存しましたが、トレースで43,082イベントが欠落しました。[2回目のCPUサンプリング記録と引き継ぎ](research/os-sampled-capture-2026-10-05-ja.md)では欠落イベント0件で保存でき、実ゲームのサンプル・スタックから、下流のID・テーブル・ページ、一時メモリ、雇用準備処理の候補を観測しました。測定者の報告は48.46秒ですが、対応するTickTask CSV、正確なゲーム進行の測定境界、ゲーム終了の理由は未確認です。これらは実行の証拠であり、ボトルネックや高速化の確定ではありません。

過去の[OS記録の準備と手順](research/os-capture-preparation-2026-10-05-ja.md)には、下流のネイティブ範囲42件と未測定のテンプレート8件があります。[専用WPRプロファイル](research/vic3-focused-cpu.wprp)はCPUサンプリングとスケジューリング診断を分離します。名前付きセッションにはWindowsの管理者権限が必要で、現在継続中の記録はありません。生のETLやシステム全体のエクスポートはローカルに留め、ゲームに絞った集計、限定的な証拠、再現手順、ハッシュを保存しています。[オフライン実装の引き継ぎ](docs/superpowers/reports/2026-10-05-offline-three-plan-handoff-ja.md)は、静的解析・OS解析・プロファイラー関連ツールの入口です。

読み取り専用のネイティブプロファイラーDLLと、PIDを明示するローダーは実装済みです。実ゲームへの接続、観測負荷、安定性は未検証です。ネイティブ性能パッチ、スケジューラーの上書き、シミュレーション状態の変更は実装していません。測定・静的解析ツールとオフラインのプロファイラー参照コーデック・パーサーを用意しています。新しい9回の測定では時間のばらつきが小さく、タスクスレッド数8・12・16の平均経過時間はそれぞれ37.043・34.517・34.777秒でした。診断の基準を12、比較を16としますが、最適値の確定ではありません。12スレッドのCSVの1つには末尾に3フレーム余分に含まれるため、測定境界を厳密に揃えた再現性には追加確認が必要です。ネイティブ最適化を選ぶ前に、同期したOSレベルのプロファイリングが必要です。

過去の記録は`docs/superpowers/reports/`に残しています。新しい引き継ぎと矛盾する場合は、過去の記録を現在の状態として扱わないでください。

## 対象

- Victoria 3 Windows 1.14.5
- Caligula：`release/1.14.5` / `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- Clausewitz：`caligula/release/1.14.x` / `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`
- `victoria3.exe`のSHA-256：`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## データの保存方針

正確な統合入力がオフライン解析の効率と再現性を高めるため、`input-data/Vic3_data.zip`をGit LFSで保持しています。

- LFSのSHA-256：`79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- サイズ：124,462,636バイト

小さな抽出済み入力と保存済みのPC測定証拠も`input-data/`にあります。正式な一覧と保存規則は[入力データのマニフェスト](research/input-data-manifest.md)を参照してください。無関係なものや価値の低い大きなゲームアセットは追加せず、第三者のゲームデータを再配布する際は適用される利用条件を確認してください。

## 研究の原則

まず測定します。CPU全体の使用率が低いという理由だけで、スケジューラーやロックを原因と推定しません。再現性、OSレベルの証拠、対象ビルドの検証、期待する効果、動作上のリスクを理解するまで、ネイティブ最適化を導入しません。

## 次に必要な証拠

1. [保存済みの9回の測定](benchmarks/measured-2026-10-05-3month-repeats/)と[検証済みの分析](research/generated/repeats-2026-10-05/repeat-evidence.json)を使い、過去の単発測定とは分けて扱います。
2. 12_r2の終了境界を確認します。共通フレームのタスク・呼び出し負荷は一致しますが、生のCSVには3フレーム余分にあり、統合済みの負荷フィンガープリント検査がこの不一致を検出します。
3. 自動の境界タイムスタンプと交互の実行順序を使い、条件を揃えた12・16スレッドの測定をWPR/WPAまたはAMD uProfと同期します。
4. CPU処理・スケジューリング・待機を分類し、HandleAutonomousInvestment、ProcessEconomicMigration、UpdateEmploymentの読み取り専用調査を優先します。
5. 呼び出し元スタック、メモリ確保、メモリアクセスの証拠を使って[下流のネイティブ候補6件](research/generated/deep-native-2026-10-05/economics/findings.json)の寄与を調べ、初期化ガードやtick統計の更新をワーカー・状態の同期と区別します。

## 正式な参照資料

- [設計](docs/superpowers/specs/2026-10-04-native-performance-optimization-design.md)
- [実装計画](docs/superpowers/plans/2026-10-04-native-performance-optimization-implementation.md)
- [反復測定と開発判断](docs/superpowers/reports/2026-10-05-repeated-benchmark-analysis-ja.md)
- [詳細なネイティブ調査と開発条件](docs/superpowers/reports/2026-10-05-deep-native-investigation-ja.md)
- [CPUサンプリングの観測結果と未取得の証拠](research/os-sampled-capture-2026-10-05-ja.md)
- [オフラインツールの引き継ぎ](docs/superpowers/reports/2026-10-05-offline-three-plan-handoff-ja.md)
- [入力データのマニフェスト](research/input-data-manifest.md)

## 読み取り専用ネイティブプロファイラーの試作

Windows 1.14.5の完全に一致するビルドに限定し、3つのTickTask末尾アンカーを観測するDLLと、PIDを明示するローダーを追加しました。実ゲームでの観測負荷・安定性は未検証です。ビルド、接続、無効モード、停止、測定の手順は[Windows実ゲーム検証ガイド](docs/superpowers/guides/2026-10-05-native-profiler-runtime-validation-ja.md)、実装範囲と検証記録は[実装の引き継ぎ](docs/superpowers/reports/2026-10-05-native-profiler-runtime-implementation-handoff-ja.md)を参照してください。
