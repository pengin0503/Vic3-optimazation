# 最初のOS記録：保存できたがイベント欠落あり

2026-10-05。TaskThreadCount=12、同セーブの1911/3/1→6/1を操作者が計測し、**37.53秒**と報告した。WPRの開始、目印、保存、専用sessionの終了は成功したが、保存時に**43,082件のイベント欠落**が判明した。この記録を定量的なnative費用・待ち割合・critical pathの判定には採用しない。

## 保存した証拠

- [manifest](generated/os-capture-attempt-2026-10-05/manifest.json)：実測値、exe/save hash、PID、trace hash/容量、欠落数、不明条件、操作者の報告根拠。
- [今回のTickTask CSV](generated/os-capture-attempt-2026-10-05/ticktask_timings.csv)：dump指示後に更新された909,805 bytes、23,445行、261処理。
- [前の12スレッド3回との比較](generated/os-capture-attempt-2026-10-05/ticktask-comparison.json)：共通368フレームでframe/task/callsのmultisetは3回全てと一致。今回の余分な末尾frameは0。内部状態の完全一致を示すものではない。
- [trace header](generated/os-capture-attempt-2026-10-05/trace-statistics.txt)、[目印](generated/os-capture-attempt-2026-10-05/trace-marks.txt)、[provider別容量](generated/os-capture-attempt-2026-10-05/provider-diagnostics.json)、[保存ファイルhash](generated/os-capture-attempt-2026-10-05/integrity.json)。

過去12スレッド平均34.5167秒に対して今回は8.73%長い。ただし1回の収集あり計測で、run固有のwarmup、camera/UI/speed等の詳細は独立確認できていない。収集負荷の推定やゲーム性能の悪化とは断定しない。操作者は前の9回について同save/期間/設定、warmupありと確認したが、今回分のwarmupを明示的に再回答したわけではない。その違いをmanifestに残す。

| 処理 | 今回の累積ms | 過去12の共通frame平均ms |
| --- | ---: | ---: |
| HandleAutonomousInvestment | 1,708 | 1,617 |
| UpdatePopGrowth | 1,319 | 1,224 |
| ProcessEconomicMigration | 1,013 | 966.33 |
| RecalculateModifierNodes | 983 | 873.33 |
| UpdateEmployment | 896 | 841 |

これらはTickTaskの累積計測値であり、wall timeの内訳や下流native関数のCPU時間ではない。移民・雇用のID lookup、一時配列、共有helperについて、前の静的候補を動的な費用と対応させる調査は引き続き必要。

## 欠落の診断と次の設定

元の`CPU.Verbose.File`はSampledProfile、CSwitch、ReadyThreadのstackと多数のuser providerを同時に記録する。4,213,178,368 bytesのETLに、StackWalk 22,402,408件 / 3,180,959,224 storage bytes、Thread 16,350,062件 / 647,848,480 bytesが記録された。ThreadにはCSwitch 10,500,050件、ReadyThread 5,733,630件を含む。これらはsystem全体の診断値であり、Victoria 3の切替回数ではない。

欠落がどのprovider・時刻で起きたかは不明。停止前statusの`Dropped event: 0`だけでは品質を保証できず、保存後の警告とtrace headerを確認する。xperfは通常欠落traceの処理を拒否した。`-tle`で明示的に処理した出力は品質診断用に限定する。一般的な「disk bandwidth不足」メッセージだけで、このPCのdiskが原因とは決めない。

[vic3-focused-cpu.wprp](vic3-focused-cpu.wprp)を用意し、収集を2種類へ分けた。[Microsoftのcollector仕様](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/1-collector-definitions)と[provider仕様](https://learn.microsoft.com/en-us/windows-hardware/test/wpt/2-system-and-event-provider-definitions)に従い、実機WPRでprofile一覧と実際のkeyword/stack/buffer設定を確認した。

- `Vic3Sampled`：ProcessThread、Loader、SampledProfileとSampledProfile stack、WPR目印。次のCPU実行位置の照合に使用。CSwitch/ReadyThreadの待ち分析はできない。
- `Vic3Scheduling`：ProcessThread、Loader、CSwitch、ReadyThreadとそのstack、WPR目印。別runの待ち分析用。高容量になる可能性があり、まだ実記録では検証していない。

system bufferは1,024KB×64、marker bufferは128KB×16。sample intervalやゲーム設定は変えない。buffer増加はメモリ消費も変えるため、収集あり/なしの負荷比較は別に必要。短い時間で保存し、終了後に必ずlost eventsを検査する。

`Vic3Sampled`の10秒の開始/目印/停止確認は成功し、traceは42,991,616 bytes、lost events 0、lost buffers 0だった。これは計測設定の動作確認であり、3か月の負荷中に欠落しないことの証明ではない。Windows PowerShell側はローカルscript実行が無効だったため、確認用子processだけ`-ExecutionPolicy Bypass`を使った。恒久的な実行policyは変更していない。

## 次回の操作

同saveを再loadし、同じwarmup・設定で12スレッド、1911/3/1にpause。前の[runbook](os-capture-preparation-2026-10-05-ja.md)の専用session/marker/stop手順を使い、開始profileを次のように置き換える。既存runを上書きせず、新しい保存先とsession名を使う。

```powershell
wpr -start research/vic3-focused-cpu.wprp!Vic3Sampled -filemode -recordtempto $runFolder -instancename $captureSession
```

このPCでは通常tokenの`wpr -status`が、別の昇格tokenで開始した専用sessionを「記録していない」と表示した。開始・目印・status・stopは同じ管理者権限で行い、保存後にsession終了を確認する。sandbox外実行だけではWindows管理者権限は得られない。

raw ETLとsystem全体のprocess/stack exportはlocal `raw-captures/`へ保存する。今回のtrace SHA-256は`8f0c4f7b28c0026960ad44cb985e77a049fd940220bfa34db8acc85e127ab96d`。Gitには上記のゲームCSVと診断集計を保存する。失敗記録を良好な本計測のrepeatへ混ぜない。
