# 実測上位TickTaskの準備処理とcallback候補

対象: Victoria 3 Windows 1.14.5。実行ファイルSHA-256:
`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。
解析基準: main `aba95bf96678a3b2d9514ff8e4f2498e35ce53fd` と今回の添付。
RVAはこのビルドの調査位置であり、固定のAPIや利用可能なhook契約ではない。

## 今回増えた証拠

以前はクラス固有の末尾仮想関数から直接callを追っていた。今回はその入口で
materializeされるMSVC RTTI付き関数オブジェクトを照合した。
3処理すべてに `std::_Func_impl_no_alloc` のvtable参照があり、型名には対応する
TickTask、`Prepare`、lambda、rangeとexecution contextが含まれる。
民間投資と経済移民は `gamestatetick.h` / `Prepare` の診断文字列も参照する。
したがって、入口を「重い計算全体」と扱うより、準備処理とcallbackを分けて調査する根拠がある。

| 実測対象 | 末尾仮想関数の入口 | Prepare lambdaのvtable / slot 2 | RangeExecuteHelper lambdaのvtable / slot 2 | その先の直接call候補 |
| --- | --- | --- | --- | --- |
| 民間投資 | `0xf6e590` | `0x4557a88` / `0xf7ec40` | `0x4557918` / `0xf8a290` | `0xf771a0` |
| 経済移民 | `0x11b0c00` | `0x4576830` / `0x11baee0` | `0x4576698` / `0x11bed40` | `0x11aec40` |
| 雇用更新 | `0x13b8310` | `0x45901f8` / `0x13caed0` | この段階では同型の中間段を確認せず | `0x13b8540` |

slot 2という位置は今回の観測。関数オブジェクトの全slotを別々の候補として保存し、
直接call、仮想関数slot、tail jump、コードアドレス参照を混同しない。
vtable対応はlocatorのsignature=1、pSelf、TypeDescriptor名、コード領域へのslotポインタで検証した。
この静的な関連から、実行時の呼出し回数、到達性、thread、タスク依存関係は確定しない。

## 処理本体候補の追加照合

| 処理本体候補 | 復元できた範囲（終端を含まない） | 範囲内bytes | 直接call箇所 | 間接call箇所 |
| --- | --- | ---: | ---: | ---: |
| 民間投資 `0xf771a0` | `0xf771a0–0xf775af` | 1039 | 10 | 2 |
| 経済移民 `0x11aec40` | `0x11aec40–0x11aed95` | 341 | 6 | 3 |
| 雇用更新 `0x13b8540` | `0x13b8540–0x13b8765` | 549 | 8 | 3 |

雇用更新候補はさらに `0x4590230` の関数オブジェクトを参照し、型名に
`CollectEmployment`、`CPdxArray<CState*>`、range/contextがある。
これは雇用収集処理への対応を強める証拠だが、この範囲だけで全雇用計算を測れるとは限らない。

民間投資・経済移民に共通する `0x7c51e0` は、入口側では条件分岐の下で
`Cleanup was not executed` の診断情報とともに呼ばれる。
この共有callだけをschedulerやlockの責任箇所に指定しない。
2段の候補グラフに既知scheduler入口 `0x7db150` / `0x7dbaa0` への直接edgeはなかった。
間接経路と未展開先が残るので、schedulerを通らないという証明にはならない。

## 保存した範囲と限界

- [hotspot-callgraph.json](generated/runtime-followup-2026-10-05/hotspot-callgraph.json): 3入口から深さ2、39関数群、12077 bytesを線形decode。全範囲decodeできた。79先は深さ制限またはunwind不在で未展開。
- [callback-continuations.json](generated/runtime-followup-2026-10-05/callback-continuations.json): 上表のcallback/本体候補6範囲を別途decodeした派生結果。
- [native-targets.json](generated/runtime-followup-2026-10-05/native-targets.json): 16スレッドのcost/longest_lock上位各20件と、最初の断片・復元した範囲の対応。

全decodeは命令として読めたという意味。関数全体、完全なcall graph、実際の実行経路、
critical path、実行時間を保証しない。3段の広い試行では関数数制限と部分decodeが出たため、
再開用の主資料は範囲を明示した深さ2と限定callback解析に絞った。

次は同じ3か月・16スレッドのWPR/WPA等で、入口と上表の候補を別々に照合する。
OSサンプルでRVAを求めるときは、その実行で記録したmodule load baseを使用する。
OSのCPU sample比率はTickTask累計msと同じ値ではなく、時間区間を合わせて比較する。
DLL計測器の導入、schedulerの変更、処理回数の削減はまだ実施しない。
