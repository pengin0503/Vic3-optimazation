# 実ゲームattach失敗の調査記録 — LoadLibraryWからSteam Overlayへのジャンプ経路

Date: 2026-10-12 JST  
対象: pengin0503/Vic3-optimazation / Windows Victoria 3 1.14.5  
状態: **原因の局在化が進んだが、attachは未成功。Phase 4実測ゲートはblockedのまま。**

## 1. 結論と証拠の境界

- **観測済み:** disabled modeのネイティブProfiler Loaderが `Attach failed (no retry), code 4` / exit 8で失敗。詳細段階は `byte_mismatch`。これは同一APIアドレスのローカル/ゲーム側の先頭16バイト不一致による、DLL注入前のfail-closed拒否である。
- **観測済み（後続の別プロセス）:** `KERNEL32.DLL!LoadLibraryW` のゲーム側入口は `E9` detourに変更されており、16 KiBの `MEM_PRIVATE` / `PAGE_EXECUTE_READWRITE` 中継領域を経由し、**Steam `gameoverlayrenderer64.dll` の `MEM_IMAGE` 実行領域**に到達する。
- **強い示唆:** Steamゲーム内オーバーレイのコード経路が、このAPIフックに関係する。**ただし、フックを最初に設置した主体、Steam Overlay無効化時の挙動、全プロセスでの再現性は未確認**。ジャンプ先がSteam DLLであることと「Steamが直接パッチを書いた」との主張を区別する。
- **重要な境界:** 実際にLoader接続が失敗したゲームのPIDは `28636`、後続の読み取り専用メモリ検査を行ったゲームのPIDは `3584`。それぞれ別プロセスで、同一個体の連続記録とは扱わない。
- **未実施:** disabled attach成功、stop/finalize、3 target enabled、TickTask CSVとの同期、observer overhead、OS Running/Ready/Waiting採取、速度改善やネイティブ最適化。

## 2. 実ゲーム接続失敗 — PID 28636

ユーザーがWindows実機で取得し、ZIPとしてチャットに提出したA（disabled attach）のログに基づく。

