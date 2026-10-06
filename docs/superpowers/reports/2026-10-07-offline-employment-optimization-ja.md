# 実測を追加せず進めた雇用処理の軽量化調査
日付: 2026-10-07（日本時間）  
解析基準main: `7f2c5772de280481811562ecb6c4085f4e451a0c`  
対象: Victoria 3 Windows 1.14.5

## 成果と現在地
雇用準備の下流11 unwind群、14,543 bytesを新たに調査した。配列取得の呼び出しが、従来の3箇所に加えて前処理内にも存在することを確認した。検索成功位置を検証して再利用する方式を、捨てることを前提とした合成モデルで試した。9テストと25,676回の比較で不一致0件。

**ゲーム向け軽量化DLL、実行ファイルへのpatch、実ゲームでの速度改善は未実装・未検証。** 合成モデルを製品コードへ昇格させない。今回の結果は、次の設計を具体化するための研究成果である。

ユーザーの目的は、追加実測を待たず、文化・宗教・国数・更新頻度を変えずに軽量化を進めること。既存の測定や静的解析を捨てず、結果を保てる候補から進める。今後のゲーム向け実装は新しい仕組みなので、Superpowers brainstormingの書面設計・計画レビューを経る。

## 新たに確定した構造
### 同じitem-originに対する4つの配列取得site
以下は同一呼び出し系列に存在する静的siteであり、全てが毎回実行されることや、同じ配列が必ず返ることの証明ではない。

| 順序 | site → callee | 入力・役割の観測 |
|---|---|---|
| 1 | `0x13b8632 → 0xf3e040` | itemの+8をkeyとする取得。ID走査中に参照先+0x204を0へ書く |
| 2 | `0x10b7db4 → 0xf3e040` | `0x10bd4eb → 0x10b7c60` の下流。呼び出し元から渡された同じitemの+8をkeyとする取得 |
| 3 | `0x10bd565 → 0xf3e040` | 同じitemの+8をkeyとする取得。resolverと条件付きcalleeを伴う走査 |
| 4 | `0x10bd66b → 0xf3e040` | 同じitemの+8をkeyとする再取得。別アドレスのresolverを呼ぶ走査 |

4箇所とも同じGameState起点の+0x608、+0x120、+0x2f40の経路を辿る。item同一性はcallerの引数渡しとcalleeの保存レジスタから追跡した。ヘルパー・初期化・条件付き処理を挟むため、取得結果の寿命と変更可能性は未確定。

### ループの単純な融合は採用しない
`0x13b8650–0x13b8677` は全IDの+0x204をリセットしてから `0x10bd490` を呼ぶ。後続には `0x10b7c60`、`0x10b8810`、`0x10b9200` 等のcalleeがある。「1件リセット→同じ1件を処理」へ変えると、全件リセット済みという前提が失われる。これらのcalleeが別対象を読むかは未証明なので、今回の候補から融合を外す。

### 異なるresolverアドレスは別データベースの証明ではない
`0x85d7c0` と `0xc46bc0` のRIP-relative参照を独立計算した。
- database pointer global: 両方 `0x5a39c18`
- fallback pointer global: 両方 `0x5a37980`
- 初期化済み通常経路: 24-bit index、bounds、16-byte table-entry、pointer、full IDの検証という同じ命令構造

会話途中に述べた「別データベース」はこの照合で訂正した。両者の全例外・ログ経路の等価性や、呼び出し間のobject寿命まで証明したものではない。生object pointerの使い回しを正当化する根拠にはしない。

### 検索は成功経路と失敗経路を分ける
`0xf3e040–0xf3e0fd` の189-byte限定excerptに、4-byte keyのFNV型hash計算、40-byte slotの走査、key照合、descriptor（slot+0x10）へのreturnがある。成功側の限定excerpt内には書き込みとcallはない。

`0xf3e0ee` のtail-jump先 `0xf468d0–0xf469aa` は、TLSを読むguard、初期化候補call、globalへの書き込みを持つ。単に空配列を返す無副作用関数と扱わない。追加218-byte群を別途検証した。

`0xf3e040` には解決済みunwind metadataがなく、189 bytesは手動で限定した命令excerpt。完全なsource-level関数の復元とは呼ばない。失敗経路は元関数へ通すことを候補方式の必須条件とする。

### 一時bufferの持続化も直ちには行わない
`0x10c17f0` はsource pointerを0にし、destinationの旧pointerがあればdestructor候補 `0x1068cc0` とrelease候補 `0x421f980` を呼び、sourceを移す。単純なTLS buffer持続化は所有権・破棄時点を変える可能性がある。移動・破棄・nested配列の条件を確認するまで変更しない。

