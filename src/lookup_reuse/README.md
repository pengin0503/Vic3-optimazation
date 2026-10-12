# 検索再利用コア（Stage A、オフライン）

[雇用処理の検索再利用・シャドウ比較設計](../../docs/superpowers/specs/2026-10-07-employment-lookup-reuse-shadow-design.md)のための、移植可能なC++20静的ライブラリ、テスト、オフライン実行ツールです。[Stage Aの計画](../../docs/superpowers/plans/2026-10-06-offline-lookup-reuse-core.md)に沿って実装しています。

**対象範囲：**すべて所有する不変の合成テーブルで動作します。ネイティブアダプター、DLL、迂回フック、実プロセスメモリ、ゲーム入力、検索の省略は含みません。ライブラリはWin32、MinHook、プロファイラーのコーデックに依存しません。V3PF v1形式、対象ID、参照データは変更していません。テストの成功は、ネイティブコンテナーとの同等性、ABI、メモリ寿命、ゲーム速度の証拠にはなりません。

## 構成要素

| ファイル | 役割 |
|---|---|
| `include/TableView.h`、`core/TableView.cpp` | `OwnedTableFixture`が範囲を限定したバイト列をコピー・検証し、`ValidatedTableView`を発行します。FNV-1aの`HashKey`と、範囲を限定した`ReferencePositiveSearch`も含みます。 |
| `include/PositiveSlotHint.h`、`core/PositiveSlotHint.cpp` | 正のプライマリスロット1件の識別情報、マスク、完全なキー、インデックスを記憶し、`Try`のたびに再検証します。 |
| `include/ShadowComparison.h`、`core/ShadowComparison.cpp` | `OfflineShadowEvaluator` / `ObserverScope`。元の検索を厳密に1回実行し、結果と例外を変更せず渡します。ヒントによる候補は比較だけに使います。 |
| `runner/` | 固定シードの差分比較と単独のJSON出力。書式処理と入出力は実行ツール側だけに置きます。 |
| `tests/` | Releaseでも有効な`CHECK`テスト、`--list` / `--filter <exact-name>`、標準ライブラリだけを使うJSON・CLI検証の`VerifyRunner.py`。 |

### テーブルの契約（layout_version 1）

40バイトのリトルエンディアンレコードをフィールドごとに読みます。制御バイトは+4にあり、`0`なら空です。それ以外は`HashKey(key) & mask`からの、折り返さない探索距離+1を表し、最大255です。完全なuint32キーは+8にあります。`mask`は`2^n - 1`で、スロット`0..mask`がプライマリ、それ以降が末尾領域です。

検証は次の順に拒否します。未対応レイアウト、不正なマスク、サイズのオーバーフロー、切り詰められた領域（バイトサイズ不一致、プライマリ数より少ないスロット、末尾の空終端の欠如）、制御値の不整合、完全なキーの重複、通常の探索で到達できないキーです。通常の探索は`control < distance + 1`で停止します。

### 所有権と識別情報

`OwnedTableFixture`と`ValidatedTableView`はコピー・移動のどちらもできません。ビューは借用であり、元のテストデータより長く生存してはいけません。`TableIdentity`（`map_id`、`storage_id`、`lifetime_epoch`、`layout_version`）はテストデータの所有者が設定し、変更・配置移動・再生成のたびに世代を進めます。世代はオフライン用の仕組みであり、ゲームにそのフィールドがあると仮定したものではありません。

### ヒントとシャドウ比較の規則

- 識別情報、マスク、完全なキーが一致し、指定インデックスの現在のプライマリスロットに同じ完全なキーが存在する場合だけヒントを使います。それ以外は呼び出し側が通常の検索を行います（`NeedsOriginal`）。
- 未検出、末尾スロット、範囲外・空のスロット、別のキーを指す結果は記憶しません。
- モードは既定の`Off`と`Shadow`です。最適化モードはありません。
- 状態は`NoCandidate`、`Equal`、`Mismatch`、`Skipped`です。スキップ理由は`Off`、`MissingView`、`MissingScope`、`Reentrant`、`SessionDisabled`です。
- 不一致が起きると、その評価器のセッションの残りでは候補処理を停止します。モード変更でも再有効化されません。
- 再入呼び出しは候補処理を省略し、外側のヒントを無効化します。外側の呼び出しは`Skipped/Reentrant`として完了します。

