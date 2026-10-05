# Victoria 3 1.14.5: native最適化に向けた公開一次資料の追加調査

調査日: 2026-10-05。対象: Windows 1.14.5、exe SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。公開資料は現行binaryの実行結果ではない。資料8件の主張、公開日、現地確認手順、推論禁止事項は [sources.json](generated/deep-native-2026-10-05/public/sources.json) に保存した。sourceの本文を転載せず要約した。

既存の `research/public-performance-architecture-evidence.md` はTask/Modifier/Employmentの基礎説明をすでに扱う。本メモはその続編で、PR9のModifierNode静的追跡とは独立した調査。コード変更、native patch、Git操作は実施していない。

## 1. 最も大きな追加情報: Taskの論理依存とデータの競合は別

本人の体験を述べた [Mathieu Ropert Part7](https://mropert.github.io/2025/10/06/making_games_tick_part7/) は、在籍当時のVictoria3では異なるTickTask同士を同時実行していなかったと説明する。Task内部のparallel loopは使われ、退職後に変更されていれば事情は異なるとの留保も明記している。[公式DD76](https://www.paradoxinteractive.com/games/victoria-3/news/dev-diary-76-performance) のTask依存説明と矛盾する必要はない。依存グラフは処理順序を表しても、暗黙の共有stateへのread/writeが安全であることを保証しない。

**現行1.14.5への適用は仮説。** TaskThreadCountを増やしてもTask間が並列になると見なさず、Taskの実時間重複とTask内部のworker利用を別に観測する。各callbackの親Task、開始終了、TID、共有cache・script・RNG・Pop生成破棄への副作用を記録する。read/write対象を宣言する設計案は、sourceを持つengine再設計の参考になる。現行binaryのTask依存を外す根拠にはならない。

## 2. 描画bindingがsimulationにまで待ちを作る経路

[Part5](https://mropert.github.io/2025/06/17/making_games_tick_part5/) は、初期Victoria3で停止中のFPS低下を追い、可視Stateのpollution取得がBuildingと雇用比率を毎frame繰返し計算する問題を見つけた体験談。掲載コードは記憶による再構成で、当時のcache更新頻度も著者は確定していない。明示的な定期cache更新Taskを採用したという設計判断が有用である。

現行版に未修正で残っているとは推論しない。pause/進行、zoom、可視都市数の条件を揃え、UI/graphicsのCPUとSession待ちの変化を確認する。simulationにも使う値の期限cacheやdirty条件を変える場合はゲームstate比較が必要。lazy getterの内部でcacheを書き換える案は、暗黙の書込みと同期を増やす可能性がある。

## 3. Pop数だけでなく、候補組合せと1個の大きさを見る

[DD105公式Steam本文](https://store.steampowered.com/news/posts/?enddate=1708009914&feed=steam_community_announcements) は、1.6の移住で小さいPop全体の移動と統合を優先し、communityで行き先を絞る設計を説明する。当時のcommunity生成条件はmarket内のStateとcultureの組合せで月次評価される。現行移住の負荷説明には候補ペア数、split/merge、失敗候補も必要だが、現行のループ構造は未確認。

[1.6公式patch本文](https://store.steampowered.com/news/posts/?enddate=1709737629&feed=steam_community_announcements) は、Pop objectのmemory footprintを小さくしてiterationのcache利用を改善したと記録する。さらに毎tick判断の削減、不必要なmodifier再計算の抑制も前例としてある。**object数削減、1個のデータ量削減、不要な反復削減は異なる対策**である。現行型サイズ・SoA・container種類は、この資料だけでは分からない。

現行上位Taskについて、Pop topology、候補数、allocation、load stride、hot fieldの利用、cache miss latencyを照合する。文化・宗教を潰してPopを減らす変更はsimulation等価なnative最適化とは分ける。既存1.6修正を再度適用して利益があるとも主張しない。

## 4. 待っている理由を先に確定する

[Microsoft CPU Analysis](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/cpu-analysis) のRunning/Ready/Waitingとreadying chainを使う。Sessionが待つ場合、workerが最後に終わるのか、UIがstateを読み終えるのか、timer/I/O待ちなのかを区別する。ReadyはCPUの割当待ち。cache missによるhardware stallは通常Runningに含まれ、WPAだけで内訳は分からない。Task合計時間・各threadのCPU時間・期間wall timeは別の量であり、並列部分を単純加算しない。

[AMD uProf 5.3のIBS dump](https://docs.amd.com/r/en-US/57368-uProf-user-guide/7.9.3.2.3.-ASCII-Dump-of-IBS-Samples?contentId=hlXghfKOxlVSVvgBWDtgNg) と [cache metrics](https://docs.amd.com/r/en-US/57368-uProf-user-guide/7.9.3.3.1.-Supported-Metrics?contentId=jaBE5A_fpYU3aMOys3mItg) は命令/メモリ帰属を調べる手段。実CPU・インストール版・利用可能metricを確認した後、module load baseを引いたRVAで既存exact-build callback mapと結ぶ。Modified/Owned cache hit単独ではfalse sharingを証明しない。

[AMD GDC24](https://gpuopen.com/download/GDC2024_AMD_Ryzen_Processor_Software_Optimization.pdf) のSMT共有資源、cache line共有、過剰prefetchの競合は、12と16で飽和・後退する理由の候補になる。資料のmicrobenchmark倍率はゲームへ転用しない。

## 5. 次に判断可能にする順序

1. 同save・同tick区間で12基準/16比較のSession・worker・UIのtimelineを取得する。正確なTask boundaryにはbounded event計測が必要で、CPU samplingだけで短いTaskの重複不在は証明できない。
2. 期間wall timeを説明する主成分をRunning、Ready、Waiting、worker tailへ分ける。observer overheadと欠損記録も保存する。
3. Runningが支配的ならIBS等でcache/branch/allocationとobject iterationを調べる。Waitingが支配的ならreadier chainとUI releaseを調べる。
4. 現行cacheの既存更新・invalidationを確認し、結果等価な不要処理削減/局所cache/一時buffer再利用を先に候補化する。Task間並列化やstate layout変更は広い再設計で、前提確認を経て別扱い。
5. 変更時は同じ初期save、RNG・iteration順序、同tick終端、state/checksum、長期結果、multiplayer OOSとobserver overheadを評価する。speedupだけで正しさを判定しない。

現時点で追加資料は**原因候補と検証方法を増やした**。1.14.5のTask間並列の有無、cache/false sharingの支配度、利益の出るnative patchはまだ確定していない。公開資料の調査だけでそれらを確定することはできない。
