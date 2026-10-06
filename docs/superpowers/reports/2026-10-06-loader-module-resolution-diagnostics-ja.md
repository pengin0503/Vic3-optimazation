# Loader ModuleResolution 診断追加

## 実ゲームからの報告

Windows 11 Home build 26200、exact Victoria 3 loader の disabled attach が
`Attach failed (no retry), code 4` で停止。PowerShell からゲーム本体の PID / path、
System32 の KERNEL32.DLL (831488 bytes) / KERNELBASE.dll (4202496 bytes) を取得できた。
ただし、PowerShell の列挙成功は loader 内の各 API / byte comparison の成功を保証しない。
OS バージョンが原因とは断定していない。

## 変更

従来は export lookup、owner PE、実行可能 .text、module path/size、remote page protection、
16-byte read/一致をすべて code 4 にまとめ、失敗した条件を特定できなかった。
既存の判定条件と順序、explicit-PID / exact-build gate、single snapshot を維持し、
ModuleResolution failure だけ stage と関連値を標準エラーへ出力する。

- Win32 API failure は直後の GetLastError を保存する。
- comparison failure は win32_error=0。古い API error を原因として出さない。
- owner path、local/remote image size、export RVA、match count、read count、
  remote state/protection、typed PE error を記録する。
- remote allocation/write/thread creation の前で、従来どおり失敗終了する。
- fallback、retry、権限変更、security bypass、hook 対象追加は行わない。

## 検証

診断出力の回帰テストを先に追加し、未実装の diagnostics API で RED を確認。
実装後に Linux g++ の loader-options / diagnostics tests が GREEN。
Python 全体テストの初回は実行環境の capstone 未導入により errors=3 / skipped=13。
既存の tools/requirements-callgraph.txt を導入した再実行は 142/142 成功、skip なし。
target include --check / git diff --check 成功。

Windows CTest に実 API の負ケースを追加した。nonexistent PID は snapshot stage、
null process handle は remote_query stage / ERROR_INVALID_HANDLE として拒否し、
helper DLL の probe event が未通知のままであることを確認する。成功した helper injection は
stage=none / win32_error=0 とし、既存の injection / wrong-process / stop 回帰も実行する。
Windows 実行結果はこの変更 commit の GitHub Actions に記録する。Linux の成功から推測しない。

## 未解決と次の確認

この変更は原因を特定するための診断追加であり、実ゲームの attach failure 自体を
修正したという主張ではない。Windows 11 build 26200 での stage ログが次の入力。
診断版の DLL/exe を同じ CI artifact から取り出し、disabled mode で新しい出力ファイル名を
指定して実行し、Module resolution diagnostics v1 の2行を含むログを保存する。
