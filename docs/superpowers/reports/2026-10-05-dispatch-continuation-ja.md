# 並列実行経路と雇用callbackの追加調査

Date: 2026-10-05
Repository: pengin0503/Vic3-optimazation
Base main: `3972ba6fa21d4fbef4ccafe75a4b678ab0024cae`

## 今回の成果

添付の1.14.5 exeとGitHub上の前回成果を使い、共通dispatcher候補から既知のrange runner・
heuristicまでの直接callを確認した。主要3クラスに対応するslot 6の呼び出しと、
フラグによる並列経路／callback直接呼び出しの分岐を記録した。
雇用処理ではCollectEmployment・SortEmploymentのcallbackとitem処理候補まで進めた。

詳細、比較即値、callsite、再現手順は
[静的dispatch対応表](../../../research/ticktask-dispatch-static-map.md)を参照。
前回の[callback対応表](../../../research/ticktask-callback-map.md)と併用する。

重要な区別として、共有helper `0x74f7b0`はcallableの移動／交換に似た構造であり、
そのcallだけでjobを実行したと判断できない。今回確認した実行側の間接call位置と分けて扱う。

## 保存したもの

- `tools/map_native_callers.py`: 指定RVAのE8 rel32 callerを逆方向に検索し、unwindの命令境界で照合。raw match・棄却・未解決・確認済みを分離。
- `research/recipes/reproduce_dispatch_evidence.py`: exact hashを照合し、18選定関数群と指定3targetのcaller検索を再現。
- `research/generated/dispatch-followup-2026-10-05/`: 9972bytesの選定範囲、命令抜粋、4直接call、派生ファイルhash。
- 静的dispatch対応表と最新READMEへのリンク。

## 検証

新toolは、正しいcallと即値内の偽E8、unwind不在、部分decode、サイズ上限、hash不一致、
target名重複をテストする。テストの失敗を確認してから実装し、添付exeとZIPで再現recipeを実行した。

- 添付ビルドのintegrationを含む全68テスト成功、skipなし。
- 独立レビューでCritical/Important指摘なし。接頭辞付きE8 callを取りこぼすMinor指摘は、失敗するテストを追加して修正した。opcode位置と命令先頭位置を分離して保存する。
- レビュー担当が派生3ファイルを独立再生成し、修正前の保存結果とbyte単位で一致を確認。接頭辞対応後も、今回の4直接callと18選定範囲は同じ。
- 派生ファイルhash、変更文書の相対リンク、diffの空白を照合。

## 作業状態と次の順序

Task 7のbinary mapとTask 5の測定後照合を前進させた。native loader・hook・性能patchは
未着手。Task 9以降の実装を開始する条件は、既存の承認済みdesignのまま。

1. OSのCPU sample / wait / stackを今回のnative範囲へ照合する。
2. 共通dispatcherのcaller stackからtaskを識別し、並列経路と直接callback経路の実際の比率を調べる。
3. 雇用のCollect・Sort・item候補についてCPU計算と待ちを分ける。
4. 対象とABIが確認できた段階で、最小のread-only計測に進む。

OS trace、繰り返し測定、runtimeのcallback identityは未取得。静的対応だけで
lockの原因・serial bottleneck・thread数の最適値・性能効果を決定しない。
Issue #2 / #3 / #4 / #5を完了扱いにする材料にはまだ足りない。