| 項目 | 証拠 |
| --- | --- |
| Victoria 3対象ファイル | `victoria3.exe` SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`（対象ビルドと一致） |
| 初期セーブ | `アメリカ合衆国_1911_03_01.v3` SHA-256 `08d22b19929a5ec480e3e45f4e1eb8ff581b91e1de1b4bdb16512e3d0ea5e949` |
| Loader | SHA-256 `2abbfcd6e1dcb69a967b3e9a24f7e9270e080767f24a364741636d90f34770bc` |
| Profiler DLL | SHA-256 `39d14473352914bc51d2eb015d3c053604d6f5be45ad058f27402b7ece5e790d` |
| Profilerソースビルド | `a101c56a7dcb33b9361677e99f146ae10b3ef831`（CI artifact provenance） |
| OS | Windows 11 Home / 10.0.26200 |
| PID / プロセス開始UTC | `28636` / `2026-10-12T09:40:55.1123778Z` |
| 実行方式 | `--disabled`; hookが有効化されたことを示す結果なし |
| 結果 | `Attach failed (no retry), code 4`; `AttachExit=8` |

完全な診断出力の主要部分：

~~~text
Module resolution diagnostics v2: stage=byte_mismatch win32_error=0 pe_error=0
owner_path=C:\WINDOWS\System32\KERNEL32.DLL local_size=831488 remote_size=831488 export_rva=257584 matches=1 bytes_read=16 remote_state=4096 remote_protection=32
local_base=140718582595584 local_address=140718582853168 remote_base=140718582595584 remote_address=140718582853168
~~~

- `export_rva=257584 = 0x3EE30`、`matches=1`、ローカル/ゲーム側のモジュールサイズ、ベースと対象関数アドレスは一致。
- `remote_state=4096 = MEM_COMMIT`、`remote_protection=32 = PAGE_EXECUTE_READ`、16バイトの読取に成功し、その内容が不一致。
- `win32_error=0` / `pe_error=0` は比較上の拒否であり、Windows APIの呼び出し失敗を示さない。
- `Injector.cpp` ではこの拒否が `VirtualAllocEx` / `WriteProcessMemory` / `CreateRemoteThread` の前にあり、この試行でDLL注入は開始されていない。
- 同一ログ内の `loaded-modules.csv` には120モジュールがあり、少なくとも `gameoverlayrenderer64.dll`（Steam）と `amdihk64.dll`（AMD）の読み込みを確認。読み込まれていること自体は関数変更の原因証明ではない。
- 接続失敗後の同一ゲームプロセスに対するretry / stop / enabled再attachは実施対象外とする。

## 3. 別プロセスでの読み取り専用メモリ検査 — PID 3584

以下はユーザーのPowerShell出力と提出JSONに基づく。PID 28636の失敗ログとは別のゲームプロセスである。**PID 3584について、同じexe/save hashを独立に採取した記録は提示されていない。**

### 3.1 LoadLibraryW入口の比較

| 項目 | 値 |
| --- | --- |
| 調査PID | `3584` |
| `KERNEL32.DLL!LoadLibraryW` RVA | `0x3EE30` |
| 関数入口 | `0x00007FFB9924EE30` |
| PowerShell側16バイト | `48-FF-25-C9-C5-04-00-CC-CC-CC-CC-CC-CC-CC-CC-CC` |
| Victoria 3側16バイト | `E9-57-13-FF-FD-04-00-CC-CC-CC-CC-CC-CC-CC-CC-CC` |
| 判定 | `equal=false` |

PowerShell側は `48 FF 25 ...`（RIP相対の間接jmp）、ゲーム側は `E9 57 13 FF FD`（5バイトの相対jmp）で入口が異なる。ゲーム側の相対変位は `-33,615,017`、ジャンプ先は `0x00007FFB9724018C`。

**診断スクリプトの初回出力に現れた全ゼロ `game_bytes` は無効な結果。** PowerShellの `UIntPtr` 型変換例外によりメモリ読取が実行されなかったためで、上表はそれを修正し、実際に16バイト読み取った後の結果のみを使用している。

### 3.2 第1ジャンプ先：private実行メモリ

| 項目 | 値 |
| --- | --- |
| ジャンプ先 | `0x00007FFB9724018C` |
| RegionBase / AllocationBase | `0x00007FFB97240000` / 同じ |
| RegionSize | `16384` バイト（16 KiB） |
| MemoryType | `MEM_PRIVATE` |
| StateHex | `0x1000`（MEM_COMMIT） |
| ProtectHex | `0x40`（PAGE_EXECUTE_READWRITE） |
| MappedFile | 取得できず |
| 読み取った先頭16バイト | `E9-9F-D5-9E-A8-00-00-00-00-00-00-00-00-00-00-00` |

先頭の `E9 9F D5 9E A8` は再び相対jmp。変位 `-1,465,985,633` を用いると次のジャンプ先は `0x00007FFB3FC2D730`。

途中で `Marshal.SizeOf([Vic3MemoryInfo])` のPowerShellオーバーロード解決エラーが生じたが、構造体のインスタンスを渡す方式に修正後に上表のメモリ属性を取得した。これは検査スクリプト側の障害であってゲーム側の失敗ではない。

### 3.3 第2ジャンプ先：Steam OverlayのDLL内

ユーザーが同じPIDで報告した最終結果：

~~~text
ジャンプ先の所属モジュール:

ModuleName  : gameoverlayrenderer64.dll
FileName    : C:\Program Files (x86)\Steam\gameoverlayrenderer64.dll
BaseAddress : 140717082542080

Target     : 0x00007FFB3FC2D730
MemoryType : MEM_IMAGE
ProtectHex : 0x20
MappedFile : \Device\HarddiskVolume3\Program Files (x86)\Steam\GameOverlayRenderer64.dll
~~~

- 第2ジャンプ先のモジュールベース `0x00007FFB3FB80000`、DLL内相対オフセット `0xAD730`。
- `MEM_IMAGE` / `PAGE_EXECUTE_READ` と、Windowsのマッピングされたファイル名の双方がSteam `gameoverlayrenderer64.dll` のコード領域への到達を裏付ける。
- したがって、**観測したゲームプロセスのLoadLibraryWは private領域を経由してSteam OverlayのDLLへ制御を移している**。これがSteam Overlayの関与を示す最も強い実ゲーム証拠。
- ただし `gameoverlayrenderer64.dll` 内の逆アセンブル、パッチ実施主体の追跡、Steam Overlayを無効にした比較、PID 28636の同じチェーン採取は未実施。第2ジャンプ先がSteamに属することは、Steam単独の責任や悪性挙動を証明しない。
- `PAGE_EXECUTE_READWRITE` のprivateメモリの存在だけでマルウェア、障害、ユーザーデータへの影響を推定しない。

## 4. 開発上の評価

リポジトリの `src/native/loader/Injector.cpp` は、呼び出し先のowner moduleを列挙し、対象 `LoadLibraryW` のローカル/リモート先頭16バイトを比較する。実環境で入口が別のdetourに変更されていると、`byte_mismatch` でfail-closedになる。これは**拒否が意図どおり動いた**記録であって、プロファイラーが正しく接続できたことや最適化できたことではない。

現時点で以下を行わない：

- 先頭16バイト検証の無条件削除、コードアドレスの推測fallback、安全検証の回避。
- 同じゲームプロセスへの失敗後再attach。
- ゲーム実測Phase 4 gateをready扱いすること、CPU高速化の主張。
- 単独のモジュール一覧だけを根拠にSteam/AMDが原因と断定すること。

## 5. 次に実施可能な最小の対照試験（未実施）

1. **SteamのVictoria 3個別設定で「ゲーム中にSteamオーバーレイを有効にする」を無効化**し、ゲームを完全終了後、新しいPIDで通常起動する。Windowsセキュリティ機能や検証gateは変更しない。
2. exact 1.14.5のゲーム実行ファイルと同じLoader/DLLのSHA-256、初期save、PIDとprocess start UTCを保存し、`LoadLibraryW` 入口16バイトの読み取り専用比較を再実行する。Steam overlay DLLのロード有無も記録する。
3. 前提と照合が合った場合だけ、**新しいゲームプロセス**でStep Aのdisabled attach/stopを試行し、成功/拒否ログを保存する。不一致やcode 4ならそこで停止。
4. もし無効化後も同じ不一致があるなら、原因をSteamだけに限定せず、別のフック経路を同様に調べる。AMD Overlayなどの影響は一条件ずつ比較する。
5. 接続が成功しても、その後にStep B（3targets enabledの短い確認）とStep C（観測負荷とOS状態の本測定）が必要。ゲーム内の機能・速度改善を自動認定しない。

この調査報告は**情報の保存のみ**であり、製品コード・検証policy・Windows設定・CI・セーブデータは変更しない。

## 6. 一次証拠と参照先

- ユーザー提出ZIP: `disabled-8c2d6d7b9deb45868d0ab06e9c0f1845.zip`、SHA-256 `bc8be55ba4a84c98bf6d44498c862b539cfe62d9119b906b7b47f43a490dc5ae`。中身は `attach-exit.txt`、`attach.log`、`context.json`、`identity.log`、`loaded-modules.csv`、`modules.log`、`windows.log` の7ファイル（計測専用の新しいV3PFは作成されていない）。
- ユーザー提出JSON: `loadlibrary-byte-comparison.json`、SHA-256 `fce00af22df913c145ce443458fb6c970b8ca4323e7b14b5313efebb66e1199c`。
- 第1/第2ジャンプ先のメモリ属性・Steam DLLの所属確認はチャット上のユーザー提供PowerShell出力。対応するJSONの原本はこの記録の時点では添付されていない。
- [最初の実ゲーム検証ガイド](../guides/2026-10-12-user-game-validation-first-pass-ja.md)
- [ネイティブLoaderの実装](../../../src/native/loader/Injector.cpp)
- [Phase 4 runtime gate](2026-10-12-cpu-runtime-evidence-gate-ja.md)

プライバシーとサイズのため、Windowsのユーザープロファイルへの絶対パスや実行ファイル、セーブ、上記生ログ/ZIPはこのGitHub文書へ添付しない。証拠の値・取得範囲・ハッシュのみを記録する。
