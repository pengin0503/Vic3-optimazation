# Victoria 3 1.14.5 — Debug Mode / Console 起動手順

Date: 2026-10-05  
Repository: `pengin0503/Vic3-optimazation`  
Target: Victoria 3 Windows 1.14.5

## 目的

Vic3-optimazation の実測では、次の開発者console commandを使用します。

```text
Threading.TaskThreadCount <count>
clear_ticktask_timings
dump_ticktask_timings
```

通常起動では開発者consoleを使用できない前提で進めます。

そのため、**実測用runではVictoria 3をDebug Modeで起動してください。**

---

## 方法A — Steam Launch Options

推奨方法です。

1. Steamを開く
2. Libraryから `Victoria 3` を右クリック
3. `Properties` を開く
4. `General` → `Launch Options` を開く
5. 次を入力する

```text
-debug_mode
```

6. Propertiesを閉じる
7. Victoria 3を通常どおり起動する

この設定は削除するまで維持されます。

ベンチマークを複数run行う場合はこちらが便利です。

---

## 方法B — Paradox Launcher

LauncherからDebug Modeで起動する方法でも構いません。

LauncherのGame Settingsで、Debug Mode起動に相当する項目を使用します。

実測中はSteam Launch Options方式とLauncher方式をrunごとに混在させず、同じ起動方法へ統一してください。

---

## Consoleを開く

Debug Modeでゲームを起動した後、consoleを開きます。

通常はバッククォート / チルダ系キーを使用します。

例:

```text
`
~
```

ただし、日本語キーボードなど配列によってキー位置や入力方法が異なる場合があります。

consoleが開けば、画面上にコマンド入力欄が表示されます。

---

## 最初の確認

最初はbenchmarkを開始せず、console commandが使用できるか確認してください。

### 1. TaskThreadCount

例:

```text
Threading.TaskThreadCount 8
```

エラーにならず受理されることを確認します。

### 2. TickTask timing reset

```text
clear_ticktask_timings
```

### 3. TickTask timing dump

数秒ゲームを進めた後:

```text
dump_ticktask_timings
```

これで `ticktask_timings.csv` が生成されるか確認します。

---

## ticktask_timings.csv の検索

1.14.5静的解析では、デフォルトfilenameとして:

```text
ticktask_timings.csv
```

が確認されています。

まずDocuments側を検索します。

PowerShell:

```powershell
Get-ChildItem "$env:USERPROFILE\Documents\Paradox Interactive\Victoria 3" `
  -Recurse -Filter ticktask_timings.csv -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 10 FullName, LastWriteTime, Length
```

見つからない場合は、Victoria 3のinstall directory側も検索してください。

最初の実測時に実際の出力pathを記録します。

---

## 実測時の基本順序

各runで次の順序を使用します。

```text
Victoria 3をDebug Modeで起動
        ↓
heavy saveをload
        ↓
pause
        ↓
Threading.TaskThreadCount <count>
        ↓
camera / UI状態を固定
        ↓
clear_ticktask_timings
        ↓
Speed 5 + stopwatch開始
        ↓
固定終了日に到達
        ↓
pause + stopwatch停止
        ↓
dump_ticktask_timings
        ↓
ticktask_timings.csv保存
        ↓
finalize_benchmark_run.py
```

---

## 推奨quick pass

最初から完全28runを行う必要はありません。

まず:

```text
TaskThreadCount = 1
TaskThreadCount = 4
TaskThreadCount = 8
TaskThreadCount = 16
```

の4条件を取得し、console / CSV / benchmark workflowが正常に動くことを確認します。

その後、本番matrix:

```text
1 / 2 / 4 / 6 / 8 / 12 / 16
```

へ進みます。

---

## Debug Mode と性能比較

TickTask CSV取得にはDebug Modeが必要ですが、Debug Mode自体が通常起動と完全に同じ性能条件とは限りません。

そのため最終的には、同じheavy save・同じ固定期間で:

### Debug Mode

```text
-debug_mode
TickTask CSVあり
```

### Normal Mode

```text
通常起動
profilerなし
wall-clockのみ
```

を比較します。

推奨:

- Debug Mode wall-clock × 3
- Normal Mode wall-clock × 3

これによりDebug Modeのoverheadを確認できます。

---

## Console Enabler MODはbaselineに使用しない

baselineではconsoleを開くためのMODを使用しません。

理由:

- MOD由来のscript/UI処理が追加される可能性
- benchmark条件が増える
-再現性が下がる

ゲーム標準のDebug Modeを使用します。

---

## 最初に確認するチェックリスト

- [ ] Steam Launch Optionsに `-debug_mode` を設定
- [ ] Victoria 3を起動
- [ ] consoleが開く
- [ ] `Threading.TaskThreadCount 8` が受理される
- [ ] `clear_ticktask_timings` が実行できる
- [ ] `dump_ticktask_timings` が実行できる
- [ ] `ticktask_timings.csv` が生成される
- [ ] CSVの実際の出力pathを記録
- [ ] その後quick passへ進む

---

## 関連資料

完全な実測手順:

`docs/superpowers/guides/2026-10-05-runtime-data-collection-guide-ja.md`

Windowsなしで進められる作業:

`docs/superpowers/plans/2026-10-05-offline-work-roadmap-ja.md`

現在のcheckpoint:

`docs/superpowers/reports/2026-10-05-offline-research-checkpoint.md`
