# scheduler近傍の同期を分類した追加証拠

2026-10-05、Windows 1.14.5。exe SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。入力archive SHA-256 `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`。全てread-onlyの限定静的解析。

## 結果

既存のdispatcher caller `0x7e1820/0x7e20c0`、range runner `0x7dbaa0`、heuristic `0x7db150` を起点に、直接call/tail-jump、code-address参照、参照vtableのslot候補を含む混合候補graphを深さ3・200群まで追った。address/vtable候補は実際の呼出しを示さない。その近傍で見つかった同期を、Task完了待ちやGameStateロックと一括認定することはできない。具体的には、初期化ガードと整合する経路と、tick統計の整形・更新につながる経路を分けられた。下表の4本のpathはgraph全体と別に直接call命令で確認した。

| 分類候補 | exact-buildの証拠 | 未確認事項 |
|---|---|---|
| 静的初期化ガード | `0x7db150` と `0x7e20c0` は `GS:[0x58]` からTLSを読み、global guardとの比較で `0x4234408` を呼ぶ。後者はSRW取得、guard値0/-1、condition variable待ち、TLS epoch更新。`0x423439c` はglobal epoch更新、解放、WakeAll | source symbolがMSVC `_Init_thread_header/footer` と一致するか、計測区間内に到達するか、blocked duration |
| tick統計更新 | `0x7e20c0 → 0x7e1910 → 0x7e56b0/0x7e5950`。中間に `Tick - Average Sum Time`、`%s - Average tick time`、`%s - Average sum time` の参照。末端はSRWを挟み、整形済みlocalを `0x764150` へ渡す | timing設定別の到達性、ロック競合、collector自体の費用、Session critical pathへの寄与 |

ガード側の呼出し位置は `0x7db992` と `0x7e2cdd`、completion側は `0x7db9d8` など。統計側は `0x7e2bc3 → 0x7e1eb8/0x7e1fce`。統計更新側のAcquire/Release位置は `0x7e588d/0x7e58a8` と `0x7e5b2b/0x7e5b46`。記録JSONに範囲hash、命令bytes、直接call witness、文字列RVAを保存した。

[Microsoftのthread-safe local static資料](https://learn.microsoft.com/en-us/cpp/build/reference/zc-threadsafeinit-thread-safe-local-static-initialization?view=msvc-170) は、初期化中の他threadの待ちと、初期化後のTLS利用を説明する。今回の構造はこれと整合するが、API・命令形だけではsource symbolを確定できない。[SleepConditionVariableSRWの仕様](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-sleepconditionvariablesrw) は、sleep時の解放・復帰時の再取得、spurious wakeへのpredicate再確認を説明する。待ちAPIの存在は継続的な競合の証拠ではない。

## 範囲と再現性

- 起点候補graphは200群のbudgetに到達。197群は全decode、3群はpartial。参照vtableの静的slot候補は展開するが、動的なvirtual dispatchの実際の対象、data依存、動的API解決は確定していない。完全なcall graphではない。
- file-backed executable sectionのnormal-import IAT向け `FF15/FF25` 候補を探し、unwind範囲の先頭からdecodeして命令境界とslotを照合。prefix付き命令も既にdecodeした命令との照合で処理した。
- この限定方式で4,641個の同期API参照箇所を確認。うち起点graph内19箇所。77候補はunwind未解決またはpartial decodeのため確認済みに含めていない。これは静的call/jump site数であり、実行回数・待ち回数・lock数・hotspot数ではない。他の呼出し形式は対象外。
- 詳細に保存した7群は全decode済み。文字列と4本の直接pathは証拠JSONに保存。大きな全graph・全site一覧はGit保存を省き、生成recipeとその生成hashを保存した。

保存先は [schedulerの証拠](generated/deep-native-2026-10-05/scheduler/scheduler-classified-evidence.json) と [走査集計](generated/deep-native-2026-10-05/scheduler/probe-summary.json)。再生成は [手順](deep-native-reproduction-2026-10-05.md) を参照。

## 開発上の判断

この2経路を、そのままworker barrierやsimulation state lockとしてpatchする候補から外す。runtimeで初期化がwarm-up中に済んでいれば、計測区間の利益はない。統計更新はobserver overheadの候補として、本体Taskの費用と分ける。実際のworker completion、UI reader、allocator内部同期は未解決で、同区間のWPA Running/Ready/Waiting・readier chainとcaller stackで追う。ロックを除去したりheuristicの強制parallel化を行う根拠は得られていない。
