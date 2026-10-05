# PC内のVictoria 3資料の保存と追加解析

調査日: 2026-10-05（日本時間）  
保存先: 非公開 `pengin0503/Vic3-optimazation`  
開始時のmain: `1c018568c1acc5108265301b25a29c5989db9a67`

PCのVictoria 3関連ファイルを読む許可と、情報をできるだけGitHubへ保存する依頼に基づいて、元ログ・計測CSV・設定・スクリプト・セーブの再現条件を追加保存した。既存の内部処理調査を引き継ぎ、現在のゲーム本体で再検証し、主要9処理の静的呼び出し関係も追加した。

## 保存したもの

| 対象 | 今回の保存内容 |
| --- | --- |
| ゲーム本体、Eドライブの同名コピー、Workshop、ユーザーデータなど | 154,570件・計54,931,932,783バイトのファイル一覧。サイズ・更新時刻を記録。画像、音声、実行ファイルなどは一覧中心で、全内容をアップロードしたという意味ではない |
| 設定・スクリプト・GUI・ログ・計測資料 | 5,647件、展開時89,398,266バイトを22個のZIPに保存。各ファイルのSHA-256とZIP内の保存位置を記録 |
| 旧TickTask計測 | 1/2/4/6/8/12/16スレッドの初回資料、8/12/16スレッドのbench2、3か月のbench3。13個のCSVを再集計。既存の3か月の生CSVも保持 |
| センサー記録 | 旧計測10件のHWiNFO CSV原文と、列番号を保持した温度・使用率・電力などの集計 |
| ログ | 現在のログ、ローテーションされたログ、logs2、元のvic3_logs.zip。セッションを混ぜずに索引化 |
| 計測用セーブ | 1911.3.1.6のアメリカ合衆国セーブ。元は266,677,017バイト、gzipで42,438,889バイト。9個の順序付き分割ファイルから復元可能 |
| セーブの識別情報 | PC内で発見した590件の.v3ファイルのサイズ・更新時刻・SHA-256。内容を保存したセーブは上記1件。全590件の本文を保存したという意味ではない |
| シミュレーション定義 | game/commonの3,107ファイル、eventsの328ファイル、GUIの205ファイル、Jomini/Clausewitzの資料、scripted_testsの例など |
| MOD | Workshop内の639件のスクリプト・設定・GUI、GORAを含むメタデータ、ローカル建設MODの資料、回収GUI、ランチャーのMOD・プレイセット情報 |
| 診断資料 | 88件のprofiler/scripted_tests等の関連ファイル索引、現在の性能関連define値 |
| バイナリ識別 | 現在とEドライブのコピーにある計50件のEXE/DLLについて、ハッシュ・PE情報・import/export情報。EXE/DLL本体は保存していない |

主な入口は [保存一覧](../../../research/generated/pc-evidence-2026-10-05/preservation-index.json)、[収集範囲](../../../research/generated/pc-evidence-2026-10-05/scope.json)、[ZIP一覧](../../../research/generated/pc-evidence-2026-10-05/archive-index.json)、[元ファイルとの対応](../../../research/generated/pc-evidence-2026-10-05/source-files.json)。内容を保存した資料は `input-data/pc-evidence-2026-10-05/` にある。

一覧は発見したVictoria 3関連フォルダーを対象にしたもの。PC上の全ドライブ・全フォルダーを漏れなく検索したという主張はしない。対象に関係のない資料は収集していない。ランチャーのデータベースは読み取り専用でMOD・プレイセット関連テーブルを抽出し、アカウント・認証関連列は対象外にした。

## 今回確かめたこと

現在の実行ファイルのSHA-256は既存調査と同じ:

`9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`

現在の実行ファイルから260個のTickTask名、258個の具体クラス対応、920個のソースパス、17個のprofiler/consoleコマンドを抽出した。18個のexact-buildシグネチャはすべて一致。未対応の名前は `CTickTask_CheckNonFulfillments` と `CTickTask_MoveFormations` として明示している。[現在の静的解析要約](../../../research/generated/pc-evidence-2026-10-05/native/summary.json)

前回のdispatch再現recipeを実際のインストール先に適用し、18個の選択範囲と4個の直接callsiteを再現した。[現在のdispatch資料](../../../research/generated/pc-evidence-2026-10-05/dispatch-live/dispatch-regions.json)

UpdateEmployment、UpdateStatePopNeedCache、ProcessPopPurchases、RecalculateModifierNodes、UpdateWorldMarket、UpdateAI、UpdateStateTrades、UpdatePopGrowth、MergeSmallPopsを起点に、深さ2・最大80関数・各関数最大65,536バイトの制限で呼び出し候補を調べた。80関数グループを保存し、215個の未展開候補を理由付きで残した。この上限付き解析は全経路の網羅を意味しない。[主要9処理の静的呼び出し関係](../../../research/generated/pc-evidence-2026-10-05/hotspot-nine-tasks.json)

