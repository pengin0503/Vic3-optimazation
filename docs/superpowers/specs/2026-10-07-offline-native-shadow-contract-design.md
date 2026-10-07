# B0: offline native shadow 接続契約

日付: 2026-10-07  
状態: 会話で選択したB0案を書面化。書面レビュー待ち。実装計画・B0実装は未作成。

## 1. 目的と今回の到達点

段階Aの所有された合成table上のpositive-slot hintを、将来のnative shadowと接続する際の境界を、実ゲームを読まずに検証可能にする。成功条件は、native風の戻り値をslotと混同せず、比較できない条件を明示し、どの経路でも元callbackの実行・戻り値・例外を保存すること。ゲーム内の検索省略や速度改善は今回の成果に含めない。

前提資料:

- [段階A/Bの承認済み設計](2026-10-07-employment-lookup-reuse-shadow-design.md)、特に§8のnative gate。
- [段階B準備報告](../reports/2026-10-07-native-shadow-preparation-ja.md)と、そのexact-build静的成果物。
- [全ブランチ統合記録](../reports/2026-10-07-branch-integration-ja.md)。native profiler prototypeがmainに入ったことと、実ゲームで成功したことは別の条件である。

選択した方式はB0の独立したoffline contract libraryとfixture runner。Task 9の実ゲーム検証を先に行う方式はlive実行証拠を得られるが、今回の実測なしという進め方では実施しない。native shadowを直接組み込む方式は読み取り寿命とworker scopeの証拠がなく、採用しない。

## 2. 範囲と配置

新しいコードは`src/lookup_reuse_contract/`に独立したC++20 library、tests、offline runnerとして置く。既存の`src/lookup_reuse/`に依存できるが、その公開API・検証条件・結果形式を弱めない。CMakeはWindows/Linux双方で実行可能とし、Windows SDK、MinHook、DLL、loaderに依存しない。

B0で扱うのは次の四つだけである。

1. 所有されたexe bytesのexact-build locator検証と、caller witness manifest。
2. 所有されたnative風fixtureの結果値からprimary slotへの正規化。
3. 元callbackを必ず実行するoffline shadowとscope/session規則。
4. 比較・skip理由を区別する固定サイズ記録とrunner出力。

live process memory、detour、native ABIの実呼び出し、Task 9 loaderの修正、V3PF v1変更、検索省略modeは追加しない。B0が通っても段階Bの§8 gateを満たしたとは扱わない。

## 3. Locator manifestと静的証拠

manifestはexe SHA-256、`.text`境界、lookup entryと署名、対象callerのcall/return RVA、除外callerを保持する。正本は既存のnative-shadow-preparation成果物であり、同じ値を別の手書き設定に増殖させない。生成物は正本のhashとschema versionを記録する。

