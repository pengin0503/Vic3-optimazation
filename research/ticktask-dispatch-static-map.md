# TickTaskの実行経路と並列分岐の静的対応

Date: 2026-10-05
Build: Victoria 3 Windows 1.14.5
Executable SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

## 今回確認した接続

主要3クラスの末尾slot 6から得たPrepare周辺の入口に加え、共通dispatcher候補
`0x7dc160–0x7dc606` を確認した。この関数はタスク候補オブジェクトのslot 6を呼び、
戻ったcontext内のフラグ・callable・rangeを読む。その後、並列経路またはcallableの
直接呼び出しへ分岐する。ソース関数名と実際のtask identityは未確定。

| 種類 | 命令位置RVA | 静的に確認した内容 |
|---|---|---|
| task virtual dispatch | `0x7dc23e` | `[r14]`のvtableに対する`call [rax+0x30]`、slot 6。`rcx=r14`、`rdx`はローカルcontext候補 |
| conditional direct call | `0x7dc412` | `test al,1`による分岐の先で`0x7dbaa0`をcall |
| indirect callback call | `0x7dc47a` / `0x7dc4ca` | 上記callを通らない分岐で`call [rax+0x10]`。前者はrangeを1刻みで更新するループ内 |
| second indirect callback | `0x7dc4e0` | 別のcallable候補が非nullなら`call [rax+0x10]` |
| range runner → heuristic | `0x7dbde0` | `0x7dbaa0`の範囲内から`0x7db150`を直接callし、戻り値をtest |

`0x7dbaa0` / `0x7db150`の役割は既存の文字列・RTTI解析による候補名。
フラグbit 0を「常に並列で実行される保証」と解釈しない。heuristicが拒否した後の分岐、
実際のworker数、待ち、処理時間は別途確認が必要。

主要3クラスはslot 6が固有Prepare入口なので、上記slot呼び出しに対応する静的候補を
絞れる。8-slotクラスではslot 6が共有`0x7d76b0`なので、全258クラスの固有末尾を
同じslotで呼ぶという意味ではない。

## 直接callerを逆方向に確認した結果

file-backed executable section内のE8 rel32を検索し、unwind rangeの先頭からdecodeした
命令の位置・種別・targetに照合した。指定3targetについて候補4件、確認4件、棄却0件、
未解決0件。間接callやtail jumpのcallerは検索対象外。

| caller root RVA | callsite RVA | target RVA |
|---|---|---|
| `0x7e1820` | `0x7e18c3` | `0x7dc160` |
| `0x7e20c0` | `0x7e2678` | `0x7dc160` |
| `0x7dc160` | `0x7dc412` | `0x7dbaa0` |
| `0x7dbaa0` | `0x7dbde0` | `0x7db150` |

命令境界上のcallを確認したという結果。実行到達性、全callerの網羅、task間dependency、
ゲーム内ソースの関数名を証明するものではない。

## callableの移動と実行を区別する

Prepare周辺と後続callbackの複数箇所で呼ばれる`0x74f7b0–0x74f900`は、
2つのcallable候補の`+0x38`ポインタを交換し、必要時にslot 1で移す／複製する形を持つ。
この関数内に直接callはなく、slot 2の実行callもない。正確なC++シンボル名は未確定だが、
この共有callだけを「job dispatch」や「並列実行開始」と数えない。

主要3PrepareはRTTI付きcallableを構築し、このhelperを通じてcontext候補へ移す。
民間投資・移民では移動先としてcontext候補`+0x50`を渡す命令を確認。
共通dispatcher候補は、そのローカルcontext候補内のcallableポインタを読み、後続の
間接callに使う。これにより、前回のvtable参照関係を実行側の静的構造と対応付けられた。
実際のcallback identityやcontextの完全なABIはまだruntimeで検証していない。

また、共有slot 3の`0x3bf72f0`はtask slot 4を呼ぶ。主要3クラスのslot 4
`0x1808250`は`mov rcx,rdx; jmp 0x3bf2d60`という8bytesの観測を確認した。
unwind metadataがないため、関数長を8bytesと認定したり、通常の関数グラフに混ぜたりしない。
このslot 3/4経路から主要3本体やrange runnerへの接続は、今回確定していない。

## 雇用処理の後続段階

`0x13b8540`の後続callableを追い、次の候補を追加した。

| RTTIで読めた名前 / 関係 | native対応 | 命令・構造 |
|---|---|---|
| CollectEmployment lambda | vtable `0x4590230`、slot 2 `0x13cada0–0x13cae91` | linked work-item候補をたどるループ、`0xc24140`へのcall |
| CollectEmployment continuation内のsort候補 | `0x13cae0b` / `0x13cae1a` / `0x13cae29` | count候補を`0x300`と比較し、`0x13c54c0`または`0x13c3140`をcall |
| SortEmployment lambda | vtable `0x4590268`、slot 2 `0x13cad10–0x13cad62` | range内のindexを読み、各item候補に`0x10befb0`をcall |
| sortの分割候補 | `0x13c3140–0x13c339a` | `0x200`比較、partition形の処理、2つのhelperから返るobjectにslot 2をcall |
| item処理候補 | `0x10befb0–0x10bf094` | `0x10bdb50`、`0x12a4ee0`へのcallと間接call |

RTTI名が示すlambdaの所属と、native helper自身のソース名は区別する。
2つのhelperから返るobjectを、この情報だけでworker jobと認定しない。
`0x300` / `0x200`は比較即値の観測であり、最適化のために変更する閾値としては未選定。

## OS照合で優先する位置

OS記録が得られたら、module load baseを使ってVAをRVAへ変換し、同じexe hashの
CPU sampleとstackを上記範囲へ照合する。まず共通dispatcher・range runner・heuristicと、
雇用のCollect continuation・Sort callback・item候補を分けて見る。

共通helperのsampleだけではtask名を特定できない。caller stackとbuilt-in TickTask区間の
両方を使う。CPU sampleの割合、blocked時間、critical pathは別の指標として扱う。
各thread設定1回の現状では、最適thread数・性能改善率・patch対象は決定しない。

## 再現と派生データ

```text
python -m pip install -r tools/requirements-callgraph.txt
python research/recipes/reproduce_dispatch_evidence.py <Vic3_data.zip> local-data/dispatch
```

- [dispatch-regions.json](generated/dispatch-followup-2026-10-05/dispatch-regions.json): 18選定unwind関数群、9972bytes。各範囲のhash・直接/間接call・RTTI vtable・命令抜粋と、別扱いの8bytes thunk観測。
- [scheduler-callers.json](generated/dispatch-followup-2026-10-05/scheduler-callers.json): 指定3targetの逆方向検索、4件のcallと4caller範囲。
- [artifact-index.json](generated/dispatch-followup-2026-10-05/artifact-index.json): 派生2ファイルのSHA-256。

再現recipeはexe hashを最初に照合し、選定範囲が部分decodeになる場合は停止する。
命令抜粋もunwind range先頭からのdecode結果を抽出し、途中の任意byteからdecodeし直さない。
18関数群は今回の選定範囲であり、完全なcall graphではない。