Eドライブのゲームコピーと現インストールについて、GUI・defines・game_rules・scripted_tests等の399ファイルをハッシュ比較し、399件すべて一致した。[比較結果](../../../research/generated/pc-evidence-2026-10-05/historical-current-controls-comparison.json)

現在の `content_load.json` は `enabledMods=[]`、`disabledDLC=[]`、`enabledUGC=[]`。これは今回読み取った設定であり、過去の計測時のMOD状態を遡って証明するものではない。ハードウェアは現在のsystem.logにRyzen 7 9700X・8物理/16論理コア、Radeon RX 7800 XT、RAM 31,938MBとして記録されている。

## センサー記録の読み直し

HWiNFOの10記録は同じ列名が複数回現れるので、辞書で上書きせず列番号で保持した。UTF-8の見出しとCP932の「いいえ」などが混在しているため、セル単位で復号し、復号不能セルが0件であることを確認した。対象のHTC・PROCHOT CPU・PROCHOT EXTの列は、採取済みサンプル内ですべて「いいえ」だった。

bench2の8/12/16ファイルにあるCPU温度（Tctl/Tdie）の最大値は59.2/58.6/58.6℃。これらは過去のキャプチャ全体に対する記録であり、現在の3か月計測の温度ではない。また、ロード・待機を含む可能性があり、計測の開始終了と正確に同期した区間は未確認。CPU使用率が低いことだけで並列化不足やロック原因を断定しない。[センサー集計と列番号](../../../research/generated/pc-evidence-2026-10-05/sensor-capture-summary.json)

## セーブを復元して別端末で再利用する

回収したセーブのメタデータはVictoria 3 1.14.5、1911.3.1.6、アメリカ合衆国、Pop Consolidation=`aggressive_consolidation`。そのセーブは現在のユーザーフォルダーにある同名セーブとSHA-256で一致した。ただし、過去の全計測にこの同じハッシュのセーブを使用したことを証明する記録はない。[セーブ検証](../../../research/generated/pc-evidence-2026-10-05/save-validation.json)

復元後のSHA-256:

`08d22b19929a5ec480e3e45f4e1eb8ff581b91e1de1b4bdb16512e3d0ea5e949`

リポジトリを取得した後、ルートで次のPythonを実行すると `local-data/recovered-benchmark-save.v3` に復元できる。ゲームのセーブフォルダーへ自動配置はしない。

```python
from pathlib import Path
import gzip, hashlib, io, json

root = Path.cwd()
evidence = root / "research/generated/pc-evidence-2026-10-05"
parts = json.loads((evidence / "save-parts.json").read_text(encoding="utf-8"))
compressed = bytearray()
for entry in parts["parts"]:
    data = (root / entry["path"]).read_bytes()
    assert len(data) == entry["bytes"]
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]
    compressed.extend(data)
assert hashlib.sha256(compressed).hexdigest() == parts["gzip_sha256"]
target = root / "local-data/recovered-benchmark-save.v3"
target.parent.mkdir(parents=True, exist_ok=True)
assert not target.exists(), "Choose an unused output file"
with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source, target.open("xb") as output:
    digest = hashlib.sha256()
    size = 0
    for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
        output.write(block)
        digest.update(block)
        size += len(block)
expected = json.loads((evidence / "save-validation.json").read_text(encoding="utf-8"))
assert size == expected["restored_bytes"]
assert digest.hexdigest() == expected["restored_sha256"]
print(target, size, digest.hexdigest())
```

他のZIPは `source-files.json` のarchive/memberを使って必要なファイルだけ取得できる。ゲーム定義を読みたいだけなら、EXEを別途持っていなくてもGitHubの保存資料から開始できる。実行ファイルの更なる解析には同じSHA-256のEXEが必要。

## 検証と次の作業

22個のZIPのCRCと5,647個の展開内容のSHA-256を照合した。セーブはgzip展開後のサイズ・SHA-256と、9個の分割ファイルの連結内容を検証した。現在のゲーム本体を入力にしたintegrationとCapstoneを含め、既存68テストはすべて成功し、skipは0件。[収集検証](../../../research/generated/pc-evidence-2026-10-05/collection-validation.json) / [追加解析検証](../../../research/generated/pc-evidence-2026-10-05/additional-analysis-validation.json) / [テスト結果](../../../research/generated/pc-evidence-2026-10-05/repository-test-results.txt)

この保存作業でゲーム本体・ゲーム設定・MOD・セーブには書き込んでいない。資料と解析結果はプロジェクト側へ生成した。収集時に変化したため除外したファイルと読み取りエラーは0件。

次の調査は、復元セーブを基準に同じ区間を反復計測し、現在の3か月CSVとOSのCPU/待ち/stack記録を同期すること。追加保存したscripted_testsの例とprofiler資料は自動化の調査に使えるが、retail buildでの起動経路や測定負荷はゲーム上で未検証。静的callgraphをOSのstackと照合し、待ち・計算・schedulerのどれが支配的かを区別してから性能変更を検討する。

今回もnative hook、scheduler変更、DLL注入、性能パッチは実施していない。資料保存・静的対応・過去データ集計の成功と、実ゲームの性能改善は区別する。
