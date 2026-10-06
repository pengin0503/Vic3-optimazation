# 雇用配列検索の再利用coreとshadow比較 — 設計書

日付: 2026-10-07（日本時間）  
リポジトリ: `pengin0503/Vic3-optimazation`  
作成基準main: `da2bbc1158c5a17eb5ed8faafb04890bee8bd5e5`  
状態: **書面specはユーザー承認済み（2026-10-06 UTC、この会話）。** [段階Aの実装計画](../plans/2026-10-06-offline-lookup-reuse-core.md)を作成し、計画レビュー待ち。製品コードは未作成。

## 1. 目的と成功条件

追加のゲーム内測定を待たず、文化・宗教・国数・経済ルール・更新頻度・処理順序を維持する軽量化候補を具体化する。第一候補は、同じitemに対するID配列検索の成功slotを検証して再利用し、hash計算とprobeを繰り返す仕事を減らす方式。

まずnativeから独立したC++20 coreを作り、所有された不変の合成table上で通常検索と一致することを検証する。実ゲームへ進む段階では、元関数の戻り値を変えないshadow比較を先行する。**本specはゲームの検索呼び出しを省略する性能patchを許可しない。** 性能patchの有効化は、shadow・寿命条件・観測費用・実測効果を確認した後の別設計とする。

成功の区分:

| 段階 | 成功条件 | 成功しても主張できないこと |
|---|---|---|
| A: offline core | 明示した不変条件下で通常検索と同じslotを返し、不明・不正な入力ではhitを返さない | native containerの等価性、実ゲームの高速化 |
| B: native shadow | 対象・ABI・読み取り寿命が検証済みの範囲で元関数を1回呼び、比較結果を記録する | 元関数の呼び出し省略の安全性、長期決定性 |
| C: 性能patch | 本specの対象外。別設計・計画・実ゲーム検証を要する | A/Bの成功だけでは着手しない |

今回の書面レビュー後に作る実装計画は**段階Aだけ**を実装対象とする。段階Bは条件付きの接続契約であり、未検証条件を仮定して実装・稼働させない。

## 2. 根拠と証拠の限界

一次入力:

