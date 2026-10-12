# Loaderのオフライン保留項目：追加検証とWindows fixture修正

Date: 2026-10-12 JST

ユーザーは前回の保留作業について「オフラインの保留作業を完了する」と指定した。実ゲーム操作は行わず、PR #18を継続する。開始時にmainを再fetchし、`321064d479248153585c0e838f8c25836aeae783` から変更がないこと、PR #18の前回head `b4b7365ccd5572b91f9e31a47f989dcb454132ed` を保持していることを確認した。

## 解消した保留項目

1. **追加query失敗のcoverage:** `ObserveRemoteBranchRegion` に既存read-only queryを抽出。テスト専用childの不一致証拠から、実invalid handleでVirtualQueryExを失敗させる。成功→失敗→成功の再利用を含め、元の `stage=byte_mismatch` / `win32_error=0` と両byte配列を保持し、古いquery属性をclearすることを検証した。probe未取得・未知entry・別stageではqueryせず、元stage/errorを保持する。
2. **出力書式:** hex/showbaseを設定したstreamで数値がdecimalになり、呼出元のflagsが復元され、その後の299が `0x12b` になることを検証。既存実装はこの追加テストを通ったので出力コードを変えていない。
3. **Pure helperの古い結果:** 拒否後の成功でも旧stage/errorが残る失敗を再現。各helperが成功時に自分の結果を `None/0` へ更新するよう修正した。失敗判定、16-byte比較、bounds、呼出側のstop-on-failureは維持する。前段拒否を無視して進むことを許可する修正ではない。
4. **Windows fixtureの6 errors:** 前回の5 methodsを再実行し6 errorsを確認。header-only CSVのmanifest検索をPOSIX相対pathへ統一。Windowsで作成できないdrive colon入りshadow directoryを作らず、実際のabsolute/drive-relative/backslash manifestは全OSで拒否検証する。production `check_cpu_runtime_gate.py` は変更していない。
5. **リンク権限の前提:** 通常path/出力aliasの否定検証と、実symlink/hardlinkの否定検証を別testsへ分離。Windowsで実link作成がWinError 5/1314となる場合のみ当該testを明示skip。他のエラーは引き続き失敗とする。通常path、外部証拠の不変、header-only拒否はskipしない。権限やsecurity設定は変更しない。
6. **goldenの改行:** 元blobのJSONと既存SHA-256は同じだが、Windows checkoutのCRLF変換でhash testが失敗することを再現。.gitattributesでgolden directoryを `-text` とし、元bytesを維持する。expected hashを更新して通す修正ではない。

## ローカル検証記録

環境とMinHook pinは前回と同じWindows 11 x64 / Visual Studio 2026 / MSVC 19.51 / Release。SuperpowersのNative / executing-plans、systematic-debugging、TDD、verification-before-completionを適用。[実行計画](../plans/2026-10-12-loader-offline-followup.md)に沿って進めた。

| 検証 | 観測結果 |
| --- | --- |
| Native pure policy RED | 拒否後の成功で古いstageが残るassertionに失敗 |
| 観測seam RED | 未実装関数のlink失敗。宣言したtest契約と実装不在を確認 |
| Windows x64 Native GREEN | build成功、10/10 CTest。実API失敗/成功/観測不要、書式、再利用の追加coverageを含む |
| Python対象RED | 前回の5 methodsで6 errors再現 |
| Python対象GREEN | 分離後7 tests、OK（link能力不足の2件skip） |
| golden RED→GREEN | checkout byte hash不一致を再現→元blob/新attributeで1 test OK、元hash維持 |
| Windows Python全suite | 257 tests、OK（skipped=8）、errors/failures=0。リンク検証を2つの独立methodsに分離したので前回255から257へ増えた |

前回の6 errorsは今回のWindows full suiteでは0。skip8はVIC3_DATA未指定の2件、hardlink作成拒否の5ケース、symlink権限不足の1件。うちlink2件は今回の独立化で追加されたmethods。skipを合格件数に含めない。最終CIのrun/head/job結果はPR本文とchecksへ記録し、結果を追記するだけのpushで再CIしない。CIは今回の最終確認で1回だけ起動し、途中の変更はpushしていない。

## 独立review

read-only reviewerが追加範囲 `b4b7365..62544bb` を確認し、Critical / Important / Minorはいずれも0。全followupログ8本、binary2本のSHA-256一致、golden4点のblob不変、拒否後のcaller停止、通常の否定検証がskipされないことを確認した。追加修正passや再reviewは不要だった。

判断対象外は実ゲーム/性能、既存のメモリ変化競合とコード全体の信頼、Windowsで能力不足となった実link結果、レビュー時点で未実施の最終CI/package検証。CI/packageはこの後に完了させてPR本文へ結果を保存する。review中の計画checkbox更新はcode変更ではなく、本作業で別途確認した。

## 残る境界

- 実ゲーム接続、Steamフックの安全な呼出、Phase 4、CPU高速化は未確認。バイト比較・対象build/同一PID gateを維持し、フックの解除/回避は追加していない。
- query失敗は拒否を変更しないことを実APIで検証したが、processのmodule/byte/queryの同時変化や関数全体の信頼性を保証する変更ではない。
- link testをskipしたWindows環境ではその実linkケースを検証したと数えない。CIのLinux側ではskipせず実リンクで検証する。
- Pure helperの成功はそのhelperの最新結果。前段失敗を保持したい直接callerはその結果を保存し、前段失敗後に次のhelperを呼ばない。production wrapperは毎回全diagnosticsをresetし、各拒否で終了する。

## 再開手順

最新PR headと[validation.json](../../../research/generated/loader-readonly-diagnostics-2026-10-12/validation.json)のsource/binary provenanceを使う。前回のWindows Python6 errorsは当時の記録として保持し、今回の結果と分ける。実ゲームを行う場合は別途、[読み取り専用guide](../guides/2026-10-12-loader-readonly-diagnosis-ja.md)に沿ってfresh PIDの診断だけを行う。今回ユーザー指定のオフライン範囲では、そのゲーム操作は実施していない。