## 試した候補: 成功slotの検証付き再利用
生object pointerや配列内容のsnapshotは保存しない。直前に成功した検索のslot位置をhintとして扱い、次の取得時に現在のdescriptorを返す。

合成モデルでのhit条件:
1. map instance、table storage、mask、full keyが一致する。
2. 保存slotが保守的にprimary slot範囲内にある。
3. 現在のslotが有効で、現在のfull keyが一致する。
4. 条件を満たさなければ通常検索へ戻る。
5. miss/fallbackとtail slotはhintに保存しない。

scopeはhashとprobeの再実行回避のみ。全件reset、処理順序、RNG、object解決時のfull ID検証、例外・失敗経路を維持する方向の設計候補である。安定した成功keyを4回検索する合成例は、通常検索を1回へ減らした。**削減した検索数はCPU時間やゲーム速度の改善率ではない。** 検証・hook・TLSの費用で遅くなる可能性もある。

### 合成モデルの限界
モデルはvalidなRobin-Hood型tableの逐次アクセス、storageの安定した寿命、再配置の検出を仮定する。この仮定が実ゲームに成立することは未確認。
- table mutation、allocatorによるaddress再利用、並行アクセス、reentrancy
- control byte、padding/sentinel、capacityの完全なcontainer不変条件
- shared helperの全caller、RVAのsource名、内部ABI
- 正常な元検索が返すdescriptorとの実ゲームでの一致
- original callよりhit検証が安いか、hit率、全体への寄与

native版を設計するときは旧slotを読む前に現tableを検証し、解放済みaddressを読まない条件を説明する必要がある。tableのaddressだけの一致では生pointer再利用を許さない。今回のモデルはnative memory safetyの証明でもない。

## 検証結果と再現
- 元exe SHA-256と保存済み6群のinstruction bytes/range hashを添付へ再照合。
- 新規11群のchained unwind metadataを復元。最初の短いfragmentだけで判定せず、26→1,909、112→875、41→930 bytesの続きまで読んだ。
- 新規11群14,543 bytes、fallback群218 bytes、lookup excerpt189 bytesの命令をbyte完全一致で確認。
- selected direct E8/E9の相対targetを独立計算。
- 合成モデルは実装前の7テストFAILを観測後、9テストPASS。
- seed=20261007、1,000 table rebuild、25,676 query比較（成功13,676）、不一致0。
- 初期化・並行実行・native ABI・ゲーム状態・速度・multiplayer OOSは未検証。リポジトリの製品コードを変更していないので既存suite全体は実行していない。

[コンパクトな証拠](../../../research/generated/employment-reuse-2026-10-07/evidence.json)にgroup metadata、range hash、限定witnessを保存。生exeと巨大な全命令dumpは追加しない。

[モデルsource](../../../research/generated/employment-reuse-2026-10-07/model-source.py.txt)と[test source](../../../research/generated/employment-reuse-2026-10-07/model-tests.py.txt)は**捨てる前提の研究用source witness**。実ゲームへ接続するコードではない。再現する場合は独立した一時directoryへそれぞれ `slot_hint_model.py` と `test_slot_hint_model.py` としてコピーし、`python -m unittest discover -s <一時directory> -v` を実行する。製品の `src/` に移さない。

新しいcallee群は既存 `research/recipes/inspect_deep_native_groups.py` へevidence.jsonの `new_groups[].entry_rva` を渡して再生成できる（既存Capstone依存が必要）。metadata不在のlookup excerptは同recipeで除外されることを維持し、保存witness bytesとhashだけを限定範囲で照合する。

## 次の設計案と承認対象
推奨は、**検証付き検索hintをnativeから独立した試作coreにし、先にshadow比較まで設計する**こと。全面的なループ融合、object pointer持続化、buffer持続化より変更対象を狭くできる。

実ゲーム用新subsystemの書面設計では、exact-build検証、対象callsiteと内部ABI、container不変条件、TLS/reentrancy、shadowの観測費用、fail-closed条件、可逆なfeature flagを定義する。shadowは返り値を変更せず、元検索結果と候補結果の一致/不一致と件数を観測する。不一致や不明な寿命条件があればnative最適化へ昇格しない。shadow自体もゲーム内の負荷・安定性検証を要する。

代替はcall-localなdescriptor引数渡しだが、call間のmutation証明と関数再構築範囲が広い。現時点では推奨しない。元のTask 9 profiler完成・復旧は別作業として維持し、この調査をprofiler修正の成果と混ぜない。

今回の承認対象はこの設計方針。承認後に正式specを作成し、その書面レビューを経て実装計画を作る。書面spec・計画の承認と必要な実ゲーム検証が済むまで、native性能patchを投入しない。

