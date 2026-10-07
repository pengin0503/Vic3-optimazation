# 段階B native shadow — 準備報告と開始条件

日付: 2026-10-07（日本時間）  
調査基準main: `66ac704e46c1028655b2577aaa6f14479b4fce1b`  
対象: Victoria 3 Windows 1.14.5  
状態: **準備調査済み。native shadowの実装・有効化条件は未達。** 本書は既存spec §8への証拠addendumであり、新しいnative実装計画や寿命証明ではない。

## 1. 結論と今回の成果

段階Aの成果を確認し、段階Bに使う静的target資料、ABIのregister witness、開始条件、runtime統合前の確認事項を用意した。追加のゲーム内測定・live memory読み取り・hook・loader修正は行っていない。

静的資料だけでも、入口の一意署名、4つの候補callsiteの一意署名とreturn RVA、map/key/returnのregister経路、候補外caller、fallbackの副作用まで具体化できた。一方、game tableの借用期間、不変条件、worker scope、実ゲームのprofiler動作と費用は未証明である。**段階Aの0 mismatchとCI成功から、これらを補うことはできない。**

次に進める範囲としては、実ゲームに接続せず、target manifest・opaque戻り値の扱い・証拠不足時の拒否・scope/telemetryを所有fixture上で検証する「B0: offline接続契約の準備」を推奨する。これは提案であり、実装承認済みの新計画ではない。実ゲームのBへ進む前に、下記の開始条件を満たす証拠と接続設計・計画のレビューが必要。

## 2. 段階AとCIの確認

mainの `src/lookup_reuse/`、header/core、合成結果、検証記録を確認した。GitHub Actions APIで同じcommitの以下3 jobのsuccessを確認した。ローカルで29 testsを再実行したという報告ではない。

| Workflow / run | Job | 確認結果 |
|---|---|---|
| [tests / 37549511496](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37549511496) | python | success |
| [lookup-reuse-core / 37549511550](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37549511550) | ubuntu-24.04 core | success |
| 同上 | windows-2022 core | success |

[段階A結果](../../../research/generated/lookup-reuse-core/results.json): 2,004 snapshot、32,948 query、core hit 5,355、reference call 27,593、membership/slot/shadow mismatch 0。これらは合成検索の回数であり、ゲームのhit率や所要時間へ換算しない。

## 3. native runtimeの所在と統合前提

**基準mainには `src/native/` がない。runtimeソースは別ブランチに存在する。** 「runtimeが未実装」と「mainへ未統合」は区別する。

