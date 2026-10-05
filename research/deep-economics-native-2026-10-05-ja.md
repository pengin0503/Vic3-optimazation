# 投資・移民・雇用のnative内部構造：追加証拠

2026-10-05 / Victoria 3 Windows 1.14.5 / 解析基準コミット `2bde7dc`。

既存資料のPrepare・callback・scheduler対応より下流へ進み、ID解決、疎なコンテナ走査、雇用の一時配列、投資処理の入れ子ループを確認した。**根本原因や最適化対象はまだ確定しない。** 今回の成果は、ゲームの計算内容を減らさずに調べられるnative候補を、具体的な命令位置と実行時の確認条件へ落としたこと。

入力は `E:/Vic3_data.zip`、124,462,636 bytes、SHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`。実行ファイルSHA-256は `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。実行ファイルはメモリ内で読み取り、コピーを出力せず、ゲーム・MOD・セーブ・プロセスを変更していない。

## 新しく具体化した候補

| 対象 | 命令列で確認した構造 | 実行時に確認すること |
|---|---|---|
| 民間投資 | `0xf771a0` は8-byte pointerを2配列から同じoffsetで読む外側ループ。途中に24-byte slot走査・整数除算・`0xf5df00`の反復callがある | 配列item数、slot占有率、内側反復回数、CPU sampleの内訳 |
| 経済移民 | `0x11aec40` は32-byte record反復。検証後の`0x12addb0`にkey処理・24-byte slot走査・inline8件の一時配列がある | 32-byte record数と検証失敗、slot走査、8件超過のallocation経路 |
| 雇用更新 | reset pass → 雇用収集候補内で同じID配列への別pass →さらに異なる型のresolverによるpass | 配列の同一性、途中の変更、順序依存、ID解決のCPU/cache費用 |
| 雇用収集 | linked nodeのindicesを統合し、capacity不足ならallocate/copy。4-byte数値sortの後に40-byte recordの深い処理へ進む | 統合batch数とcopy量、sortの費用、`0x10bdb50`の費用を分離 |
| 複数対象の共通処理 | 移民と雇用が`0x12a4ee0`（2406 bytes）を共有。投資・移民・雇用にID/table/page解決の共通先がある | 同じRVAをcaller stack付きで各taskへ帰属し、data latencyを確認 |

### 投資：外側item数だけでは計算量を説明できない

`0xf771c2–0xf771cd` はend-beginを8で割り、`0xf77544` がindex offsetを8増やして `0xf7755b → 0xf77210` で反復する。`0xf77309–0xf77361` は24-byte刻みのslotを走査し、`+4`のbyteがゼロのslotを飛ばして `+0x10` の64-bit値を合計する。

その後 `0xf7739e/0xf773de/0xf77406/0xf77418/0xf77427` に条件別の整数除算がある。全5箇所を毎回実行するという意味ではない。`0xf77489` で `0xf5df00` を呼び、成功側で `ebx` を減らし、`0xf77504 → 0xf77480` で正の残数を反復する。ここまでで「itemごとに一定費用」と置く仮説は弱くなる。整数演算、slot走査、内側call、子関数の費用を分けて計測する。

### 移民：検証とkeyed-container処理を分ける

`0x11aec4e` のcount×32、`0x11aed6f` のstride32を確認した。3つのvirtual validity候補call `0x11aec92/0x11aecaf/0x11aeccc` がfalseの場合、分岐先は次recordではなくepilogue `0x11aed7c`。その静的構造を「無効recordをskipして続行」と読み替えない。

`0x12addb0`（2082 bytes）では `0x12adf10–0x12adf44` に4 byteのkeyを `xor 0x811c9dc5` と繰り返す `imul 0x1000193` で組み合わせる形、`0x12ae0c0–0x12ae1dd` に24-byte slotの占有フラグ走査がある。具体的なsource container名・計算量は未確定。

`0x12adfe4` のRTTIは `CPdxHybridInlineBufferAllocator<pair<TPdxRef<CPop>,long long>,8,int>` を示す。`0x12ae02f` の容量8と、`0x12ae067` の必要件数×16 bytesのallocator call、`0x12ae091` のcopy、`0x12ae0a1` のreleaseが対応する。これで一時配列の件数が多い場合のallocation候補を絞れるが、overflow頻度や実費は未計測。

### 雇用：resetと後続収集に複数のID走査がある

本体候補 `0x13b8540` は `0x13b8632` でID配列を取り、`0x13b8650–0x13b8677` で各4-byte IDを `0x85d7c0` へ渡し、返るobjectの `+0x204` をゼロにする。その直後 `0x13b8693` で呼ぶ `0x10bd490` も、同じitem-originの `+8` をkeyとして `0xf3e040` からID配列を得て、`0x10bd580–0x10bd5da` で同じresolverを反復する。