- Victoria 3 Windows 1.14.5、exe SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- 添付archive SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`、124,462,636 bytes
- [調査報告](../reports/2026-10-07-offline-employment-optimization-ja.md)
- [限定された命令証拠](../../../research/generated/employment-reuse-2026-10-07/evidence.json)
- [捨てる前提の合成モデルsource](../../../research/generated/employment-reuse-2026-10-07/model-source.py.txt)、[test source](../../../research/generated/employment-reuse-2026-10-07/model-tests.py.txt)
- [合成結果](../../../research/generated/employment-reuse-2026-10-07/synthetic-results.json): 9テスト、1,000 rebuild、25,676比較、不一致0

静的siteは `0x13b8632`、`0x10b7db4`、`0x10bd565`、`0x10bd66b`。4箇所とも `0xf3e040` を呼び、同じitem-originの+8をkeyとする経路を持つ。全siteが毎回実行されること、同じdescriptorが返ること、runtime hit率は未証明。

`0xf3e040–0xf3e0fd` はmetadata不在の189-byte限定excerpt。4-byte keyのFNV型hash、40-byte slot、control byte +4、full key +8、descriptor +0x10を観測した。全containerの仕様・sentinel・paddingを復元したことにはしない。

失敗側のtail-jump先 `0xf468d0–0xf469aa` は初期化guardとglobal書き込みを持つ。miss結果のcacheや初期化の代行を禁止する。

全件reset後に前処理・条件付き処理を行う順序を維持する。2つのresolver `0x85d7c0`、`0xc46bc0` のdatabase globalは共に `0x5a39c18`、fallback globalは共に `0x5a37980` だが、object pointerの寿命・全例外経路まで等価と扱わない。

## 3. 採用案と代替

**採用: 成功slotをhintとして保存し、現在のtableから検証したlocationを返す。** 生object pointer、配列内容、以前のdescriptor pointerは保持しない。1つのhintだけで出発し、連想cache・pool・複数bucketへ広げない。

代替のdescriptor引数渡しはcallee間のmutationと内部関数再構築の証明範囲が広いので今回は採用しない。ループ融合は全件resetの順序条件を変えるため採用しない。一時buffer持続化は移動・破棄・nested allocationの所有権を変え得るため別課題とする。

安定した同じ成功keyを4回検索する合成例では通常検索を1回へ減らせた。これは検索回数の削減であり、速度の改善率ではない。実ゲームではvalidation、TLS、hookの費用が削減分を上回る可能性がある。

## 4. コンポーネントと配置

提案する製品コードの配置は `src/lookup_reuse/`。既存 `src/native/` のWindows専用profiler scaffoldから独立させ、段階AはMSVC/GCCでbuildできるplatform-neutral static libraryとする。外部依存・ダウンロード・game SDKを不要にする。

| コンポーネント | 責務 | 入力・出力 |
|---|---|---|
| OwnedTableFixture / ValidatedTableView | offlineの所有された不変bytesとその構造検証 | bounded bytesとidentity → valid view / typed error |
| ReferencePositiveSearch | offline表現上の通常の正の検索 | valid view、uint32 key → slot / NoPositiveResult |
| PositiveSlotHint | 前回成功locationを現在のviewで検証 | valid view、key → Hit / NeedsOriginal |
| OfflineShadowEvaluator | 元検索を必ず実行する比較のfixture | reference callback、hint → 同じ元結果と比較記録 |
| Native adapter（段階B、未実装） | 検証済みgame読み取り領域をcoreへ接続 | 実ゲームtarget、寿命証拠、ABI → 比較のみ |

coreはWin32 API、live process memory、MinHook、profiler codecを知らない。portable CMakeではnative loader/DLLをbuildしない。

想定ファイルは、`CMakeLists.txt`、`include/TableView.h`、`include/PositiveSlotHint.h`、`include/ShadowComparison.h`、対応する `core/*.cpp`、`tests/*.cpp`。正式なタスク順・commit単位・実行commandは書面承認後の計画で定める。

## 5. offlineデータ契約

### 5.1 Viewとidentity
`ValidatedTableView` はbounded immutable bytesを借用する。所有fixtureがview使用中にbytesを変更・解放しない。bytesはprivateに所有し、immutable snapshotからのみviewを発行する。可変な外部spanへのbool certificateを認めず、所有者の破棄・move後のview使用も禁止する。identityには `map_id`、`storage_id`、`lifetime_epoch`、`layout_version` を含む。epochはfixture所有者が変更・再配置・再生成で更新する。coreはepochを勝手に推定しない。

このepochは**gameに存在すると仮定したfieldではない**。段階Bには別の寿命証明が必要であり、header hashやVirtualQueryのreadable判定だけでepochを代用しない。

offline slotはalignmentやC++ struct paddingに依存せずlittle-endianとして40-byte recordを明示的に読み、controlを+4、uint32 keyを+8に置く。descriptorの内容は参照せず、出力はslot indexで表す。これは正の検索に必要な限定表現で、nativeの全fallback/sentinelを再実装する形式ではない。

### 5.2 Validatedの意味
単にcallerが `valid=true` と渡せるAPIにしない。fixture validatorが以下を検証してからviewを発行する。

- layout_version=1、maskは非負の2^n-1、slot spanとprimary範囲が一致する。
- index/stride/size計算がoverflowせず、必要なbytesが全てspan内にある。
- keyはfull uint32として一意。低24 bitだけで同一視しない。
- 空slotと正のprobe distanceに整合するcontrol表現を持つ。
- 各occupied keyが通常検索の停止条件より前に到達可能で、control distanceに整合する。
- control byteが表せないprobe distance、truncated tail、重複key、到達不能keyはinvalidとする。

検証はoffline fixture構築時に行う。全slotの検証をgame hot pathへ移さない。native adapterがこの契約を満たす根拠は別途確認する。

### 5.3 ReferencePositiveSearch
4-byte little-endian keyに32-bit wraparoundを明示したFNV型計算を使う。正のprobeはhash&maskから始め、keyとcontrolを検証する。無制限走査を行わず、span端・controlの表現限界・停止条件で打ち切る。

成功はslot indexを返す。見つからない場合は `NoPositiveResult`。gameのfallback関数、global初期化、empty-array addressを実装しない。合成referenceはnativeの完全なemulatorとは呼ばない。

## 6. Hint契約

hintが保持するのはidentity、mask、full key、primary slot indexのみ。descriptor/objectの旧addressをdereferenceするAPIを持たせない。

hitは次の条件を全て満たす場合のみ:
1. 現viewがvalidatedかつ使用中不変である。
2. map/storage/epoch/layout/mask/full keyが一致する。
3. 保存indexが現在のprimary範囲内で、現在のspanから安全に読むことができる。
4. 現在のslot controlが正で、現在のfull keyが一致する。

不成立は `NeedsOriginal`。元の検索はcallerが行う。成功した元検索のslotがvalidated view内のprimary範囲へ一意に対応するときだけhintを更新する。miss、tail/padding/sentinel、invalid view、scope終了ではhintを消す。失敗結果を記憶しない。比較・診断へ出すidentityはそのrun内のopaque tokenとし、実addressを恒久IDとして保存しない。

identityの一致だけで、変更可能なtableに対する等価性を保証しない。validatedなimmutable viewという前提が必須である。合成モデルでsame-storage再配置を再検証できたことは、live pointer寿命の証拠ではない。

## 7. Shadowの比較契約

### 7.1 offline
hintから候補slotを得ても、reference callbackを必ず1回呼ぶ。正常に返ればその元結果をそのままcallerへ返す。候補を元結果へ代入しない。元callbackが例外を投げたら変換・抑制せず伝播し、RAIIでscope状態だけを片付ける。

比較status:
- `NoCandidate`: hint missまたは未適格。mismatchとして数えない。
- `Equal`: 同じimmutable view上で候補と元結果のslotが一致。
- `Mismatch`: 比較可能な同じviewで不一致。hintを消し、そのobserver sessionの候補計算を停止。
- `Skipped`: view/scope/lifetimeの証拠不足。candidate hit率の分母と分離。

比較用のrecordはfixed-size値とcounterのみ。text整形やJSON出力はrunner側で行う。

### 7.2 native（条件付き）
live tableに安全にアクセスできることが確認されない限り、追加読み取り・hint計算を行わない。以前のslot pointerを読む前に現在の所有領域・scope・寿命を確立する。原関数が読み取れることだけからobserverの延長された読み取り期間まで安全と推定しない。

入力snapshotを取る場合も、取得全期間の安定性と所有権を証明する。元関数の前後でheaderが同じだったという観測だけでは競合・ABAを除外しない。比較途中に証拠を失ったら `Skipped` とし、事後にcandidateを作ってhit実績へ数えない。

shadowは元関数をexact original trampolineで1回呼び、正常戻り値・引数・失敗経路・初期化・例外を維持する。元関数を省略するmodeは設けない。reentrancyの内側は候補計算をbypassし、外側hintもinvalidにする。再帰状態を無制限に蓄積しない。

## 8. Native接続の開始条件

現在の資料は下表の条件を満たしていない。条件が未達なら段階Aの完了を報告できても、game向けshadowを有効化できない。native接続を実装する前に、証拠addendumとその実装計画をレビューする。

| 条件 | 必要な証拠 / 未達時 |
|---|---|
| 対象locator | 支持exe hash、.text内のunique signature、相対callsite・control-flowの照合。研究RVAだけではarmしない |
| 内部ABI | map/key/returnの実呼び出し契約、全関連normal/tail path、callsite。既存TickTaskのvoid(two-pointer) ABIを流用しない |
| hook入口 | metadata不在leafのrelocation・stolen instruction・external tail-jumpを検証。189-byte excerptだけでcomplete functionと認定しない |
| caller scope | 検証済み4siteのallowlistと雇用callback内での適用範囲。別callerは元関数のみ |
| 時間範囲 | worker callbackの実行寿命を確認。既存TickTask tailのTLS scopeがqueued jobへ自動継承されると仮定しない |
| table不変条件 | primary/tail/control/sentinelとmutation・破棄・再配置、address再利用を説明できる |
| 読み取り寿命 | native viewの借用期間をgame側の同期・所有規則で保証。証拠不足ではlive読み取りを行わない |
| profiler前提 | Task 9のloader/DLL検証、停止動作、trace互換性、実ゲームの観測費用が確認済み |
| 費用と一致 | compare可能な対象をrun別に数え、欠測・skip・dropを保存する。不一致0でもsampling外の等価性を主張しない |

supported buildでもどれか未達ならshadowはOff。失敗処理をSEHで隠して追加読み取りを続けたり、新しいlockでgameを止めたりしない。

## 9. 既存profilerとの関係と診断

[Task 9 runtime計画](../plans/2026-10-05-read-only-native-profiler-runtime.md)は、3つのTickTask tailのみを観測する既存計画として維持する。今回のcoreをそのTask 6のdeeper hookとして紛れ込ませない。loaderの既知エラー修正も別作業である。

[V3PF v1契約](../../../research/native-profiler-event-format.md)のheader/event layout、target ID、既存goldenを変更しない。段階Aはstandalone JSON結果を出す。段階Bの診断は既存traceと関連づけるsidecarにし、run ID・build hash・observer build IDを保存する。

必要なcountsは `observed_calls`、`candidate_attempts`、`candidate_hits`、`equal`、`mismatch`、`skipped_by_reason`、`fallback_or_no_positive`、`reentrant_bypass`、`dropped_records`。candidate hit数と同じviewでの比較完了数を分ける。dropがあるrunを完全比較済みとして扱わない。

native hot pathは既存profilerと同じくheap allocation・file I/O・formatting・mutexを行わない。1-thread/1-hintのfixed storageを使い、registrationやbuffer不足では元関数のみへ戻る。slow-path sidecar書き込みはprofiler-owned threadが行う。

初期modeは `Off`。将来の `Shadow` だけを定義し、`Enabled/Optimize` はこのspecに作らない。不一致時はobserver eligibilityを停止し、gameを走行中のhookから直ちにunloadしない。停止・flush・hook整理は既存lifecycleのcontrol threadで行う。

## 10. 検証と受け入れ

段階Aはtest-firstで、既存Pythonモデルをexpected generatorとして使わない。hand-derived slot配置、独立key/value集合、通常検索とのdifferential比較を併用する。

必須ケース:
- 成功位置の同一性と、repeat hitでreference searchを省略できるcore単体の挙動
- shadowではhit時も元callback1回、元結果の維持、例外の伝播
- map/storage/epoch/mask/layout変更、clear、scope終了、再配置・再生成
- full keyが異なる場合、衝突とbackshift、同じslotを別keyが再利用する場合
- control overflow、到達不能key、重複key、truncated span、size/offset overflow
- primary範囲外・tail・sentinel・missをcacheしない
- comparator mismatchで候補停止、Skipped/NoCandidateをmismatchへ混ぜない
- reentrant callbackをbypassし、外側hintを無効化する
- 全valid fixtureでreference結果とkey/value集合の存在判定が一致する
- fixed seedと、そのseedとは別のboundary fixturesで再現可能な比較

releaseのportable core testsと、既存 `python -m unittest discover -s tests -v` を実装計画の完了時に実行する。test commandと実行環境・skipを報告する。fake game hostの成功を実ゲームでのABI・memory safetyの成功と呼ばない。

段階Bでは、同じsave・同tick終端・同設定でOff/Shadowを交互に反復し、TickTask workload boundary、wall time、trace/sidecar、drop、比較coverageを保存する。観測負荷がbenchmarkで識別できるnoiseを上回るなら、速度の証拠に使わず、観測頻度・範囲を別途設計し直す。0 mismatchは観測した範囲の結果であり、完全な等価性やmultiplayer OOSの保証ではない。

## 11. 非対象と完了境界

このspecと段階A計画では、DLL注入、game helperのdetour、game-state書き込み、scheduler/lock/cadence変更、Employment pass融合、allocation置換、保存済み測定の再収集は実装しない。

**段階Aの完了はportable core・test・再現可能なfixtureと結果まで。** native adapterの証拠条件が未達でも、仮定で穴埋めせずその状態をhandoffに残す。正式な性能patchの設計へ進むには、比較coverage、寿命不変条件、観測費用と原因別runtime evidenceを必要とする。

## 12. レビュー対象

この書面で確認する判断は、(1)成功slot hintへ限定すること、(2)portable coreを先に実装すること、(3)native shadowを明示した証拠条件付きにすること、(4)性能patchは別設計にすること。

書面spec承認後、Superpowers writing-plansで段階Aの実装計画を作成する。実装計画のレビューと実行方法の選択後に実装を開始する。現在の承認を、まだ存在しない計画やnative target addendumの承認として扱わない。
