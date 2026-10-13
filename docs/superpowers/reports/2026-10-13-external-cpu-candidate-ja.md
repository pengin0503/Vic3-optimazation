# 外部CPU計測で選定する改善候補

2026-10-13 JST。基準main `e738fa5`。対象exeは1.14.5 / SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。

## 今回決めたこと

雇用の検証付き検索slot再利用を**設計の具体化が進んだ第一候補**にする。実行時費用が最大という選定ではない。既存Stage A/B0を再実装せず、外部計測で採否を判断する。民間投資・経済移民を対照として観測し、別処理が主因なら第一候補を保留する。

## 証拠と今回の再確認

| 項目 | 根拠 | 判断できる範囲 |
| --- | --- | --- |
| 同じitem起点の検索site4件 | [雇用調査](2026-10-07-offline-employment-optimization-ja.md)、[静的証拠](../../../research/generated/employment-reuse-2026-10-07/evidence.json) | `0x13b8632`, `0x10b7db4`, `0x10bd565`, `0x10bd66b`から`0xf3e040`へのcall。毎回4回、同table、同寿命とは未証明 |
| lookup成功経路 | 上記の189-byte excerpt `[0xf3e040,0xf3e0fd)` | 限定excerptにhash/probe/key照合。source-level関数全体の認定ではない |
| miss/fallback | `[0xf468d0,0xf469aa)`の218-byte excerpt | TLS guard、初期化call、global書込みがあり、検索全体を無副作用と扱えない |
| 雇用準備の実行 | [旧OS sample](../../../research/os-sampled-capture-2026-10-05-ja.md) | `0x13b8540` inclusive4,732件、`0x10bd490` inclusive4,731件。外側区間の重複するsample数であり、msやwall割合ではない |
| 旧TickTask比較 | [旧9回](2026-10-05-repeated-benchmark-analysis-ja.md) | 12threadの記録累計: 民間投資1,617ms、移民966.3ms、雇用841ms。並列累計なのでwallの内訳ではない |
| 元結果の維持 | Stage A/B0の既存owned fixture | 合成データの整合性。native ABI/借用table/worker寿命の証明ではない |

今回、添付ZIPのSHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` とexe hashを再確認した。雇用の11group＋lookup/fallbackの**13範囲**のhash、**7 direct call**の実byteと相対target、既存42対象のsource/range hashが一致した。[今回の検証結果](../../../research/external-cpu/offline-verification.json)に保存した。追加の全面decompileや合成モデルの再作成は行わない。

既存42対象のcatalogには`0xf3e040` / `0xf468d0`の限定範囲が含まれない。そこで[補助catalog](../../../research/external-cpu/employment-lookup-catalog.json)を既存builderで生成した。既存catalogへ混ぜず、同じnormalize出力に対して別々に照合する。補助catalogの命中を、無関係なcallerを含む「雇用専用費用」と呼ばない。caller stackが必要。

## 実測後の採否

| 観測結果 | 次に行うこと |
| --- | --- |
| 同一区間の複数Sで、lookup/probeが雇用caller下の主要CPU消費として再現 | その寄与と測定解像度を示し、native ABI・table変化/寿命・reentrancyを確認する限定設計へ進む |
| 雇用は重いがlookup/probeの寄与は小さく、別calleeが主要 | slot再利用を保留し、観測されたcalleeを対象にする。雇用全体の時間をlookup削減可能量としない |
| 投資/移民の別経路が支配的 | 既存の各静的候補へ戻る。共有helperのsampleを雇用へ付け替えない |
| sampleは少ない、stack欠落/外側境界の不確かさが大きい | 「費用ゼロ」と結論せず、情報不足を明示。短いlookupはsampling解像度の制約を受ける |
| workersの待ち/dispatchが疑わしいがSampledしかない | 別のVic3Scheduling runを提案。SampledからReady/Waiting・lock原因を確定しない |
| B/Sで実時間や処理別の傾向が大きく変わる | collectorの影響を報告し、Sの時間を本来の性能として採用しない。profileを追加して情報量を増やす前に必要な問いを絞る |

採用を自動判定する新しいgateは作らない。sample数はcall count、allocation頻度、cache miss、msではない。inclusive範囲は重複するので足し合わせない。独立した同条件記録で再現し、実ゲームの遅延につながる根拠を確認する。

## 将来の変更案と残る条件

候補は成功slot位置をhintにし、現在のtable/map/full key/slotの有効性を確認して、成立しなければ元検索へ戻す。失敗・fallbackを省略しない。全件reset、full ID検証、処理順序、RNGを維持する。生object pointer、全配列snapshot、別call間の無条件キャッシュを保持しない。

外部CPU記録で、借用期間、allocatorによるaddress再利用、並行table更新、内部ABI、relocation/unwindの正しさまでは証明できない。これらが必要になれば対象を絞った観測/設計を行う。現行shadowは元結果を返し、lookup bypassは別の変更である。DLL接続問題を保留することは、bypassや強制patchを許可することではない。

現時点の削減可能な**wall時間割合は不明**。Amdahlの式に入れる割合をTickTask累計やinclusive sample比から作らない。速度改善、hit率、observer overheadはnullのまま。次は[実測手順](../../guides/vic3-external-cpu-measurement-ja.md)。
