# 実ゲーム検証の最初のhandoff

Date: 2026-10-12 JST

実ゲームの最初の障害は接続・停止の成否であるため、[ユーザー手順](../guides/2026-10-12-user-game-validation-first-pass-ja.md)をA(disabled attach/stop)、B(3targets enabled smoke)、C(反復・同期OS・save/reload)へ分けた。最初はAのlogs/traceだけでよく、接続が失敗した状態で12本の反復を取得しない。

## 今回の非ゲーム作業

- 最新main `6584565`、研究branch `6535c2c` をfetchし、既存成果を確認した。
- 保存済みWindows artifact11706440529をAPIで確認。native-profiler-validation、89,625bytes、expired=false。対応run38148690363、build commit a101c56、binary hashはPhase3記録を使用する。native sourceはa101c56から変更されていない。
- [既存witness README](../../../research/generated/offline-closeout-2026-10-12/README.md)の出力directory不足を修正。CLI/interfaceや生成witnessの内容は変更しない。
- Loaderの実引数・ready/stop表示、parser引数、保存するPID/process/start/build identity、UTF-8 logs、再attach禁止を既存source/guideと照合した。Windows/PowerShell実行は未検証のまま記録する。
- user手順・ロードマップへの入口を保存する。新しいgame hook、観測API、GPU/kernel/性能patchは追加しない。

## ローカル入力の差分

開始時からworking treeの `input-data/Vic3_data.zip` がmodifiedだった。実bytesは71,705,600bytes、SHA-256 `42bd91eff6c50ea7252d5107242d16f883d8ad75a9c8e6ecc453be705eff24b1`。repositoryでpinした125MB archiveとは一致しない。原因や作成者を推定せず、その差分を保持し、commitしない。restore/reset/LFS pointer変更もしない。

添付コピーはSHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` と一致する。必要なwitness再現にはこのexact inputを利用する。現在のmodified working copyをprovenance-validと認定したり、過去の13/13 inventory成功をそのまま現在のworking copyへ拡張したりしない。

## 必要な次のユーザー結果

まず最新版binaryでAを実施し、identity/context/windows/modules、attach/exit、取得できたstop/parse/traceのfolderだけを送る。hash不一致や権限/loader起動問題も結果として保存する。game exe/save/DLL本体・GPU既存JSONの再提出はこのpacketに不要。

code4が出たらv2 diagnosticsを根拠に次の修正範囲を決める。A/B成功後に、Phase4のmatched boundary/overhead/OS state/save stabilityの証拠へ進む。手順作成やsynthetic CI成功は実ゲームでの成功ではない。

今回は文書の限定修正で、既存code/native/B0やそのunit suite、GitHub Actionsは再実行しない。Capstone5.0.7の一時環境で出力directoryを作成し、添付exact ZIPからwitness CLIを1回実行。保存済みJSONとbyte-identicalであることを確認した。対象Markdownのlocal links/code fencesとdiff --checkも確認した。初回link scannerはPowerShellの`[int](Read-Host...)`をMarkdown linkと誤認したため、code blocksを除外して再検査した。文書やproductの欠陥として扱わない。

PowerShell/Windows実行はこの環境では未検証。実ユーザーhostにおけるAの結果が、次に必要な証拠である。今回の変更に追加の実装subagentやreviewerは使用していない。確認済みartifactが期限切れになる場合は、既存build手順・自己build provenanceへ切り替える。
