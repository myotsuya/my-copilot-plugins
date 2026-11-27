# 基本生成器の入力

これはエージェントが内部で準備するJSON。利用者にJSONの作成を要求しない。未知の設定や未対応型は拒否する。高度な要件を削除して基本型に置き換えない。

```json
{
  "database_name": "備品管理DB",
  "notes": "備品の利用状況を管理",
  "fields": [
    {"name": "備品名", "type": 1, "required": true, "max_length": 100},
    {"name": "状態", "type": 23, "required": true, "choices": ["保管中", "貸出中", "廃棄"]},
    {"name": "数量", "type": 2, "max_length": 10, "decimals": 0, "unit": "個"},
    {"name": "担当者", "type": 52, "default_login": true},
    {"name": "登録日", "type": 5},
    {"name": "備考", "type": 11, "max_length": 2000}
  ],
  "filters": [
    {"name": "貸出中", "field": "状態", "value": "貸出中"},
    {"name": "自分の担当", "field": "担当者", "login_employee": true}
  ],
  "summaries": [
    {"name": "状態別件数", "group_by": "状態", "method": "count", "display": "table"},
    {"name": "状態別数量", "group_by": "状態", "method": "sum", "field": "数量", "display": "vertical_bar"}
  ]
}
```

型：1=1行文字列、2=数値、5=日付、6=年月、9=時刻、11=複数行文字列、20=フラグ、21=チェックボックス、22=ラジオ、23=ドロップダウン、31=会社、51=部門、52=社員。

- 必須：database_name、1～100件のfields、各項目のname/type。予約語と同名、空名、重複名は拒否。
- required/reusableはJSONの真偽値。文字列の"false"を使わない。
- choicesは21/22/23型で必須。空・重複・改行を含む選択肢は拒否。
- max_lengthは1/2/11型。1～4000／1～20／1～9999。数値型のdecimalsは0～5かつmax_length未満。
- unitは数値型のみ。default_loginは社員選択52型のみ。その他の初期値や表示幅、行数は基本生成器で指定できない。
- filtersはラジオ／ドロップダウンの固定値一致、または社員選択52／標準登録者87／標準更新者89のログイン社員一致。ログイン社員の場合はvalueを指定しない。複数条件の組合せ等は個別実装。
- summariesのgroup_byはラジオ／ドロップダウン、methodはcountまたはsum。sumのfieldは別の数値型。countではfieldを指定しない。
- displayはtable/pie/line/vertical_bar/horizontal_bar。
- 全てのフィールド名参照は表示名の完全一致。

基本生成器は元サンプルの型別設定を複製する。DisplayWidthなど、入力で指定しない値が残ることがある。必要な見た目・初期値・制約を生成後のXMLで確認する。汎用の幅設計や明細・通知等の自動対応を約束しない。
