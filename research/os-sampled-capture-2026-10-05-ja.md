# 欠落0件のCPU記録：下流native候補の実行を観測

2026-10-05。収集を`Vic3Sampled`へ絞った2回目の記録は、**lost events 0 / lost buffers 0**で保存・終了した。154,140,672 bytes、SHA-256 `0e83528be74c8702a06b7178d7c6698f1f4a5a4841b74c54598da7af76adb936`。操作者はTaskThreadCount=12、同save・warmup・設定で1911/3/1に準備したと応答し、その後1911/6/1にpause、**48.46秒**と報告した。

**今回進んだ点は、静的な候補をゲームの実行位置・stackで実際に観測できたこと。** 同じ3か月区間の厳密な関数費用や最適化効果はまだ判定しない。48.46秒は従来の12スレッド平均34.5167秒より長いが、収集負荷や条件差を分離した対照実験がなく、原因は不明。

## 未取得の情報

解析時点ではゲームが終了しており、今回のTickTask CSVは未取得。ライブCSVの更新時刻は前の37.53秒分のままだったため、再利用しない。traceのprocess表でもPID18108の終端を125,957,974usに観測したが、終了・crashの理由はその表からは分からない。操作者へ通常終了かcrashか、dumpできたか、speed/UI等の差を確認中。

開始と終了の目印は356,245usと130,724,436us、外側の区間は130.368191秒。手動操作、pause、console、返信などを含み、48.46秒のゲーム区間の開始・終了時刻として使わない。今回のsummaryはこの外側の区間に限定する。CSwitch/ReadyThreadを収集していないので、待ち割合・Ready遅延・critical pathは判定できない。

## 深い最適化の調査に役立つ実行証拠

ゲームのサンプルは398,022件。397,489件にはstackがあり、533件にはなかった。イベント欠落0件でもstackが100%揃うわけではない。以下は**サンプル数**で、関数呼び出し回数・ms・allocation回数ではない。pause中の処理も含むため、全区間に対する割合をsimulationの費用割合として示さない。

| 静的に調べた範囲 | その範囲に実行位置があったサンプル | stack中で範囲を観測したサンプル | 次に調べる意味 |
| --- | ---: | ---: | --- |
| ID/table解決候補 `0x7ed5f0` | 2,863 | 2,864 | bounds/full-ID照合と間接アクセスの費用 |
| page/live-bit参照候補 `0x13712b0` | 2,325 | 3,091 | page解決とデータ局所性。callerを分けて確認 |
| copy/sort関連の共有先 `0x427cb10` | 1,901 | 2,193 | 動かすbyte数とbatchサイズを別途調べる |
| ID解決候補 `0xc46bc0` | 1,750 | 1,753 | 投資/雇用等に分けてlookup費用を確認 |
| release委譲候補 `0x630340` | 1,492 | 2,102 | 一時配列のinline/overflow経路と解放費用 |
| allocate委譲候補 `0x630380` | 398 | 589 | 配列確保経路。sample数を確保回数へ変換しない |
| 雇用準備のreset候補 `0x13b8540` | 6 | 4,732 | 下流calleeを含む反復処理の調査 |
| 雇用準備の複数pass候補 `0x10bd490` | 4 | 4,731 | ID配列の再取得/再解決、再利用できる条件 |
| 投資のnested work候補 `0xf771a0` | 2 | 2,407 | 下流へ広がる処理のcaller別費用 |
| 共有work helper `0x12a4ee0` | 26 | 2,414 | 移民と雇用をstackで分け、下流のpage/lookup費用を調べる |

inclusive列は、その範囲を含むstackまたはleafのサンプル数であり、範囲同士で重複する。行を足し合わせない。これらは[前のexact-build解析](deep-economics-native-2026-10-05-ja.md)との照合で、source symbolを復元したという意味ではない。

`0x13b8540`と`employment_prepare_callback`は4,732件、`0x10bd490`と同callbackは4,718件のstackで共に観測された。雇用準備候補が実際のstackへ現れた証拠になる。ただしstackの共起はdirect callの証拠ではなく、UpdateEmployment全体の費用へ直結させない。他の共有先も、dispatcherがstackにあるだけでは個別TickTaskへ帰属できない。

