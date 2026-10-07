# 全ブランチのmain統合記録 — 2026-10-07

## 対象と方法

ユーザーの「さまざまなブランチをすべてmainに統合」の指示に基づく。開始時mainは`f5882d4214c8b3102a5f385bc11c778827e17e02`。開始時と更新直前のinventoryにはmain以外が9本あり、head変更はなかった。

6本は既にmainの祖先。残る3本は共通祖先からの差分を確認し、下記headをmerge parentに持つ統合commitで履歴と成果物を取り込む。mainの既存headをfirst parentにしてforceなしで更新する。PRは作成せず、branchも削除しない。

| branch | 確認したhead | 取り扱い |
|---|---|---|
| `ccr-3431d274-cl7wbf` | `66ac704e46c1028655b2577aaa6f14479b4fce1b` | 開始時mainの祖先。既に統合済み |
| `claude/vic3-native-profiler-tasks-suugii` | `271d5ea0a2a46557ed1ef21ac89df42c3d464d51` | 今回merge parentとして統合 |
| `docs/lfs-input-policy-cleanup` | `8ad039c323f8dd234c2938f177419adaeb2925aa` | 開始時mainの祖先。既に統合済み |
| `feat/offline-analysis-2026-10-05` | `5d628092e196187c715ea3c76d2c508420537eba` | 開始時mainの祖先。既に統合済み |
| `public-architecture-static-followups-2026-10-05` | `21d5fbe0adeb87ab913aec5b7d92e02807b58aef` | 今回merge parentとして統合 |
| `research/deep-native-evidence-2026-10-05` | `60e15bddf9768c79faf8d67e4ac6656d24796020` | 開始時mainの祖先。既に統合済み |
| `research/repeated-benchmarks-2026-10-05` | `b9149ebacb9d388c238d72c30e6c92770615b0f0` | 開始時mainの祖先。既に統合済み |
| `work/offline-quality-profiler-spec` | `f35df37eab6463b09444aec350038b9ab6e68a73` | 開始時mainの祖先。既に統合済み |
| `work/public-architecture-static-followups-2026-10-05` | `f2e028b56840ae96f2fc08a741331e28cd865f4c` | 今回merge parentとして統合 |

## 衝突の解決

- native branchの`.gitignore`とroot READMEはthree-wayで両方の変更を保存した。`src/README.md`の追加段落の衝突も、Stage Aのportable coreとnative profilerの説明を両方残した。
- root READMEの「DLL injection未実装」とsrc READMEの「Task 9実装開始前」「static CRT」は、統合されたprototypeに合わせて更新した。shared CRT、実ゲーム検証待ち、loader診断を明記した。履歴報告の過去の状態は書き換えていない。
- public/workのmodifier-node成果物6ファイルは異なるschema/APIであり、同一内容ではない。通常のpathにはwork版を採用した。full graph、入力container/RTTIの来歴、strict RTTI hash検証を維持するためである。
- public版の6ファイルを`research/alternatives/modifier-node-public-2026-10-05/`以下にoriginal pathとbyte内容のまま保存し、isolated overlayでの再実行方法をREADMEに記した。publicの履歴もmerge parentとして保持する。
- work版のGameState同期候補、employment-stage map、recipes、testsも取り込んだ。同期候補は静的証拠であり、wait原因の証明とは扱わない。
- 既存treeをbaseとして変更pathだけを更新し、未変更のbinary/LFS資産を置き換えない。V3PF v1 golden、native target JSON、Stage Aコードとresultsを変更していない。

## 統合候補のローカル検証

isolated scratch workspaceにGitHub blobをmaterializeし、Git blob SHA-1と受信bytesの一致を検査した。大きいsync-callers JSONはContents APIの空contentを使わずblob APIで取得し、2,398,993 bytesとhash一致を確認した。これは取得方法の補正でありsourceの修正ではない。

- Python: `PYTHONPATH=<isolated capstone 5.0.7> VIC3_DATA=<exact input ZIP> python -m unittest discover -s tests -v` — **157件OK、skipなし**。
- Stage A: GCC 13.3、CMake Release、warnings-as-errors。C++29件を含むCTest **5/5 PASS**。
- runner: seed `20261007`、1000 rebuildのfresh resultが既存`results.json`とbyte一致。
- `python tools/render_native_profiler_targets.py --check` — PASS。
- public別版: isolated copyに保存した6pathをoverlayし、専用test **7件OK、skipなし**。exact ZIPによる2回のreproductionも一致。
- adopted branch filesとpublic保存ファイルは全て元blob SHAと一致。modifier-node/syncのartifact-indexのSHA-256は対応するJSON bytesと一致。解決した3ファイルにはconflict markerがない。

Windows専用native build、real MinHook、DLL/loader fixtureはローカルLinuxでは実行しない。統合後mainの`tests` workflowでPythonとWindows native jobを確認する。CIの最終状態は該当main commitのActions runを参照する。既存lookup-reuse-core workflowはpath filterを保持しており、coreを変更しないこの統合では新規runを要求しない。

## B0とnative gate

[B0書面設計](../specs/2026-10-07-offline-native-shadow-contract-design.md)を保存する。書面レビュー後に実装計画へ進む。今回はB0 product codeを書かず、native lookup detourやlive memory viewも追加しない。native profilerの統合は実ゲームのattach成功、observer overhead、lookup ABI、live table寿命、worker scopeの証明にならない。

