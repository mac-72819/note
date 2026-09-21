# note.com 下書き自動生成パイプライン

「羅針盤ノート」記事と競馬予想(v4ロジック)の記事下書きを自動生成し、
GitHub Issueに保存するツールです。**note.comへの実際の投稿(公開ボタンを押す操作)は
手動で行う設計**にしています(理由は下記「なぜ自動投稿しないのか」を参照)。

## できること / できないこと

- できる: 決まったスケジュールで、note.com にそのまま貼り付けられる形式の
  「タイトル・タグ・本文」をGitHub Issueとして自動生成する。
- できない: note.comへのログイン・記事の公開・予約投稿。これは毎回、
  生成されたIssueの内容をコピペして手動で行ってください。

## なぜ自動投稿しないのか

note.comは記事投稿用の公式APIを提供していません。自動投稿を実現するには
「非公式API＋セッションCookie」または「ブラウザ自動操作(保存したログイン状態を使用)」
のどちらかが必要になりますが、どちらも以下のリスクがあります。

- note.comの利用規約上、想定されていない方法である可能性がある
- サイトの仕様変更で予告なく動かなくなる
- ログインセッションの管理(パスワードやCookieの保管)自体にセキュリティリスクがある

このリスクを避けるため、今回は「下書きを作るところまで」を自動化し、
公開の最終判断と操作は必ず人間が行う設計にしています。

## セットアップ手順

1. このフォルダの中身一式を、新しく作成したGitHubリポジトリ(公開・非公開どちらでも可)に
   pushしてください。
2. リポジトリの Settings → Secrets and variables → Actions → New repository secret から、
   `ANTHROPIC_API_KEY` を登録してください（Anthropic Consoleで新規発行したキーを使用。
   過去にチャットなどに貼り付けてしまったキーは必ず失効させ、新しいキーを使ってください）。
   `GITHUB_TOKEN` は GitHub Actions が自動的に用意するため、登録不要です。
3. リポジトリの Settings → Actions → General で、Workflow permissions を
   「Read and write permissions」にしてください（Issueを作成するために必要です）。
4. Actionsタブを開き、`競馬予想 note下書き生成` と `羅針盤ノート記事 note下書き生成` の
   2つのワークフローが表示されていることを確認してください。

これで、スケジュール通りに自動実行され、Issueが作成されるようになります。
すぐに試したい場合は、各ワークフローの「Run workflow」ボタンから手動実行できます。

## スケジュール(初期設定)

- 競馬予想: 毎日 日本時間7:00（対象: 佐賀競馬。`KEIBA_NAR_TRACKS`環境変数で変更可能）
- 羅針盤ノート記事: 毎週火曜 日本時間7:00（AIリテラシー/英語学習/競馬コラム等をローテーション）

`.github/workflows/*.yml` の `cron` の値を書き換えれば、時間や頻度を変更できます。
（cronはUTC基準です。日本時間 = UTC + 9時間）

## 生成されたIssueの使い方

1. Issuesタブを開き、`note-draft` ラベルの付いたIssueを開く
2. 「note用タイトル」をコピーし、note.comの新規記事作成画面のタイトル欄に貼り付け
3. 「note用本文」をコピーし、本文欄に貼り付け（見出しはある程度自動整形されます）
4. 内容を確認・必要に応じて手直し、タグを追加してから公開する
5. 公開したらIssueをクローズする（運用ルールはお好みで）

## 既知の注意点・リスク

- **netkeibaのHTML構造が変わると、競馬予想の取得が失敗します。**
  `scripts/keiba/fetch_race_list.py` と `fetch_shutuba_past.py` のセレクタ(クラス名)を
  実際のページと突き合わせて更新してください。2026年9月時点のページ構造で動作確認済みです。
- **GitHub Actionsの実行環境(海外データセンターのIP)からのアクセスが、
  netkeibaにブロックされる／CAPTCHA化される可能性があります。** もし予想生成が
  継続的に失敗する場合は、自分のPCで手動実行するか、セルフホストランナー
  （自分のPCをActionsの実行環境として登録する方式）への切り替えを検討してください。
- 生成される競馬予想はAIによる分析であり、的中や利益を保証するものではありません。
  本文には免責文言を自動で入れていますが、内容は必ず自分の目で確認してから公開してください。
- サイトのスクレイピングは `netkeiba利用規約` の範囲内で、常識的な間隔(1リクエストごとに
  1.5秒以上)を空けて行うようにしています。対象競馬場・レース数を増やしすぎないようにしてください。

## ローカルでの試し方

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export GITHUB_TOKEN=ghp_xxxxx          # repoのissues権限を持つPAT
export GITHUB_REPOSITORY=your-account/your-repo

python scripts/keiba/generate_prediction.py
python scripts/article/generate_article.py
```

## ディレクトリ構成

```
.github/workflows/
  keiba-prediction.yml   … 競馬予想を毎日生成するワークフロー
  note-article.yml       … 羅針盤ノート記事を毎週生成するワークフロー
scripts/
  common/
    claude_client.py     … Anthropic API呼び出し
    github_issue.py      … GitHub Issue作成
    note_format.py       … note.com貼り付け用の整形
  keiba/
    fetch_race_list.py   … netkeibaのレース一覧取得(JRA/NAR)
    fetch_shutuba_past.py… netkeibaの出馬表(5走成績)取得
    v4_rules.py           … v4ロジック・Loto5アルゴリズムのルール定義(system prompt)
    generate_prediction.py … 競馬予想メインスクリプト
  article/
    topics.py             … 羅針盤ノートの文体・お題定義
    generate_article.py   … 記事生成メインスクリプト
requirements.txt
```
