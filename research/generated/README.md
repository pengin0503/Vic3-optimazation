# 生成済みの研究資料一覧

これらのファイルは、ローカルで提供されたVictoria 3 1.14.5の研究用アーカイブを`tools/analyze_vic3.py`で解析して生成したものです。

検証済みの対象実行ファイル：

- サイズ：97,774,200バイト
- SHA-256：`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- PE32+ x86-64
- リンカー：MSVC 14.44
- セクション：`.text`、`.rdata`、`.data`、`.pdata`、`.rsrc`、`.reloc`
- 埋め込まれたPDBパス：`C:\mnt\gsg\caligula\caligula\outputdir_windows\binaries\victoria3.pdb`

抽出件数：

- 一意の`CTickTask_*`名：260件
- インポートされたDLL：24件
- プロファイラー・コンソールコマンドの識別子：17件
- ソースコードのパス文字列：900件以上
- Pdxの並列処理・タスク基盤を含む、タスク・ジョブ・並列処理関連のRTTI・テンプレート文字列

コミット済みの簡潔な一覧：

- `ticktasks-1.14.5.txt`
- `profiler-commands-1.14.5.txt`
- `imports-1.14.5.txt`

インポートシンボル、ソースパス、RTTI・ジョブ文字列を含む完全なJSON出力は、手作業で維持するソースファイルとして扱わず、ローカルで再生成します。

```text
python tools/analyze_vic3.py <Vic3_data.zip-or-install> \
  --output research/generated/static-analysis-local.json
```

`VIC3_DATA`にローカルのアーカイブを指定すると、統合テストが既知の1.14.5実行ファイルのハッシュと、復元した主要なインターフェースを検証します。
