# B0：オフラインのネイティブシャドウ契約

[B0契約設計](../../docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md)のための、移植可能なC++20ライブラリ、テスト、Task 4のオフライン実行ツールです。[B0計画](../../docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md)に沿って実装しています。Task 1～4は実装・検証済みです。[検証記録](../../research/generated/lookup-reuse-contract/verification.md)を参照してください。

**対象範囲：**所有するテスト用データのみです。実プロセスメモリ、迂回フック、ネイティブABI呼び出し、DLL、ローダー、Windows SDK、MinHook、検索省略モードは含みません。テストの成功は、所有データの接続契約が成立することだけを示します。ネイティブ処理との同等性、ABI、メモリ寿命、ゲーム速度の証拠ではなく、Stage Bのネイティブ処理の着手条件（仕様第9節）を満たしません。

## 構成要素

| ファイル | 役割 |
|---|---|
| `../../tools/render_lookup_contract_manifest.py` | 固定されたネイティブシャドウの静的証拠から位置特定マニフェストを導出し、`generated/manifest_1_14_5.inc`を生成します。`--check`では書き込みません。 |
| `../../tools/check_lookup_contract_locator.py` | 対象ビルドに限定したオフラインの位置特定。所有するexe・ZIP・ディレクトリ入力、PE境界検査、一意の入口・呼び出し元シグネチャ、符号付きrel32、戻り先 = 呼び出し位置 + 5、例外・連鎖アンワインドのメタデータからの呼び出し元ルート復元を扱います。静的な証拠のみです。 |
| `include/NativeFixture.h`、`core/NativeFixture.cpp` | `OwnedNativeFixture`が検証済みコピーを所有し、内部でStage Aの`OwnedTableFixture`を使います。非公開の世代管理と失効を備え、`FixtureBorrow`が状態を保持します。 |
| `include/ResultNormalization.h`、`core/ResultNormalization.cpp` | 合成64ビット結果値を、参照先の読み取りなしで6分類します。 |
| `include/NativeShadow.h`、`include/NativeRecords.h`、`core/NativeShadow.cpp` | `OfflineNativeShadow` / `NativeScope`。元の処理を厳密に1回呼び、スコープ・セッション規則、固定256件の記録領域、上限で飽和するカウンターを備えます。 |
| `tests/TestFaults.h` | テスト専用の障害注入箇所（`LOOKUP_CONTRACT_TESTING`）。比較前の候補上書きと世代・セッション・スコープの上限到達を扱います。`lookup_contract_test_core`と単体テスト実行ファイルにだけ組み込みます。 |

## テストデータの契約

位置特定ツールは、所有する実行ファイルから6つすべての呼び出し元ルートを復元した後にだけ`caller_entry_rva_verified=true`を設定します。各呼び出し元は、互いに重ならない範囲と実行時関数の断片を含む`caller_metadata`を保持します。これはメタデータの対応付けであり、アンワインド操作、ネイティブABI、フックの安全性、実行時の戻り先アドレスの検証ではありません。

出力保護は、ディレクトリ入力から選ばれた実行ファイルへの外部ハードリンクも拒否します。ただし、並行したファイル置換に対するセキュリティ境界ではありません。[オフラインの堅牢化検証](../../docs/superpowers/reports/2026-10-08-offline-locator-hardening-verification.md)を参照してください。

スロットは40バイトで、制御値は`+4`、uint32キーは`+8`、記述子の値は`table_base + 40 * slot + 0x10`です。作成時は次の順に拒否します。

1. `0x7fffffff`を超えるマスク（非負のネイティブint32ではない）、オーバーフローするアドレス配置、宣言された番兵・代替値のゼロや相互一致、任意のスロットの記述子値との一致（`AddressLayout`）。
2. 世代の上限到達（`EpochExhausted`、折り返さない）。
3. Stage Aの検証エラー（`TableValidation`）。

| 分類 | 条件 |
|---|---|
| PrimaryPositive | プライマリの記述子位置で、使用中かつ完全なキーが一致 |
| TailPositive | 末尾領域の記述子位置で、使用中かつ完全なキーが一致 |
| EndSentinel / Fallback | 宣言された値と一致 |
| InvalidPrimaryResult | プライマリの記述子位置で、空またはキーが不一致 |
| Unknown | その他すべて。0、ベースより下、位置ずれ、末尾を超過、末尾領域での失敗、無効な借用を含む |

## シャドウ比較の契約

- 既定は`Off`で、もう1つのモードは`Shadow`だけです。nullでないコールバックを渡した呼び出しは必ず厳密に1回実行し、64ビット結果を変更せず返します。例外は同じオブジェクトとして伝播し、ヒントを消去し、その呼び出しの記録は書きません。
- 順序は、すべての呼び出しで再入ガード、条件を満たした場合だけ候補処理、元の処理、再確認、正規化、比較です。候補処理の条件はShadow、有効なセッション、アクティブなスコープ、許可された呼び出し元（生成済み証拠1～4）、有効な借用です。再確認ではモード、セッション、内側の呼び出し、スコープ、借用、モードの往復変更を確認します。候補がある`PrimaryPositive`だけを比較します。
- スキップの優先順位はOff、SessionDisabled、Reentrant、MissingScope、CallerExcluded、MissingFixture、ProofLost、結果分類による理由です。入口で無効な借用は`MissingFixture`、コールバック中に失効した借用は`ProofLost`です。スキップ時は必ずヒントを消去します。`NoCandidate`では消去後、検証済みの元のプライマリスロットを記憶します。
- 不一致は評価器のセッションを永久に無効化します。モード変更や新しいスコープでは復活せず、新しい評価器だけが新しいセッションを開始します。
- `Evaluate`、正規化、記録収集ではヒープ確保、入出力、ミューテックス、全テーブル検証を行いません。メモリ確保の回数はテストで確認します。

## ビルドとテスト

```bash
cmake -S src/lookup_reuse_contract -B build/lookup-contract -DCMAKE_BUILD_TYPE=Release -DLOOKUP_CONTRACT_WARNINGS_AS_ERRORS=ON
cmake --build build/lookup-contract --config Release
ctest --test-dir build/lookup-contract -C Release --output-on-failure
python -m unittest discover -s tests -p 'test_lookup_contract_*.py' -v
```

CTestには、`../lookup_reuse`を変更せずサブディレクトリとしてビルドしたStage Aのテストも含まれます。
