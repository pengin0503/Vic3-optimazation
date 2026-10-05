# native内部最適化に向けた追加調査と引継ぎ

2026-10-05。ユーザー依頼は「浅い箇所ではなく、もっと深い根本的な個所を最適化する方向で調査」「開発に有用な情報をリポジトリへ保存」。TaskThreadCount変更、defineの更新頻度削減、文化・宗教統合によるPop数削減を今回の実装成果にはしていない。

## 到達したこと

**nativeの計算・データ取得・一時メモリまで追い、候補6件を命令位置と確認条件へ具体化した。性能の根本原因や改善率はまだ確定していない。** 対象は保存済みWindows 1.14.5 exact build。起点は投資・移民・雇用のcallback、scheduler近傍の既存静的map。35選定unwind群・20,495 bytesの命令列と341 direct edgeを入力binaryへ照合し、別にscheduler近傍の7群を分類した。installed game、MOD、save、稼働processへの変更は0件。

9回の計測は同save、1911/3/1→6/1、同設定、warm-upありとユーザー確認済み。平均37.043 / 34.517 / 34.777秒（8/12/16）。12を診断基準、16を比較とする。ただし12_r2のraw CSVには共通区間後の3frameがある。0.26秒の12/16差を統計的最適値や根本原因と扱わない。詳細は [反復計測報告](2026-10-05-repeated-benchmark-analysis-ja.md)。

## 深い最適化候補と優先順位

以下の優先順位は調査の順序であり、期待speedup順位ではない。

| 優先 | 候補 | 新たに確認した構造 | 判断に足りないもの |
|---|---|---|---|
| 1 | 雇用のID走査とデータ局所性 | resetと直後の収集に、同item-originのID配列取得と同resolverの反復。さらに別resolver pass | 同一配列・途中の変更・順序依存、lookup CPU/load latency。再利用・融合の正しさ |
| 1 | 移民の候補走査と一時配列 | keyを組み合わせる命令列、24-byte slot走査、Pop pairのinline容量8、超過時のallocate/copy/release | slot占有率、配列件数、overflow頻度、allocator実体と費用 |
| 2 | 投資の入れ子仕事量 | paired pointer列、24-byte sparse-slot合計、条件別整数除算、残数依存の下流call | 内外loop trip count、branch mix、どの下流処理が時間を占めるか |
| 2 | 雇用の一時buffer寿命 | 139,504-byte stack予約、SEmployee/SEmployment hybrid inline storage、容量256/1024 | stack-page費用、inline hit、overflow量、buffer再利用時の寿命制約 |
| 2 | 雇用Collectとordering | 4-byte indexの統合・growth/copy、raw numeric sort、その後40-byte recordへ深い雇用更新 | copy/sort/更新の別々の費用、deterministic ordering条件 |
| 横断 | 共通helperとID解決 | 移民と雇用の `0x12a4ee0`、投資との共通resolver、table/page/live-bit参照 | caller stack別の費用、invalid-reference率、cache latency |

詳細: [経済処理の静的証拠](../../../research/deep-economics-native-2026-10-05-ja.md)、[6候補JSON](../../../research/generated/deep-native-2026-10-05/economics/findings.json)。同じデータに見えることは不要処理の証明ではない。現行命令列は処理内容・iteration順序・RNG・script・object寿命の制約を含むため、その確認より前に削除や融合を選ばない。

## scheduler調査で避けられた誤認

heuristic/callerから到達するSRW/condition-variable経路の一部はTLSと初期化guardに整合し、別のSRW経路は平均tick時間の整形・更新につながる。これらをworker完了待ちやGameState同期と認定する根拠はない。統計更新についてはobserver overheadの確認対象にする。詳細は [同期の分類](../../../research/deep-scheduler-synchronization-2026-10-05-ja.md)。全走査site数を実行lock数やhotspot数と扱わない。

## 公開一次資料から増えた開発上の判断材料

8件を [資料一覧](../../../research/generated/deep-native-2026-10-05/public/sources.json) と [日本語メモ](../../../research/native-architecture-public-followup-2026-10-05-ja.md) に保存した。確認日、公開日、適用範囲、現地検証、推論禁止事項を含む。

- 元Paradox開発者の本人記事では、在籍当時は異なるTickTaskを同時実行せず、Task内部parallelを用いたと説明する。退職後の変更には留保があり、現行1.14.5の断定には使わない。依存graphとread/write安全性を別に調べる理由になる。[Part7](https://mropert.github.io/2025/10/06/making_games_tick_part7/)
- 本人の初期Vic3描画pollution取得の体験では、frameごとの再計算を明示的な定期cacheへ移した。現行未修正問題とは扱わず、UIがsimulationデータを取得する経路・cache invalidation・Session待ちを調べる設計参考にする。[Part5](https://mropert.github.io/2025/06/17/making_games_tick_part5/)
- 公式1.6 notesにはPop objectのmemory footprintを縮小してcache利用を改善した記録がある。DD105にはState/cultureの候補組合せとwhole-Pop移動・統合の説明がある。既存修正を再適用する根拠ではなく、現行候補数・load stride・split/mergeを調べる根拠。[1.6公式本文](https://store.steampowered.com/news/posts/?enddate=1709737629&feed=steam_community_announcements)、[DD105公式本文](https://store.steampowered.com/news/posts/?enddate=1708009914&feed=steam_community_announcements)
- WPA Running/Ready/Waitingとreadier chain、AMD IBS load latency/cache/coherencyを組み合わせて、OS待ちとRunning中のmemory stallを分ける。Modified/Owned hit単独でfalse sharingを確定しない。[Microsoft](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis)、[AMD](https://docs.amd.com/r/en-US/57368-uProf-user-guide/7.9.3.3.1.-Supported-Metrics?contentId=jaBE5A_fpYU3aMOys3mItg)

## 次に開発へ進むための条件

まず同じ12/16の固定区間をOS traceと結び、Session critical path・worker tail・UI待ち・allocator・lookupをcaller stackで分ける。正確なTask開始終了、loop回数、allocator byte数はsamplingだけでは得られない。既存offline profiler codec/parserはruntime writerではないため、必要なbounded event計測は設計・実装・overhead検証を別途行う。

Runningが主なら上表のlookup、走査、overflowを優先し、Waitingが主ならreadier chainから実際の所有者へ進む。候補の実費と意味上の制約が確認できた段階で、結果を保つ参照再利用、局所cache、buffer寿命の変更を設計する。Task依存を外すことや全部のロックを消すことは、この調査からは導けない。

正しさの条件は同初期save・同tick終端でstate/checksum、RNG・iteration順序、長期結果、multiplayer OOS、観測費用を評価すること。保存byteの一致は静的解析の正しさの一部を示し、ゲーム実行結果の等価性を示すものではない。

## 再開用

[再生成手順](../../../research/deep-native-reproduction-2026-10-05.md) にportable recipeとartifact hashを記録。基準mainは `2bde7dc4ce3f72af692f3cd625dbf839c5ef0795`。既存ModifierNode続報PR9は別変更として保持し、今回の成果へ混在させていない。

再開時の依頼例:

> Vic3-optimazationの2026-10-05 deep-native調査報告から再開。exe hashを確認し、12基準/16比較の同区間OS traceを保存する。6候補のcaller stack・allocation・load latencyを優先し、初期化guardとtick統計更新をworker barrierと誤認しない。結果等価性を説明できるまでnative性能patchは選ばない。ゲーム/MOD/saveはread-only、調査成果はリポジトリへ保存する。