次の調査では、単純なthread数変更から一段進め、**ID/table/pageアクセスのcaller別費用、一時配列の確保・解放・copy、雇用の複数pass**を優先する。`0x85d7c0`自体のleafは164件に留まり、静的に重複resolverが見えるだけで最優先と決めない。allocation頻度・byte数、cache miss/latency、状態変更の順序と再利用可能性は追加証拠が必要。現時点では融合・cache・native patchを実装する根拠はまだ不足している。

## 解析の検証と保存先

[capture-manifest](generated/os-sampled-capture-2026-10-05/capture-manifest.json)、[sample-observations](generated/os-sampled-capture-2026-10-05/sample-observations.json)、[game image provenance](generated/os-sampled-capture-2026-10-05/game-image-provenance.json)、[25範囲のleaf witness](generated/os-sampled-capture-2026-10-05/leaf-witnesses.json)、[verification](generated/os-sampled-capture-2026-10-05/verification.json)に保存。

実際のxperf export headerを確認し、SampledProfileの10列とStackの6列を解析した。timestamp/TIDの一致を検査し、不一致0件、ゲームのCountは全て1かつUnbatchedだった。ASLRのbase `0x7ff7f06c0000`、exclusive end `0x7ff7f6563000`は、そのtraceのゲームimage行から検証した。PEのpreferred baseは流用しない。

42下流範囲と、224 named CTickTask targets + 6 helper/callback candidatesの230-target catalogは別々に照合。後者の`dispatcher_candidate`などはTickTask名ではない。既存normalizerへ実export由来のgame leaf CSVを渡し、既存correlatorでは285,629 game-module leaf rows中11,324が42下流範囲に一致。invalid addresses 0、ambiguous 0。msやCPU時間の列は供給していない。

原初のparserと、image検証・cache・安定したtie順を加えたparserで全leaf/inclusive/cooccurrence集計の一致を確認した。独立reviewではwarmup metadataの意味を修正した。`warmup:false`は本計測の観測、`warmup_performed`はその前のwarmup実施を表す。

## 再現方法と引き継ぎ

raw ETL、system-wide export、約1.26GBのdumper出力、約104MBのgame leaf CSVと大きなnormalized JSONはlocal `raw-captures/`に保持。[raw-input-inventory](generated/os-sampled-capture-2026-10-05/raw-input-inventory.json)は内容をGitへ保存したことを意味しない。hash、path、sizeを記録している。別PCで全件を再解析するには、それらのraw入力を別途移す必要がある。

リポジトリrootから、保存済み原本を上書きしない空の出力先へ実行する。保存した[解析source](generated/os-sampled-capture-2026-10-05/analysis-source.py.txt)は、このrunのPID/base/markerを明記した研究用recipe。他のrunへ無確認で使わない。

```powershell
xperf -i raw-captures/os-sampled-t12-r01/cpu.etl -o raw-captures/os-sampled-t12-r01/process-images.txt -a process -image
xperf -i raw-captures/os-sampled-t12-r01/cpu.etl -o raw-captures/os-sampled-t12-r01/samples-stacks.csv -a dumper -provider '{ce1dbfb4-137e-4da6-87b0-3f59aa102cbc}' '{def2fe46-7bd6-4b80-bd94-f57fe20d0ce3}' -stacktimeshifting
python research/generated/os-sampled-capture-2026-10-05/analysis-source.py.txt --repo . --raw raw-captures/os-sampled-t12-r01 --output raw-captures/os-sampled-t12-r01/reproduced-analysis
```

原本exportが既にある場合は、最初の2行で上書きせず既存hashを検査する。normalizationは保存済み[mapping](generated/os-sampled-capture-2026-10-05/mapping.json)を使用し、前のrunbookのnormalize/correlate手順へ渡せる。timestampはxperfのusを明示的にnsへ変換する。公開用にはaggregate、game-onlyのbounded witness、recipeを保存し、system-wide process/stack表は保存しない。

再開時はまず今回分のCSVとゲーム終了理由を確認し、取得不能ならその欠測を維持する。その後、正確な開始/停止時刻の根拠、収集負荷の対照、12/16の同条件反復を揃える。sampleの観測だけから高速化の成功やcache bottleneckの確定へ進まない。
