# LoadLibraryW不一致の読み取り専用診断設計

Date: 2026-10-12 JST

## 目的・根拠

開始時に取得したmain `321064d479248153585c0e838f8c25836aeae783` を基準とする。[Issue #17](https://github.com/pengin0503/Vic3-optimazation/issues/17)と[既存調査](../reports/2026-10-12-game-attach-steam-overlay-byte-mismatch-ja.md)を参照した。接続拒否PID 16352と、ジャンプ経路観測PID 9280を同一実測として扱わない。

現行CLIは名前・x64・対応exe SHA-256を検証し、同じ絶対パスの所有DLLを一意に列挙、PEの.text/RVA/サイズ、remoteのcommit/execute-read、16-byte完全読取と一致を検証してからremote allocation/write/threadを行う。不一致は仕様どおりの拒否。ローカル/リモートの同じパス・サイズ・入口16バイトだけでは、関数全体・間接参照・他フック・検査後の変更まで証明できない。

## 方式比較と判断

| 方式 | 利点 | 未充足の安全根拠 | 判断 |
| --- | --- | --- | --- |
| 現行入口をフックごと呼ぶ | Steam処理を通過できる可能性 | 私有中継、第三者ABI・内部状態・ロード再入・変更競合を保証できない | 許可しない |
| KernelBase / LoadLibraryExW / LdrLoadDll等へ切替 | 別入口が未変更の可能性 | 内部実装や引数、他フック、Windowsビルドごとの経路、第三者との協調が未検証。LoadLibraryWとの同一性は仮定できない | 実装しない |
| ジャンプ先DLL名/署名を許可リスト化 | 観測した経路を識別できる | 署名/所属はメモリ中のコード全体や呼出安全性を証明しない。TOCTOUも残る | 実装しない |
| 独自stub/manual map/強制解除 | 既存入口を回避できる可能性 | 新しい実行コード・OS loader制約・第三者フック破壊。今回の禁止事項と安全基準に適合しない | 採用しない |
| fail-closed + read-only診断 | 注入せず同じPIDの証拠を増やせる | 接続問題自体は残る | 今回の採用範囲 |

Microsoftの[LoadLibraryW契約](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-loadlibraryw)は第三者detourを保証しない。[CreateRemoteThread](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-createremotethread)は不正な開始アドレスでも作成成功する場合がある。これらに観測事実を加えた上表の安全判断は本作業の推論であり、Windowsによる安全認証ではない。

## 採用設計

1. `--diagnose-loadlibrary --pid PID` の専用CLI経路。組合せはこの2オプションだけ。query/read権限だけでOpenProcessし、既存Victoria名前/x64/exe hash gateを通過する。DLL path・出力trace・named IPC・remote allocation/write/thread/stopは不要。成功exit0も診断収集が検査を通った意味だけで、attach成功ではない。拒否はexit8と診断を出す。
2. 診断と注入は同じresolverを利用。handleからGetProcessIdとGetProcessTimesを取得し、明示PIDとの一致を先に検証する。開始時刻はUTC FILETIMEの100ns値として記録。identity API失敗/不一致はfail-closed。既存injectorのhandle/PID混在を拒否する保護も追加する。
3. 診断v3に完全読取時のみ両方の16bytes、最初の不一致offset（0-based、なしは16）、不一致数を記録。不完全読取ではprobe_available=0、byte配列のログなし。再利用時の古いbyte診断はクリアする。
4. 完全読取したremote入口が`E9 rel32`の場合だけ、符号付き変位を境界検査して最初の行先を計算。行先は観測値であり、実行候補として使わない。VirtualQueryExで行先のstate/protection/type/allocation baseを追加観測する。追加query失敗は独立errorに保存し、元の拒否stage/errorは変更しない。行先のbyte読取・二段目追跡・DLL名への帰属・信頼判定は行わない。FF25や他の形式はunknownとする。
5. 既存16-byte比較・PE/module/protection/build gate、exit8、no retryを維持。現行の全メモリ検査が安全性を完全証明するとの主張もしない。

## 検証・完了境界

Pure policyテストで全16位置、複数差分、完全/部分読取、診断再利用、E9の正負/オーバーフロー/未知形式、stream書式を検証。Windows x64でread-only handleのresolver、handle/PID不一致、query失敗、既存synthetic hostへの注入と対象外CLI拒否を検証する。新しいゲーム内操作は行わない。ローカルTDDと必要なsuite後、PR作成時のCIを最終確認にする。

実ゲーム接続・Phase 4・性能向上は未確認のまま。診断は先頭と最初の行先だけであり、フック設置主体、最終行先、コード信頼性を証明しない。プロセスが検査中に変化する競合も解決しない。
