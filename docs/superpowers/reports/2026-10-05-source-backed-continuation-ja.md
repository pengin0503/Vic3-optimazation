# 添付ビルド・GitHub実測データからの作業継続

2026-10-05 / `pengin0503/Vic3-optimazation`

今回進めたのは解析ツールの修正と、実測上位3処理の内部構造調査。
ゲームへの性能変更・DLL注入は未実施。MOD完成や速度改善を確認した段階ではない。
前の [実測引き継ぎ](2026-10-05-runtime-benchmark-handoff-ja.md) の結果を維持し、
以下を最新の解析・再開状態とする。

## 情報源の確認

- 開始main: `aba95bf96678a3b2d9514ff8e4f2498e35ce53fd`。
- 添付 `Vic3_data.zip` のCRC検査成功。ビルド識別子4件が既存資料と一致。
- 実行ファイル: 97774200 bytes、SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。
- GitHubの3か月CSVは3条件ともmanifestのSHA-256と一致。各23445行、368frame、frame/task/calls一致。
- 実測: 8=37.51秒、12=36.67秒、16=34.64秒。各条件1回。16を暫定診断条件として維持。

元の実行ファイル・ZIPは解析入力として読み取った。リポジトリには派生コード・結果・資料のみ追加する。
private repositoryのGit cloneに利用できる認証がないため、GitHub connectorから固定commitの
テキストsnapshotを取得して作業した。サイズ制限で取得できなかった旧1件の大型解析JSONは
今回の入力に使わず、GitHub側では元のtreeを基に更新して保持する。

## 解析ツールの修正

### 分割された関数範囲

既存 `tail_runtime_function` は最初のRUNTIME_FUNCTION断片だった。
開始・終了・unwindの組でchainを再帰の代わりに反復でたどり、別フィールド
`tail_function_group` にroot、断片、分離した範囲、実際に含まれるbytesを記録する。

- 経済移民: 10bytesの先頭断片 → 3断片、478bytes、`0x11b0c00–0x11b0dde`。
- 非連続範囲の隙間は関数に含めない。
- 同じunwind情報を共有する別関数を統合しない。
- 循環、不正参照、未対応version、切れたデータ、重複/同開始範囲は明示的にinvalid。
- 元のsignature位置18件、最初の断片フィールド、過去の解析JSONは維持。

方式は [Microsoftのx64例外処理仕様](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64) と照合した。
実ビルドは252752断片、invalid=0、258クラスをマッピング。

### 単発測定のばらつき

以前は `CV=null` でも `noisy=false` と出力し、本文のCVを0%にしていた。
比較ツールもFalseを根拠に単発測定をplateauと扱う場合があった。

- 未算出のCV/ノイズはnull / `unknown` と表示。
- 反復性の評価には同条件3回以上と算出可能なCVが必要。
- 単発・2回・情報欠落・旧形式のCV=nullはplateauの根拠にしない。
- 旧形式のTickTask対応表にある `CV=null, noisy=false` も、新出力では不明へ正規化。
- 新しいbenchmark/scaling JSONはformat_version=2。nullをFalseとして扱わない。
- 低いCVだけで改善差の統計的有意性を証明しない。

再集計後も所要時間と順位は変わらない。8→12→16のplateau判定は全て不明。
誤った安定性の表示を直したのであり、追加測定値を作ったわけではない。

## 新たな内部対応

3処理の入口で作られるMSVC RTTI付きcallable vtableを照合した。

| 処理 | Prepare周辺の入口 | callback候補を経た処理本体候補 | 本体候補bytes |
| --- | --- | --- | ---: |
| 民間投資 | `0xf6e590` | `0xf7ec40` → `0xf8a290` → `0xf771a0` | 1039 |
| 経済移民 | `0x11b0c00` | `0x11baee0` → `0x11bed40` → `0x11aec40` | 341 |
| 雇用更新 | `0x13b8310` | `0x13caed0` → `0x13b8540` | 549 |

矢印は、RTTI付きvtableの参照関係と直接callを組み合わせた静的対応。
実際にこの順で必ず実行されるという観測ではない。
雇用更新にはさらに `CollectEmployment` の型名を含むcallableが見つかった。
詳細とOS照合位置は [callback対応表](../../../research/ticktask-callback-map.md)。

深さ2の静的グラフは39関数群・12077bytesをdecode、直接edge136、間接call/jump箇所63、
vtable参照11件。全範囲をdecodeできたが、79先が未展開。
完全な実行経路、task dependency、scheduler到達性の証明にはしない。
候補callback/本体6範囲を別のJSONへ記録した。