対象exe SHA-256は`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。lookup entryは`0xf3e040`、14-byte署名は`4c 8b 51 30 4c 8b c9 4c 63 59 3c 0f b6 c2`。対象caller witnessは以下の四つ。

| call RVA | return RVA | caller entry RVA |
|---|---|---|
| `0x13b8632` | `0x13b8637` | `0x13b8540` |
| `0x10b7db4` | `0x10b7db9` | `0x10b7c60` |
| `0x10bd565` | `0x10bd56a` | `0x10bd490` |
| `0x10bd66b` | `0x10bd670` | `0x10bd490` |

除外する確認済みcallは`0x13b847c`と`0xc6b5ca`。四つのwitnessは四回連続の同一key検索という証拠ではない。resetの全体passが処理より前にあり、一つのhintでpass間の全対象を保持できるとは扱わない。

検証器は入力を所有してからPEのraw/virtual範囲をchecked arithmeticで検証し、`.text`内の署名が一意で指定RVAにあること、対象E8 callのrel32 destinationと次命令RVAがmanifestと一致することを検査する。callerの限定署名も正本の値と一致させる。未知build、範囲外、重複署名、改変call、改変returnは拒否する。hash検証と署名検証は独立にnegative fixtureで試す。テスト専用fixtureのhashはテスト入力から求めるが、production manifestを任意hashで置き換えるCLIは作らない。

この成功はstatic witnessの一致だけを意味する。entryの命令をコピーする処理やtrampoline生成は行わず、leaf functionのrelocation、unwind、実return address取得、実ABIの正しさを認定しない。

## 4. 所有fixtureと結果値の正規化

`OwnedNativeFixture`はimmutableなslot bytes、Stage Aの`OwnedTableFixture`、合成table base/end/fallback address値を所有する。作成時だけallocationと完全検証を許す。slot bytesは40-byte stride、control `+4`、uint32 key `+8`、descriptor位置`+0x10`とする。Stage A viewを構築するbytesとfixture分類のbytesが一致することを作成時に検証する。

`OpaqueResult`は64-bitの**合成address値**であり、C++ pointerに変換もdereferenceもしない。B0のcallbackはこの値を返すhost fixture専用の型であり、実ゲームの関数pointerへのcastを許さない。将来のnative adapterは、証明した実ABIの`void*`戻り値を別の境界で取り扱う必要がある。B0のinteger callbackがそのABIの証拠になることはない。

正規化は値のsubtract/add/multiply overflow、descriptor offset、stride alignment、primary/tailの境界を検査する。primaryのslot位置が得られても、controlが0またはfull keyが異なる結果は有効なpositiveとして記憶しない。

| 分類 | 条件 | hint比較・保存 |
|---|---|---|
| PrimaryPositive | primary範囲、descriptor境界、occupied、full key一致 | 比較可能。成功slotだけ保存 |
| TailPositive | 所有fixtureのtail範囲、descriptor境界、occupied、full key一致 | skip。保存しない |
| EndSentinel | fixtureが宣言したend値に一致 | skip。保存しない |
| Fallback | fixtureが宣言したfallback値に一致 | skip。保存しない |
| InvalidPrimaryResult | primary descriptor位置だが空slotまたはkey不一致 | skip。保存しない |
| Unknown | 上記以外。0、範囲外、misaligned等を含む | skip。保存しない |

sentinel/fallback値はprimary/tail descriptor値と重複させない。不正fixtureは作成時に拒否する。これらの宣言値はfixtureの分類にだけ使い、live nativeのfallback/sentinelを入力側のassertionで認定する仕組みにはしない。UnknownをNoPositiveやFallbackにまとめない。nativeの8-bit probe wrapやsigned maskはStage Aのnon-wrapping有効tableモデルと区別し、対応できない表現はfixture作成時に拒否する。

hintはStage Aの`PositiveSlotHint::Try/Remember/Clear`を使い、保存内容はidentity・mask・full key・primary slotだけとする。候補取得で通常検索を代行しない。結果値からslotを正規化できた場合もnative address自体をhintに保存しない。

## 5. 読み取り権限と寿命

B0でviewを渡せるのは所有fixtureだけである。外部span、raw game pointer、`validated=true`、header一致、VirtualQuery成功、呼び出し側が作ったepochを使ってviewを作るAPIは置かない。既存の`ValidatedTableView`のprivate constructorを公開しない。

fixtureのborrowはfixtureが存続する同期呼び出しに限定する。fixtureごとの非公開generationとrevocation状態をfixture自身が管理し、callbackの前後で有効性を確認する。revocationは証拠喪失の模擬であり、callback中もbytesを解放しない。実際にdangling viewを読み取るテストは作らない。revocation後はhintをclearし、候補を捨て、`ProofLost`として比較をskipする。

fixtureの変更は新しいimmutable fixtureを作って行う。全bytesが同じでも新しいfixtureは同じidentityを再利用しない。epoch上限に達したら作成を拒否し、wrapしない。これはoffline ownerの規則であり、gameに同じepochがあるという主張ではない。

将来のlive read leaseには、allocation生存期間と比較窓のmutation排除をゲームの同期規則から証明する別設計が必要である。B0にlive leaseのconstructorや有効化switchを用意しない。

## 6. Shadow呼び出し、scope、session

`OfflineNativeShadow`のdefault modeはOff、追加modeはShadowだけ。APIの有効な呼び出しはnon-nullな元callbackを必須とし、mode・caller・scope・fixtureにかかわらず必ず一回だけ実行して、その`OpaqueResult`をbit単位で変更せず返す。

一つのevaluatorは一つのthreadが同期的に使用する。cross-thread共有をサポートしない。fixture runnerのworkerは別evaluatorを所有する。scopeはevaluatorに明示的に束縛するRAII objectで、別workerや別evaluatorに暗黙に継承しない。入りと終わりでhintをclearし、同じevaluatorのnested scopeは拒否する。

呼び出し順序は以下に固定する。

1. どの呼び出しでも最初に再入guardを設定する。通常の比較対象外である外側呼び出しにも設定する。
2. Shadow、session継続中、scope内、対象caller、所有fixtureの有効borrowという条件を満たす場合だけhint候補を得る。
3. 元callbackを一回実行する。
4. 通常return後にborrowと再入による失効を確認し、条件を失っていたら候補を捨てる。
5. 元結果を正規化する。PrimaryPositiveかつhint候補がある場合だけslot一致を比較する。PrimaryPositiveだが候補なしならNoCandidateとして元slotを記憶する。候補がある場合も保存できるのは検証済み元slotだけである。

再入した内側呼び出しも元callbackを一回実行し、比較をskipする。内側が正常returnでも例外でも外側hintを失効させる。外側callbackが内側例外をcatchして正常returnした場合にも外側の比較・保存を行わない。

元callbackの例外は同じ例外をそのまま伝播する。guardとhintはRAIIで復旧・clearし、その呼び出しの通常return記録は作らない。caller非対象やOffの例外でも同じ規則を守る。観測側の失敗で元callbackをretryしない。callback引数と結果の代用、元callbackのfallback pathの省略を行わない。

slot不一致ではそのsessionの比較を永久停止してhintをclearする。Off/Shadow切替や新scopeでは復活せず、新evaluatorだけが新sessionとなる。NoCandidate、結果分類skip、ProofLost、再入は不一致数に数えない。NoCandidateは古いhintをclearしてから今回の有効primary slotを記憶し、skipはclearだけを行う。skip理由が重なる場合はOff → SessionDisabled → Reentrant → MissingScope → CallerExcluded → MissingFixture → ProofLostの順で一つを記録する。再入による外側失効は`Reentrant`を使う。再入guardによる失効処理はこの理由の優先順位と独立に行う。

## 7. 記録と出力

recordはversion、caller ID、scope/session ID、key、status、skip reason、result class、candidate slot、original slot、元の合成result値を固定サイズで保持する。callの正常return時だけ更新し、内側returnの記録があっても後で完了した外側returnがlast recordを更新する。

statusはEqual、Mismatch、NoCandidate、Skipped。skip reasonは§6の条件に加えTailPositive、EndSentinel、Fallback、InvalidPrimaryResult、UnknownResultを持つ。既存Stage A enumをnative分類で膨らませず、B0固有のenumにする。

固定counterで元callback回数、比較試行、Equal/Mismatch/NoCandidate、分類別skip、再入、例外、出力dropを分ける。元callback回数はthrowした呼び出しも含む。offline collectorは固定容量で、満杯ならrecordをdropしてcounterを増やし、callback実行や戻り値に影響させない。文字列化・JSON・ファイルI/Oはrunner側だけで行う。Evaluate経路にheap allocation、I/O、mutex、table全体の検証を入れない。

出力はV3PFとは別のB0 `results.json`とverification記録。seedとfixture数、対象caller別coverage、skip理由、drop、比較数を保存し、skipが多い結果を「不一致0だからnative等価」と解釈できない説明を添える。

## 8. 受入条件

実装計画は次の独立した証拠を必須にする。

- locator: exact入力、一意署名、四caller/二除外caller、wrong hash、署名重複、範囲/rel32 overflow、call改変、return改変を検査する。exact exeの成功はoptional実データ検証とし、CIは小さい所有fixtureでも拒否経路を試す。
- normalization: primaryの最初/最後、tail、sentinel、fallback、0、misalignment、range/offset overflow、空slotの古いkey、wrong key、宣言値衝突を独立に計算した固定値で検査する。
- shadow:全mode/skip、Equal/Mismatch、scope終了、session停止、caller変更、fixture変更・address値再利用、revocationを検査する。
- original contract: normal return、throw、対象外の外側からの再入、内側throwを外側がcatchする場合、nested scope拒否、drop時にもoriginal exactly onceと結果/例外保持を検査する。
- independent oracle:期待slotはfixture作成者の配置記録、期待結果値はchecked formulaの手計算vectorを使い、正規化器自体やStage A検索を唯一の期待値生成器にしない。
- GCC/ClangのRelease・ASan/UBSan、およびMSVC x64 Releaseを検証し、既存Python tests、Stage A CTest、V3PF golden、target JSON、native CIを維持する。実行できなかった構成は成功と報告しない。

## 9. B0終了後も残るgate

B0終了後の報告は「所有fixtureの接続契約が検証できた」に限定する。live read window、worker/job scopeの伝播、実pointer結果の分類、native ABIとleaf hook relocation/unwind、actual return-address allowlist、Task 9 attach/stop/pairing/observer overheadは別々に証拠を要する。loader code 4の診断を含む既存の未解決事項を、B0で解決した扱いにしない。

次の作業はこの書面のレビュー後の実装計画作成である。計画のレビューと実行方式選択後にB0を実装し、live native shadowの接続判断はさらに§8のnative gateを満たしてから行う。
