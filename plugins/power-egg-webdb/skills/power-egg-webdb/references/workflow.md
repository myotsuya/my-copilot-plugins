# 運用・生成手順

## 対応範囲

提供仕様はPOWER EGG3.0 Ver3.5cの操作資料と26原本ZIPの解析を基礎とする。追加TXTは9件のXMLサンプル。実機取込成功の新しい報告は受けていない。参照情報の【公式】【ユーザー確認済み】【観測】【推定／未確認】を区別する。

基本生成器は1行／複数行文字列、数値、日付・年月・時刻、フラグ、チェックボックス、ラジオ、ドロップダウン、会社・部門・社員選択の13型。単純画面、一覧、選択肢固定値一致、ログイン社員一致、単一ラジオ／ドロップダウン分類の件数または数値合計。基本生成器の範囲外はXML実例で実装の根拠を確認する。型のサンプルがあることと全設定の自動対応は区別する。

## 依頼を整理する表

利用者へ必要に応じて短く見せる。必ず全欄を質問する必要はない。

|内容|設計に残すこと|
|---|---|
|用途・DB名|利用者、登録する情報、1レコードの単位|
|項目|表示名、型、順序、必須、桁数、小数、選択肢、初期値、再利用|
|画面|一覧列、入力／表示の配置、見出し、幅・高さの指定|
|条件・集計|比較対象、分類、件数／合計、初期表示|
|拡張|明細、通知先・条件、計算、外部参照、関連DB|
|運用|移行先製品版、権限、登録・編集・削除の制限|

## 作業コマンド

`<skill>`はこのスキルの実際のディレクトリ、`<python>`は環境で利用可能なPythonを表す。出力先は作業領域／利用者向け成果物領域を使い、スキル内の資料を書き換えない。

```text
<python> <skill>/scripts/webdb.py build request.json DB名.zip
<python> <skill>/scripts/webdb.py validate DB名.zip --basic
<python> <skill>/scripts/webdb.py pack databasedef.xml DB名.zip
<python> <skill>/scripts/webdb.py validate DB名.zip
```

buildとpackはZIPに加えて、`DB名-files/`に2ファイル、`DB名-validation.json`に検査範囲とSHA-256を作る。既存出力先への上書きは拒否する。再作成時は新しい出力名または新しい作業ディレクトリを使う。

原本復元・観測型の抽出が必要な場合：

```text
<python> <skill>/scripts/webdb_memo_tool.py restore <skill>/sources/POWER_EGG_WebDB_仕様.md xdb_exp5.zip original.zip
<python> <skill>/scripts/webdb_memo_tool.py validate-archive original.zip
<python> <skill>/scripts/webdb_memo_tool.py field-example <skill>/sources/POWER_EGG_WebDB_仕様.md 52
```

原本にはCSV・添付が含まれる場合がある。元ZIPの完全復元は新規定義候補の2ファイル規則とは別。原本ZIPの全内容を新規候補に混ぜない。

## 検査の区別

- `validate-archive`：原本向けのCRC、XML、certificateなどの物理検査。全26原本で確認。
- `webdb.py validate --basic`：上記に加え、基本生成器の2.91候補に限るID参照、レイアウト、集計等の検査。
- `webdb.py validate`：2ファイル構成、UTF-8、要素順、限定的な項目参照と親の全項目順を検査。明細・通知・外部参照の完全な検証器ではない。
- 実機取込検証：これらのローカル検査と別。POWER EGGへのアクセス機能は付属しない。

## 引渡し

ZIPと2ファイルのリンクを示し、要件の充足、基本型／個別実装、未対応や残る設定を簡潔に説明する。ZIPのSHA-256と実機未確認を記載する。権限は取込後に設定する必要があり、参照先・組織・通知条件も確認する。元サンプルの社員ID等を依頼者の環境で有効な値と扱わない。

他の利用者が使う場合はプラグインとファイルを利用できる実行環境が必要。同じアカウントに保存されたことだけで、他者へ共有済み・インストール済みと説明しない。
