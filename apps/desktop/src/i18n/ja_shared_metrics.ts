export const jaSharedMetrics = {
  consentTitle: '利用統計をこの端末に記録しますか？',
  dialogTitle: '利用統計',
  consentBody:
    'Nara は使われ方を集計できます：セッションの長さ、実行されたモデルとツール、何かが失敗したタイミング。メッセージ、ファイル、パス、エラーテキストは一切記録しません。',
  whatIsCollected: '集計される内容',
  collectedActivity: 'セッション：長さ、結果、エラーの種類、1 日あたりのアクティブ時間',
  collectedModels: 'モデル：使用したモデル、トークン合計',
  collectedNames: '機能：使用またはオフにした組み込みツール、コマンド、アプリの領域、設定',
  collectedMilestones: 'セットアップ：完了したステップ、プロバイダーの接続、スキル・プラグイン・ジョブの数',
  collectedReliability: 'アプリの状態：クラッシュ、起動と応答の速さ、アップデート、メッセージングの接続',
  collectedUsage: 'エージェントの品質：失敗した編集、壊れたツール呼び出し、抜け出せないループ、タスクごとのコスト',
  collectedMachine: 'マシン：OS、RAM の範囲、GPU の種類、Nara のバージョン、ローカルモデルの使用',
  sending:
    'この選択では集計値をこの端末に保存し、送信しません。送信には config.yaml で送信先と送信設定を別途指定する必要があります。ローカル収集は設定画面でいつでも変更できます。',
  readDocs: '詳細を読む',
  share: '端末に記録する',
  off: '共有しない',
  saveFailed: '選択を保存できませんでした',
  sendLabel: '利用統計をこの端末に記録する',
  sendDesc:
    '集計値のみを端末に保存し、送信しません。メッセージ、ファイル、パス、エラーテキストは記録しません。',
  unavailable: 'この設定を変更するには Nara バックエンドを更新してください。',
  stripBody: '件数のみ。メッセージやファイルは一切含みません。',
  stripReaskBody:
    '改めてお尋ねします：以前のバージョンでは、この質問が表示される前に「今はしない」が保存されることがありました。',
  stripChoices: { share: '端末に記録', off: '今はしない' },
  stripDetails: '詳細'
}