## ビルドとテスト

CMake 3.25以上を使い、リポジトリルートから実行します。

```bash
cmake -S src/lookup_reuse -B build/lookup-reuse -DCMAKE_BUILD_TYPE=Release
cmake --build build/lookup-reuse --config Release
ctest --test-dir build/lookup-reuse -C Release --output-on-failure
```

`-DLOOKUP_REUSE_WARNINGS_AS_ERRORS=ON`を加えると、`-Werror` / `/WX`を適用します。CIではこの設定を使います。Visual Studioのジェネレーターでは実行ファイルは`build/lookup-reuse/Release/`にあります。CMakeがPython 3インタープリターを見つけられない場合、JSON・CLIテストは明示的にスキップ（`Skipped`）として登録されます。

CMakeなしでGCCを使う場合：

```bash
mkdir -p build/lookup-reuse
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/tests -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/OfflineRunner.cpp src/lookup_reuse/tests/*.cpp -o build/lookup-reuse/lookup_reuse_tests
build/lookup-reuse/lookup_reuse_tests
g++ -std=c++20 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Isrc/lookup_reuse/include -Isrc/lookup_reuse/runner src/lookup_reuse/core/*.cpp src/lookup_reuse/runner/*.cpp -o build/lookup-reuse/lookup_reuse_runner
python src/lookup_reuse/tests/VerifyRunner.py build/lookup-reuse/lookup_reuse_runner
```

CMakeなしでMSVCを使う場合は、同じソース一覧で`cl /std:c++20 /O2 /DNDEBUG /EHsc /W4 /permissive- /Isrc\lookup_reuse\include ...`を使います。

## 実行ツール

```bash
build/lookup-reuse/lookup_reuse_runner --seed 20261007 --rebuilds 1000 --output research/generated/lookup-reuse-core/results.json
```

`--seed`は符号なし32ビットの10進数、`--rebuilds`は正の10進数です。符号付き表記、16進数、オーバーフロー、重複、未知のオプションは拒否します（終了コード2）。`--output`を省略すると標準出力へ書き込みます。終了コードは、0が全比較一致、1が不一致あり（JSONは出力）、3が出力の入出力失敗です。

各再構築では、一意の完全なuint32キーを1～16件生成します。`std::mt19937`の生の出力に明示的な剰余演算を適用し、小さなキー、下位24ビットが共通するキー、`UINT32_MAX`付近のキーを混ぜます。マスクを7・15・31で切り替え、実行ツール内のRobin-Hood挿入を使います。新しいストレージと、後方シフト削除を1回行って世代を更新した同じストレージの、2つのスナップショットを検証します。

最初に、シードに依存しない4つの境界スナップショットを実行します。末尾領域、後方シフトの前後、`UINT32_MAX`を使うマスク0です。期待する存在判定は独立した`std::set`から、期待スロットは実行ツール自身の配置マップから取得し、検証器や参照検索を期待値の生成に使いません。各検索を参照検索、コアのヒント呼び出し（`Try`、ヒントが使えない場合だけ参照検索）、シャドウ評価器で確認します。

コミット済みの[結果](../../research/generated/lookup-reuse-core/results.json)と[検証記録](../../research/generated/lookup-reuse-core/verification.md)は、このコマンドから生成しています。`core_hits`は合成負荷で参照検索を省略できた回数であり、時間でもゲーム高速化の証拠でもありません。

## Stage Bは未着手

ネイティブ側のシャドウ比較には設計の第8節の条件が必要です。対象ビルドの位置特定、内部ABI、フック入口、呼び出し元スコープ、ワーカーの寿命、テーブルの不変条件、読み取り時の寿命、プロファイラーの前提（Task 9のローダー・DLL）、観測範囲と観測コストを含みます。このディレクトリの検証だけでは、これらを証明できません。
