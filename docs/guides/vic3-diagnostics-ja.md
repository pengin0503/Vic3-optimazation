# Victoria 3の診断手順

このページと `tools/Invoke-Vic3Diagnostics.ps1` が現在の固定入口です。日付付きの過去報告、配布フォルダ、旧ブランチのコマンドを次の診断手順として使わないでください。今後も入口の場所と既定の読み取り専用動作を維持します。

## 毎回同じコマンドを使用する

Windows x64、64-bit PowerShell、Git、CMake 3.25以降、Python、Visual StudioのC++ x64 build toolsが必要です。実行ポリシーはスクリプトが変更しません。ユーザーの現在のポリシーでローカルスクリプトを実行できる環境を使用します。

mainを使用する診断用cloneを一度用意してください。未コミットの作業・証拠があるcloneは強制更新せず、保全した作業用cloneを使用します。mainを更新する場合はclean状態を確認して `git pull --ff-only` を行います。診断コマンド自体はfetch/pull、インデックス修復、削除、設定変更を行いません。

`C:\Vic3Optimization-Diagnostic` にcloneがある場合は、作業中のディレクトリによらず以下を使用します。

```powershell
& 'C:\Vic3Optimization-Diagnostic\tools\Invoke-Vic3Diagnostics.ps1'
```

初回またはsource commit変更時だけ、そのcommit専用の `build/diagnostics/<commit先頭12文字>/` へWindows x64 Releaseをbuildし、全CTestを実行します。成功した非空のCTest、commit、tree、Loader hashをprovenanceへ保存します。次回は同じ記録とhashを照合して使用します。古いLoader hash・PID・特定日の起動時刻を手入力する必要はありません。provenanceとbinaryが不一致なら自動上書きで隠さず停止します。

通常起動した新規のVictoria 3でsaveを読み込み、一時停止してからPIDを選択します。スクリプト起動前から実行中の新規processも受け付けます。固定日時による起動制限はありません。PIDと100ns精度の開始FILETIMEでprocess instanceを識別し、同じinstanceの過去attemptが保存されていれば再実行を拒否します。前の接続・診断試行から再利用していないprocessを選んでください。PIDだけが再利用された別instanceは開始時刻で区別します。

対象はcatalogとnative gateが定義するVictoria 3 1.14.5のexact exe hashです。exe名、hash、開始時刻、source、Loaderを照合し、`--diagnose-loadlibrary --pid PID` を1回だけ実行します。Profiler DLLをゲームへ注入せず、attach、stop、enabled計測は実施しません。

PID/FILETIMEの組をファイルのCreateNewで原子的に予約し、同時に2つのPowerShellを起動しても片方だけが診断へ進みます。予約後の起動失敗でも予約を保全し、削除して再実行せず新しいgame instanceを使用します。PID直接指定時は一時停止の申告を得ていないため、contextのgame_paused_reportedはnull（不明）です。通常の対話入口では準備確認に対する申告を記録し、ゲームのpause状態を自動検証したとは扱いません。

ゲームを準備せずbuildと検証だけを済ませる場合も、同じ入口を使用します。

```powershell
& 'C:\Vic3Optimization-Diagnostic\tools\Invoke-Vic3Diagnostics.ps1' -PrepareOnly
```

## 結果を読む

| 結果 | 意味 | 次の操作 |
|---|---|---|
| `diagnosis_status=complete entry_status=modified connection_status=blocked`, exit0 | 完全な診断を収集したが、入口変更により接続拒否が継続 | 証拠を保存して終了。接続修正完了ではない |
| `diagnosis_status=complete entry_status=matched connection_status=entry_probe_passed`, exit0 | 入口の検査は一致。attachは実行していない | 証拠を保存して終了。接続成功ではない |
| `diagnosis_status=incomplete entry_status=unknown connection_status=blocked`, exit8 | 必要な検査・読取りを完了できなかった | ログのstage/API errorを確認し終了 |
| exit2/3/4等、対象拒否・起動失敗 | CLI/権限/対象build等の前提失敗 | ログを保全。強制注入・設定緩和・再試行で埋め合わせない |

旧診断版ではbyte_mismatchでもexit8でした。現在は診断収集と接続policyを別の結果型で扱います。`stage=byte_mismatch` と `connection_status=blocked` は保持します。終了コード0だけから接続可能、フック解除、Phase 4完了、性能改善を判断しないでください。

`local-data/diagnostics/<GUID>/` にcontext.json、diagnose.log、diagnose-exit.txt、構造化result.jsonを保存します。FILETIMEはJSONでは10進文字列として記録し、doubleへの変換で精度を落としません。出力された保存先を共有すれば、手入力のhashや異なるPIDの記録を混ぜず確認できます。

## 原因追跡の範囲

byte_mismatchかつ完全なE9 rel32 probeの場合だけ、最大4つの行先を同じhandleでquery/readします。各行先の16-byte完全読取、メモリ属性、一意のmodule所属、停止理由を記録します。循環、上限、アドレスoverflow、未知命令、読取禁止、API失敗で停止し、元の拒否を変更しません。module snapshotの失敗・曖昧さは所属不明とし、推測しません。E9以外、間接jmp、署名、hook ABI、書き込み主体、検査後の変更は判断対象外です。観測したアドレスを呼び出したり、注入入口へ使用したりしません。

安全な実ゲーム接続は引き続き未確認です。バイト比較削除、第三者hook解除、別APIへの推測fallbackは追加していません。
