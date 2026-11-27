# サンプル索引

本文の番号・ZIP名には重複がある。内部の一意なsample番号とXML内のDB名を使う。添付TXTにはcertificateの実値がなく、元のXMLバイト列も保証されないため、原本ZIPの完全復元とは扱わない。

|参照|DB名|出力形式|項目数（親／明細）|原本の構造との照合|
|---|---|---|---|---|
|[sample-01](../samples/sample-01.xml)|安否報告DB|3.4|15／0|xdb_exp65.zip|
|[sample-02](../samples/sample-02.xml)|ソフトウェア管理台帳|3.2|31／0|xdb_exp62.zip|
|[sample-03](../samples/sample-03.xml)|目安箱|3.2|7／0|xdb_exp63.zip|
|[sample-04](../samples/sample-04.xml)|学生就活状況DB|3.2|18／1|xdb_exp64.zip|
|[sample-05](../samples/sample-05.xml)|クレーム管理DB（アパレル業）|2.91|70／0|xdb_exp1.zip|
|[sample-06](../samples/sample-06.xml)|アンケート集計（商品○○○）|2.91|12／0|xdb_exp5.zip|
|[sample-07](../samples/sample-07.xml)|資格情報管理台帳|2.91|15／0|xdb_exp16.zip|
|[sample-08](../samples/sample-08.xml)|在庫管理DB|2.91|36／0|xdb_exp46.zip|
|[sample-09](../samples/sample-09.xml)|設備管理台帳（印刷機）|2.91|16／15|xdb_exp58.zip|

## 元データの注記

- 添付の「サンプル7」は2回登場するため、資格台帳をsample-07、在庫管理をsample-08として整理した。設備管理はsample-09。
- アンケート例の記載ZIP名はxdb_exp65.zipだが、XML内のDB名と実構造で識別する。照合結果は上表を参照。
- 構造一致はXMLをパースして空白のみのノードを除いた比較。原本バイト列、実機取込成功、製品上の全動作を確認した意味ではない。
- 説明にある申請連携や通知などが、定義ZIPだけで移行・再現できるとは限らない。仕様の環境依存と未確認事項を照合する。

## 選び方

- 安否・社員選択・条件制御：sample-01
- ソフトウェア管理・資産台帳：sample-02
- 意見収集：sample-03
- 就活状況・学生台帳：sample-04
- 問合せ・進捗・連動・通知：sample-05
- アンケート・選択肢・集計：sample-06
- 資格・期限・社員別管理：sample-07
- 在庫・数値・発注点：sample-08
- 設備・点検・期限：sample-09

詳細な型・機能の件数は[sample-index.json](sample-index.json)。
