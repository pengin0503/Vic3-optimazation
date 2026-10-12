# オフラインCPU研究：最初の実装・静的証拠ハンドオフ

Date: 2026-10-11
Branch: `research/offline-cpu-parallelism-20261011`
Spec: [2026-10-11-offline-cpu-research-design](../specs/2026-10-11-offline-cpu-research-design.md)
Plan: [2026-10-11-offline-ticktask-gap-triage](../plans/2026-10-11-offline-ticktask-gap-triage.md)

## 実装範囲と検証状態

`tools/triage_ticktask_unresolved.py` と `tests/test_triage_ticktask_unresolved.py` を追加。原本 `research/generated/ticktask-dependencies-1.14.5.json` を読んで、未解決理由と根拠RVAを保ったまま分類する。ゲームプロセスへのアクセス・detour・native patch・synthetic CPU speedup claim はない。

独立した最小ローカル作業領域で、テストモジュール import failure (RED) を見た後、実装して unittest 7件が成功 (GREEN)。実行コマンドは `python -m unittest discover -s tests -p test_triage_ticktask_unresolved.py -v`。ローカルには GitHub の完全 checkout がないため、既存テスト群の全件実行、Windows CTest、実ゲーム runtime の検証は **未実施**。GitHub Actions は起動していない。

実装は `format_version=1` と exact hash のみを受け付ける。RVAは16進文字列・64-bit、function rangeは半開区間。複数の異なる関数に属するRVAは owner null + ambiguous。入力は変更しない。CLIは入力と同じ出力パスを拒否し、入力検証後の一時ファイルを atomically replace する。出力には入力JSONのbyte SHA-256を保存する。

実行例（repository root、`local-data` は生成物専用）:

```sh
python tools/triage_ticktask_unresolved.py research/generated/ticktask-dependencies-1.14.5.json --output local-data/ticktask-triage.json
python -m unittest discover -s tests -p test_triage_ticktask_unresolved.py -v
```

## 実入力の独立読み取り結果

GitHubに保存されているJSONを直接解析し、原本の関数範囲からownerを検査した。これは追加ゲーム内測定でも新しい依存edgeの復元でもない。

- `victoria3.exe` SHA-256 `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`。
- 入力artifactの保存済みSHA-256 `6dee83e98fbf33fc6b3eabcbb7770fd50af953e3f21fee0cdf666d08069d8fd4`。
- 41関数群、parent-child確定edge 0、未解決59レコード。
- `indirect_call_or_jump` 40件: 40件すべての命令RVAが既知関数の半開範囲内、複数ownerは0。
- `depth_budget` 9件: 既存関数range外のtarget RVA。
- `no_unwind_metadata` 7件: 既存関数range外のRVA。
- `unmapped_ticktask_identity` 2件と `parent_child_dataflow_not_reconstructed` 1件: 命令RVAなし。
- 既知function ownerなし16レコード、RVAなし3レコード。ownerが確定してもcall先・parent-childは確定しない。

### Exact exeからの小規模 disassembly spot-check

提供済み `Vic3_data.zip` の `Vic3_data/binaries/victoria3.exe` を抽出し、97,774,200 bytes・上記SHA-256が一致することを確認。GNU objdump (pei-x86-64, image base `0x140000000`) で限定命令範囲を確認した。

| RVA | 命令と隣接データフロー | 保守的判定 |
| --- | --- | --- |
| `0x7d670f` | `RCX <- [RBX+0x10]`、`RAX <- [RCX]`、`EDX` は count×4、`call [RAX+8]` 後に元データをcopyする処理へ進む | 動的メモリ確保を伴うbuffer拡張と整合。TickTask親子関係ではない |
| `0x64b336` | `RCX <- [RBX+0x10]`、`RAX <- [RCX]`、`call [RAX+0x10]`、後続で `[RBX+8]` と `[RBX]` を更新 | container storageの更新・解放に整合。仮想関数の正体は未確定 |
| `0x3c2d720` | `RCX <- [RBX+0xa0]`、`RAX <- [RCX]`、`call [RAX+0x10]`、後続で `[RBX+0x90]` と `[RBX+0x98]` を0に戻す | resource release/cleanupと整合。ほかの類似siteも個別検証が必要 |

再現（既存の信頼できる ZIP からexeを展開した後）:

```sh
objdump -d -M intel --start-address=0x1407d66b0 --stop-address=0x1407d674e victoria3.exe
objdump -d -M intel --start-address=0x14064b2f0 --stop-address=0x14064b34f victoria3.exe
objdump -d -M intel --start-address=0x143c2d6d0 --stop-address=0x143c2d7d0 victoria3.exe
```

これらの命令の構造と即値は観測済み。実際の source class/function、allocator interface、dependency semantics は未確認。類似パターンは静的追跡の優先順位を判断する補助情報としてのみ利用する。

## 次のオフライン作業と実測gate

1. scheduler/graph jobの登録・実行経路を直接callとobject dataflowに分け、上記40siteから正しいgraph-objectの構造証拠を優先。既存 `tools/map_ticktask_dependencies.py` の候補を推測でconfirmed edgeに変更しない。
2. 独立した合成スケジューラでchunk balance/dispatch/barrierの費用を変え、モデル上の差だけを比較。実ゲームの速度へ換算しない。
3. 既存 `src/native/` の Windows synthetic host・module resolution diagnosticsを拡張する場合は、先に重複テストと loader code 4 の現行契約を確認。live targetへの接続は行わない。
4. ゲーム側 Task 9 attach、observer overhead、同一区間12/16の同期OS Running/Ready/Waiting、task boundary、checksum は未達のまま。これらなしにロック除去・強制parallel化・lookup bypass・ゲーム性能改善の判断へ進まない。

**結果の境界:** 研究用の分類と追加静的証拠が得られたのみ。ゲームエンジンのCPU使用率および実ゲームwall timeには変更なし。