| 項目 | 確認内容 |
|---|---|
| runtime branch | `claude/vic3-native-profiler-tasks-suugii` |
| 参照commit | `271d5ea0a2a46557ed1ef21ac89df42c3d464d51` |
| mainとの関係 | diverged。基準mainから見てruntime側ahead=14 / behind=8 |
| 共通祖先 | `7f2c5772de280481811562ecb6c4085f4e451a0c` |
| branch CI | [37398991761](https://github.com/pengin0503/Vic3-optimazation/actions/runs/37398991761): python/nativeともsuccess |
| 実装範囲 | 3つのTickTask tail観測、loader、DLL lifecycle、固定buffer、MinHook backend、V3PF v1 |
| 実ゲーム | branchのhandoffは未検証。loader診断資料はdisabled attachのcode 4を未解決としている |

参照資料はbranchの[実装handoff](https://github.com/pengin0503/Vic3-optimazation/blob/271d5ea0a2a46557ed1ef21ac89df42c3d464d51/docs/superpowers/reports/2026-10-05-native-profiler-runtime-implementation-handoff-ja.md)、[loader診断](https://github.com/pengin0503/Vic3-optimazation/blob/271d5ea0a2a46557ed1ef21ac89df42c3d464d51/docs/superpowers/reports/2026-10-06-loader-module-resolution-diagnostics-ja.md)、[Windows実ゲーム手順](https://github.com/pengin0503/Vic3-optimazation/blob/271d5ea0a2a46557ed1ef21ac89df42c3d464d51/docs/superpowers/guides/2026-10-05-native-profiler-runtime-validation-ja.md)。診断追加やhelper hostの成功を、ゲームattachの修正・成功と扱わない。

両branchが分岐済みなので、そのままmainへfast-forwardはできない。統合作業では最新mainから隔離branchを作り、runtime側の変更を順に取り込み、衝突を解決した結果を検証してからmainをfast-forwardさせる。既存runtime branchをforce更新する必要はない。今回の準備では統合・cherry-pick・loader修正を実行していない。

統合時のreview対象:

| 衝突・依存 | 受け入れ条件 |
|---|---|
| README / `src/README.md` | 段階Aの実装済み記述、nativeの実ゲーム未検証記述、各handoffを保持 |
| `.github/workflows/tests.yml` | Python jobを維持しnative検証も実行。独立したlookup-reuse-core workflowを保持 |
| benchmark quality code/tests | runtimeのworkload fingerprint追加と最新mainの挙動を両立。古いfile全体で上書きしない |
| `.gitattributes` / `.gitignore` | generated target includeのLF、LFS入力方針、build出力除外を保持 |
| target codegen / native依存 | pinned MinHook、Windows x64 CMake、generated include再現性を確認 |
| runtime validation | Windows CTest、V3PF golden/parser互換性、disabled→ready→stop、実ゲームログ・費用を別々に確認 |

loader failureは既存Task 9の独立したblocker。原因を示す新しいstageログが得られなければ「解決済み」と更新しない。段階Bへ紛れ込ませて別方式のinjectや判定緩和を行わない。

## 4. 添付exeから再確認した静的証拠

入力archive SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`  
exe SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

[静的証拠JSON](../../../research/generated/native-shadow-preparation-2026-10-07/static-evidence.json)には、bounded命令列、caller metadata、署名、相対call edgeを保存した。最新mainのstdlib PE/unwind helpersとGNU objdumpを使用した。6つのcallerではRUNTIME_FUNCTION groupからdecodeして、callのinstruction boundaryも確認した。

| 観測 | 確認結果 / 限界 |
|---|---|
| lookup excerpt | `0xf3e040–0xf3e0fd`、189 bytes、SHA-256 `ed016a30cfa6f312cf61a2982587951e0e0227b2bf69b49c05c1c16ae0f5c1ad`。unwind metadataなし |
| entry signature | `4c 8b 51 30 4c 8b c9 4c 63 59 3c 0f b6 c2`、14 bytes、`.text`内match=1 |
| fallback excerpt | `0xf468d0–0xf469aa`、218 bytes、SHA-256 `54bde9d62b7d4ec9e064d1a733904136b8f1d63a493de9c8a0ac7bf965aace9f`、metadataあり |
| 最初のinstruction lengths | 4 / 3 / 4 / 3 bytes。5-byte patchを覆う最小whole-instruction span=7、14-byteなら14 |
| candidate caller signatures | 下表の4site全てinstruction-aligned、match=1 |
| 候補外caller | `0x13b847c`と`0xc6b5ca`もdecode済みのE8 callで同じhelperを呼ぶ |
| `.text`のraw E8 scan | 181候補。残る175箇所はboundary未確認。181を確定caller数や実行回数と呼ばない |

署名はexact hashに対する補助検証だけ。runtimeのmodule/.text検証、control-flow、callsite、relocationが通るまでarmしない。上記patch spanは命令境界の算術であり、MinHookの成功・thread安全性・unwindingの試験結果ではない。

## 5. 候補4siteのmanifest材料

| call RVA | return RVA | caller group root | key入力 | signature length / matches |
|---|---|---|---|---|
| `0x13b8632` | `0x13b8637` | `0x13b8540` | `EDX ← [R15+8]` | 12 / 1 |
| `0x10b7db4` | `0x10b7db9` | `0x10b7c60` | `EDX ← [RBX+8]` | 14 / 1 |
| `0x10bd565` | `0x10bd56a` | `0x10bd490` | `EDX ← [R13+8]` | 12 / 1 |
| `0x10bd66b` | `0x10bd670` | `0x10bd490` | `EDX ← [R13+8]` | 12 / 1 |

全4siteのRCXはGameState global → +0x608 → +0x120 → +0x2f40のmap経路を持つ。戻ったRAXはdescriptor pointerとして使用され、`[RAX]`とsigned DWORD `[RAX+0xC]`を読む経路がある。全descriptor fieldの型は未復元。

return RVAは研究用のmodule-relative値。将来のdetourではcaller return addressをdetour入口で取得し、moduleの範囲・署名・call edgeの検証結果と照合する。helper関数の中で取得したreturn addressを、元callerの値と誤認しない。旧絶対addressやRVAだけをallowlist成立の根拠にしない。

4siteは4回連続の同key検索を意味しない。`0x13b8632`は全件resetのpass、他3siteは後続の処理側にある。1-hintではreset pass全件を跨いだ全itemの結果を保持できない。まず後続item処理内のnested検索と2siteの関係・間に挟まるlookup/mutation・worker所属を確認する。resetと後続passを融合する案やscopeをtick全体へ広げる案は採らない。

## 6. 内部ABIとnative表現の差

Windows x64 ABIのRCX/RDX引数・RAX scalar returnという[Microsoft一次資料](https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention?view=msvc-170)と、上記caller/calleeの命令から、調査用prototypeは `opaque_descriptor_pointer Lookup(void* map, uint32_t key)` が支持される。これはsource-level宣言の復元でもhook実装の承認でもない。TickTaskの `void(void*, void*)` を流用しない。

観測したlookup経路:

- entryでmapの+0x30をtable base、+0x3Cをsigned int32 maskとして読む。
- 4-byte keyのFNV-1aを計算し、signed-extended hashとmaskをANDする。
- 40-byte slotのcontrol +4とfull key +8を読む。probeはwrapせず次slotへ進み、CLを8-bit incrementする。明示的なprobe overflow guardはこのexcerptにない。
- normal positiveではslot+0x10をpointer候補とする。map+0x40の1-byte値とmaskから計算した終端slotに一致すれば候補をnullへ変え、fallbackへtail-jumpする。
- fallbackはTLS/static initialization guard、global更新、callee呼び出しを持つ。旧miss結果をcacheせず、元関数を必ず実行する。

map+0x40の値は命令上の終端計算材料として確認できたが、field名・allocation全長・tail/padding/sentinelの完全仕様は未証明。coreのmask=uint64、bounded span、probe距離制限、末尾empty条件をそのままgameへ当てはめない。metadata不在だけでleafのhookを安全と断定しない。[Microsoftのx64 unwind資料](https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64)に基づき、実際に生成するdetour/trampolineとfallback tail経路のunwindingを別途確認する。

## 7. 段階Aから接続するときの境界

`ValidatedTableView`はprivateなOwnedTableFixtureへの借用であり、外部memory用constructorを持たない。Createはheapを使用して全slotを検証しowned copyを作る。この入口をgame hot pathで呼ぶ案は不適切。live spanを `valid=true` で認定する抜け道も作らない。

段階B接続設計で決める事項:

1. **結果型を分離する。** native originalのopaque pointerをexactly once得て、そのbit patternをそのまま返す。段階Aのoptional slot callbackへfunction pointerをcastして呼ばない。
2. **locationへの対応は証拠条件付き。** 現table領域と寿命が保証された時だけ、元pointerが `table_base + 40*index + 0x10` のprimary slotに一意に対応するか、checked算術で判定する。以前のdescriptor pointerをdereferenceしない。
3. **不明をNoPositiveResultに潰さない。** 未認定layout/寿命/返却領域はSkippedとして分類する。fallback/tail/sentinelの証明無しに `fallback_or_no_positive` へ数えない。native-only skip理由は段階A enumを無断で拡張せず、別契約に置く。
4. **viewを作れる主体を限定する。** 将来のnative adapterはゲーム側の所有・同期規則を示した後に借用を発行する。game epochの存在を仮定せず、header hash、VirtualQuery readable、呼び出し前後のheader一致を寿命証明にしない。
5. **scopeをworkerへ置く。** TickTask tailのTLSはqueued jobへ自動継承されない。native branchのTickTaskHooksも現状はBegin/Endを記録するだけ。`0x13b8540` / `0x10bd490` / nested `0x10b7c60` の実際のjob/item寿命を確認する。

現viewがvalidatedで不変という前提が満たせない限り、hintのkey/control再確認だけでlive memory安全性を補えない。追加のgame lock、例外を隠すSEH、table全体copyで解決済みにしない。

## 8. spec §8に対するgate表

| Gate | 今回進めた証拠 | 残る必須確認 / 現在の判定 |
|---|---|---|
| target locator | exact exe/archive hash、entryと4callsiteの一意署名、E8 edge、fallback path | runtime module/.text照合と拒否試験。静的材料あり、native未合格 |
| 内部ABI | RCX map / EDX full key / RAX pointer、6callerのdecode、normal/tail witness | hidden契約・例外/unwind・全関連tail pathと実prototypeのhost試験。部分証拠のみ |
| hook入口 | metadata不在を再確認、7/14-byte whole-instruction span | 実backend relocation、incoming edge、tail-jump、例外のWindows fixture検証。未達 |
| caller scope | 4site manifest材料、候補外2callerの確認 | 外caller/reentrantの元関数維持、入口caller捕捉、雇用scopeの実検証。未達 |
| 時間範囲 | resetと後続passを分離、worker/item候補を特定 | job作成・実行・完了、thread/再入/stopのscope寿命。未達 |
| table不変条件 | +0x30/+0x3C/+0x40とpositive/終端式を記録 | 全mutation/rehash/delete/destroy/address再利用、tail/control容量。未達 |
| 読み取り寿命 | owned offline APIとnative borrowed APIの差を特定 | ゲーム側の所有・同期根拠で追加読み取り全期間を保証。最重要blocker、未達 |
| profiler前提 | runtime branch、CI、既存停止・bufferの設計を確認 | main統合の検証、attach失敗解決、実ゲームtrace/stop/費用。未達 |
| 費用・一致 | 合成countsとnative countsを分離、共有helperを確認 | Off/Shadowの同一workload比較、対象率、skip/drop、不一致時停止。未達 |

静的部分が進んでも、全gateが通るまでnative shadowの有効化条件を満たしたとしない。

## 9. 次の作業順と受け入れ条件

**今すぐ追加測定なしで進められる候補:** B0の接続契約設計、owned fixtureによるopaque pointer→slotの判定、未知layout/寿命・外caller・再入・buffer不足・mismatch/session停止の拒否テスト、独立sidecar契約。live-readを有効にするAPIやdetourはこのoffline準備へ含めない。

**別系統で必要:** 既存Task 9 runtimeのmain統合レビューとWindows検証。成功したhelper host/CIに加え、実ゲームのdisabled attach・3 tail hooks・trace/stop・CSV境界とobserver overheadが必要。既存の診断手順を利用し、段階Bのhelperを新しくhookする前にruntimeの基準を確定する。

**native接続前の研究:** map +0x2F40の所有者・constructor/destructor・全構造mutation、callback jobへの引数受け渡し、並行実行と同期を追跡する。key/control/slotが安定する根拠と、borrowの開始・終了を明記する。sample、header一致、0 mismatchはこの規則の代わりにしない。根拠が得られなければnative追加読み取りは開始しない。

**将来のWindows fixture:** exact locator拒否、opaque ABI、元callback1回/引数/戻り値/例外、relocationとfallback tail、caller allowlist、scope、再入、途中のproof失効、pool不足、stop中active callを試験する。fake hostのPASSはgame安全性のPASSと区別する。

**将来のgame run:** 新しいB専用設計・計画のレビューとgate成立後、同save・同tick終端・同設定でOff/Shadowを交互に反復する。run ID、game/save/build hash、workload fingerprint、wall time、V3PF/sidecar hash、observed/allowlisted/candidate/compared/skip/drop数を保存する。既存3 target IDやV3PF v1 layoutは変更せずsidecarへ出す。

helperは共有されているため、4site以外で候補をbypassしてもglobal detour自体の費用は発生する。候補外の呼び出しも費用評価へ含め、合成hit率から改善率を見積もらない。

## 10. 選択肢と推奨

| 進め方 | 得られるもの | 必要条件 / 判断 |
|---|---|---|
| **B0: offline接続契約を先に設計** | target/ABI材料の利用、opaque結果保持、拒否・scope・sidecarのfixture検証 | 追加ゲーム測定を待たず進められる。推奨。設計と計画のレビューが次の段階 |
| Task 9統合・実ゲーム基準を先に完成 | 再利用するruntimeと費用の基準 | Windows作業とloader stageログが必要。B0と独立して進められる |
| full native shadowへ直行 | 実table上の比較 | 寿命・table・scope・runtime gate未達のため現在は選択不可 |

まずB0を設計対象にし、runtime問題とlive寿命証明を独立した開始条件として残す。runtimeの既存実装を再作成せず、段階Aのownership契約も緩めない。

## 11. 再現手順と保存物

研究用recipeは [collect-static-evidence.py.txt](../../../research/generated/native-shadow-preparation-2026-10-07/collect-static-evidence.py.txt)。repoの `tools/` helpersをimportし、入力zipを読み取るだけ。GNU objdumpが必要。repo外の一時ディレクトリへrecipeをcopyして実行する:

```bash
cp research/generated/native-shadow-preparation-2026-10-07/collect-static-evidence.py.txt /tmp/vic3-stage-b-static-evidence.py
PYTHONPATH=tools python /tmp/vic3-stage-b-static-evidence.py input-data/Vic3_data.zip /tmp/vic3-stage-b-static-evidence.json
cmp /tmp/vic3-stage-b-static-evidence.json research/generated/native-shadow-preparation-2026-10-07/static-evidence.json
```

zip pathは実際の添付/checkout先へ置き換える。LFS pointerのままならexe入力として扱わず、実体を取得してから実行する。

今回、添付zipから1回目を抽出し、最新mainのhelpersを改めて取得して2回目を抽出した。双方はbyte一致。入口と6callerの署名は全て `.text`内match=1、4つだけが将来の候補allowlist、6つ全てE8 edgeを独立計算して一致。lookup metadataなし、fallback 218 bytesを確認した。

- [static-evidence.json](../../../research/generated/native-shadow-preparation-2026-10-07/static-evidence.json): bounded命令・署名・edge、raw scanと限界。
- [repository-state.json](../../../research/generated/native-shadow-preparation-2026-10-07/repository-state.json): 基準commit、branch分岐、main/branch CIの観測。branch差分数は記録した基準mainに対する値。
- [artifact-index.json](../../../research/generated/native-shadow-preparation-2026-10-07/artifact-index.json): report/recipe/JSONのhashとサイズ。

本準備で製品コード・既存native target JSON・V3PF v1・段階Aの結果/検証記録は変更しない。実装計画を作った、native gateを満たした、ゲームが速くなったという報告ではない。