`tools/map_hotspot_calls.py` を追加。実行ファイルhashとRTTIのhashを照合してから解析し、
深さ・件数・サイズを制限する。直接call、tail jump候補、コードポインタ、vtable slot候補を分離。
Capstoneはこのツールだけの追加依存。従来の静的抽出・unwind・CSV解析は標準Pythonのまま。

## 保存した派生結果

[runtime-followup-2026-10-05](../../../research/generated/runtime-followup-2026-10-05/) に:

- 修正後benchmark JSON/Markdown（公開部分は各groupのcost/lock上位20、全件集計はraw CSVから再生成可）。
- thread-scaling JSON/Markdown。
- native-targets、主要3件のRTTI/断片、39関数群のcallgraph、限定callback解析。
- 18signatureの再検証、入力由来と生成ファイルのSHA-256。

最適化の暫定判断表は [candidate-hotspots.md](../../../research/candidate-hotspots.md)。
根本原因・改善率の上限は未算出、選定patchは0件。

## 検証

- TDD: chain、単発/旧形式ノイズ、callgraph/vtable、triage連携の再現テストを修正前に実行し、失敗を確認してから修正。
- 独立レビュー: 旧形式の不明CV、重複した関数範囲の2指摘を再現し、回帰テストを追加して修正。未対応のコード指摘なし。
- `VIC3_DATA=<添付ZIP> python -m unittest discover -s tests -v`: **62 tests、全てpass、skipなし**。
- 静的pipeline: 260 TickTask名、258 RTTI対応、source paths 920、signature18/18一致。
- 入力CRC/hash、CSVのframe/task/calls、派生JSON、相対リンク、callbackの仮想関数slot、直接callアドレスを照合。

これらは解析コードと派生結果の検証。実ゲームでの性能改善やnative hook動作の検証ではない。

## 判断と残る証拠

1. 既存承認済みの測定優先方針の範囲で、解析の不備を修正し、3対象の構造を掘り下げた。新しいゲーム動作やhookアーキテクチャは導入しない。
2. private Gitの認証制約に対して、固定commitのsnapshotと元treeに対するconnector更新を使用する。未取得の旧ファイルを削除しない。取り違えた場合のriskは誤ったbaseへの更新なので、保存直前のmainと変更パスを確認する。
3. 元の断片フィールドとsignatureは保ち、復元範囲・新形式結果を別に保存する。誤って既存locatorを変えるriskを避ける。
4. 未測定の実行到達性・実際のcallback呼出し・ソース関数名・待ちの原因・性能効果は未確定として扱う。これを誤って断定すると、誤った関数の計測やゲーム挙動を変えるpatch選択につながる。

Phase 1〜6のIssuesは未完了の証拠が残るためopenを維持。
Phase 1の「実測未取得」という旧状態は更新するが、繰り返し測定・OS記録が揃ったとは扱わない。

次に必要なのは同じ3か月・16スレッドのOS CPU/待ち/context switch記録。
設定順位とノイズを確定するときは同期間の8/12/16各3回。
1〜16全条件の取り直しを、内部構造調査を続ける前提にはしない。

## 再開手順

1. この報告、callback対応表、candidate-hotspotsを読む。
2. 次の手順で派生結果を再生成する。
3. OS記録が来たら候補のRVAとCPU sample/待ちを区間で照合。
4. native prototypeは既存設計のversion/signature/ABI/overhead条件が満たされた後に進める。

```text
python tools/analyze_benchmarks.py benchmarks/measured-2026-10-05-3month --json local-data/bench3.json --markdown local-data/bench3.md
python tools/analyze_thread_scaling.py local-data/bench3.json --json local-data/scaling.json
python tools/map_ticktask_rtti.py <Vic3_data.zip> --output local-data/rtti.json
python -m pip install -r tools/requirements-callgraph.txt
python tools/map_hotspot_calls.py <Vic3_data.zip> --rtti local-data/rtti.json --task HandleAutonomousInvestment --task ProcessEconomicMigration --task UpdateEmployment --depth 2 --expected-sha256 9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54 --output local-data/callgraph.json
python tools/triage_benchmark_targets.py local-data/bench3.json local-data/rtti.json --variant baseline-no-active-mods --threads 16 --top 20 --json local-data/native-targets.json
```

Windowsゲーム環境がなくても、バイナリの静的decodeと上の解析はPython環境で行える。
ゲーム実行・OS記録・動作変更の実測確認はWindows側の作業。