さらに `0x10bd66b` がID配列を再取得し、`0x10bd680–0x10bd6aa` は `0xc46bc0` で解決する。**同じresolverを2回呼ぶことは、仕事が不要という証拠ではない。** reset後のcalleeが値・配列を変える可能性があり、順序依存も残る。確認対象は重複取得・解決のcache/locality費用と、再利用できる範囲。

### 雇用：大きいstack領域には実在するinline allocator型がある

`0x10bd4a8` は `0x220f0`（139,504 bytes）を読み、helper call後の `0x10bd4b2` で `rsp` から引く。4つの初期化helperのRTTIは `CPdxHybridInlineBufferAllocator` の `SEmployee`、`SEmployment`、各pointer型を示す。value bufferのfast pathは容量256、pointer bufferは1024。大きいstack領域を見ただけで、大量heap allocationや全領域の毎回zero-fillと断定しない。

allocation候補 `0xc2eb30/0x630380` は自身のslot7を呼び、その戻りobjectのslot1へtail-jumpする。release候補 `0xc2eaf0/0x630340` はpointerが`this+8`のinline領域ならそのまま戻り、その他は戻りobjectのslot2へ進む。これにより、inline hit、overflow、共通allocatorへの委譲を分けた計測候補になった。`0x10c2b70`には384-byte elementを反復し、nested arrayを解放する処理もある。

### Collect・sort・深い雇用更新の区別

Collect callbackの `0x13cadd0–0x13cadea` はnodeの `+0x20` をたどり、`0xc24140` にsource pointer・count・挿入位置を渡す。`0xc24160` はold_count+incoming_countとcapacityを比較し、growth側ではallocator→3つの条件付きcopy→`0x64b2f0` へ進む。capacity内では末尾へcopyして `0x64d790` へtail-jumpする。これは3つのcallを持つ並べ替えhelper候補だが、各call先 `0x422fc70` はunwind metadataがなく、reverse/rotateのsource名は認定していない。

小範囲sort候補 `0x13c54c0` にはbyte span128の分岐、再帰call、4-byte値の比較・移動がある。pivot候補 `0x13cb1d0` はraw32-bit値を比較・交換し、objectの取得やindirect comparatorは使わない。したがってこの段はindexの数値ordering候補。後続のSortEmployment callback `0x13cad10` はsorted indexから40-byte recordを選び `0x10befb0 → 0x10bdb50` へ進む。sortの名前だけでこの全経路の費用をsort自体へ帰属しない。

### scheduler以外の共有native候補

`0x12ae4e6`（移民）と `0x10bf01b`（雇用）は `0x12a4ee0` を直接呼ぶ。投資 `0xf5e082` と移民 `0x12adfa6` は `0xcb4ba0` を共有し、投資 `0xf5df49` と雇用 `0x10bd68f` は `0xc46bc0` を共有する。

`0x7ed5f0/0x85d7c0/0xcb4ba0/0xc46bc0` の通常側には24-bit index、bounds check、16-byte table-entryからのobject pointer取得、full ID照合、fallbackの共通形がある。`0x13712b0` はlive-bit確認後に `ID>>10` のpageと `ID&0x3ff` の16-byte elementを求める。ここで調べるのはlookup回数、invalid-reference頻度、pointer/data cache latency。共有call先であること自体はlock、critical path、hotspotの証明ではない。

## 保存したデータと確認結果

- [findings.json](generated/deep-native-2026-10-05/economics/findings.json): 6候補の観測命令位置、解釈、各候補に必要なruntime probe。archive/exeのhashとscopeも記録。
- 5組の選定decode JSON/TXT: `first-pass`、`economics-inner`、`shared-helpers`、`employment-buffer-init`、`allocator-continuations`。各範囲のhash・全命令bytes・direct/indirect call・RTTI・backward branchを保存。
- [inspect_deep_native_groups.py](recipes/inspect_deep_native_groups.py): 特定RVAのunwind群だけをdecodeする読み取りrecipe。1群8192-byte制限、partial decodeなら停止。metadata不在は除外。
- [finalize_deep_native_economics.py](recipes/finalize_deep_native_economics.py): 保存命令bytesをexact binary範囲と再照合し、E8/E9 displacementを独立計算。[artifact-index.json](generated/deep-native-2026-10-05/artifact-index.json) は保存物のhash。[再生成手順](deep-native-reproduction-2026-10-05.md) を参照。

35選定unwind群、20,495 bytesを全decodeし、保存した命令bytesと入力範囲の一致・範囲hashを確認。341個のE8/E9 direct edgeを独立計算で照合した。`0xc29dc0` と `0x422fc70` はmetadata不在で除外。backward branch一覧は検出候補で、epilogueへ戻る分岐やexternal tail-jumpを含み、全てをloopとして数えない。

これは**選んだ範囲の線形静的解析**であり、完全なcall graph、実行到達性、task全体、runtime時間、競合、cache miss、効果を確認したという意味ではない。計算削減・閾値変更・native patchは0件。次のOS CPU stackとmemory-access計測は、上の候補ごとの反証・確認に使う。ASLRはそのrunのmodule baseを使ってRVAへ変換する。
