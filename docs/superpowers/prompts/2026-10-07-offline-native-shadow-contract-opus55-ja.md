対象: `pengin0503/Vic3-optimazation`

開始時の最新mainを取得し、以下を読んでB0のTask 1〜4を順に実装してください。

- 設計: `docs/superpowers/specs/2026-10-07-offline-native-shadow-contract-design.md`
- 計画: `docs/superpowers/plans/2026-10-07-offline-native-shadow-contract.md`

SuperpowersのNative / executing-plansを使用し、TDD・不具合時のsystematic-debugging・verification-before-completionを守ってください。

対象はoffline locator、所有fixtureとopaque結果の正規化、original exactly onceのshadow、runner/CIだけです。live memory、native lookup hook、DLL/loader変更、ゲーム内の検索省略には進まないでください。Stage A、V3PF v1、既存target/goldenを維持してください。

計画の検証とレビューを完了し、記録・results・文書の状態を更新してください。実行できない検証は未実行と明記し、native等価性や速度改善を主張しないでください。利用可能なら`VIC3_DATA`に添付の正本ZIPを指定し、optional exact-build locatorも検証してください。

Taskごとにcommitし、最後に最新mainへforceなしのfast-forwardで統合してください。PR作成・他branch削除は不要です。完了報告はcommit、テスト/CI結果、残るnative gateに絞ってください。
