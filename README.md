# Discord Task Bot

指定チャンネルに常駐して、
- 毎朝(デフォルト6:00 JST)にタスク一覧を通知
- `/task add` `/task remove` `/task list` でタスク管理
- そのチャンネルでの発言に、設定した口調でGeminiが雑談で返信

する Bot です。

## 構成

```
discord-task-bot/
├── bot.py            # 本体(コマンド登録・スケジューラ・雑談ハンドラ)
├── config.py         # .envの読み込み
├── tasks_db.py        # タスクのSQLite永続化
├── gemini_client.py   # Gemini API呼び出し(REST直叩き)
├── requirements.txt
├── .env.example
└── discord-task-bot.service  # systemdユニット
```

## 1. Discord Bot の準備

1. https://discord.com/developers/applications で New Application
2. 左メニュー Bot → Reset Token でトークンを取得(`.env` の `DISCORD_TOKEN`)
3. 同じ Bot ページで **Privileged Gateway Intents** の `MESSAGE CONTENT INTENT` をON
   (雑談機能はメッセージ本文が読めないと動きません)
4. OAuth2 → URL Generator で scope に `bot` と `applications.commands` をチェック、
   Bot Permissions は `Send Messages` `Read Message History` があればOK
5. 生成されたURLを開いて自分のサーバーに招待

チャンネルIDの取得: Discordの設定 → 詳細設定 → 開発者モードON → 対象チャンネルを右クリック → 「IDをコピー」

## 2. Gemini API キーの準備

https://aistudio.google.com/apikey でAPIキーを発行 (`.env` の `GEMINI_API_KEY`)。

料金は `gemini-2.5-flash-lite` が現行モデルで最安クラス(input $0.10 / output $0.40 per 100万トークン)で、
無料枠も用意されています。1日1回の通知+ちょっとした雑談程度なら、無料枠内に収まる可能性が高いです。
ただし2026年に入ってGoogleは無料枠の仕様変更を続けているので、AI Studio上で自分のプロジェクトの
実際のクォータを確認しておくと安心です。もう少し賢さが欲しければ `gemini-2.5-flash` に変更してください
(`.env` の `GEMINI_MODEL`)。

## 3. ローカルでの動作確認

```bash
cd discord-task-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env を編集してトークン・APIキー・チャンネルIDなどを埋める

python bot.py
```

サーバーで `/task add` などのスラッシュコマンドが出てくれば成功です。

## 4. EC2への常駐デプロイ

EC2は触ったことがあるとのことなので手順は簡単に:

```bash
# EC2上で
sudo apt update && sudo apt install -y python3-venv git
git clone <このプロジェクトのリポジトリ>  # またはscp等で転送
cd discord-task-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env  # 値を埋める

# 動作確認
python bot.py   # Ctrl+Cで停止
```

systemdに登録して常駐化:

```bash
sudo cp discord-task-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/discord-task-bot.service
# WorkingDirectory / ExecStart / User をご自身の環境のパス・ユーザー名に合わせて修正

sudo systemctl daemon-reload
sudo systemctl enable discord-task-bot
sudo systemctl start discord-task-bot

# 状態確認
sudo systemctl status discord-task-bot
journalctl -u discord-task-bot -f   # ログをtail
```

これでEC2再起動後も自動起動し、クラッシュ時も `Restart=on-failure` で自動復帰します。

## カスタマイズポイント

- **口調・キャラ**: `.env` の `PERSONA_PROMPT` を書き換えるだけ。日本語のキャラ設定をそのまま書けます。
- **通知時刻**: `.env` の `NOTIFY_HOUR` / `NOTIFY_MINUTE`(タイムゾーンはJST固定でbot.py内に書いています)。
- **雑談の履歴の長さ**: `config.py` の `CHAT_HISTORY_TURNS`。長くするとGeminiに送るトークン数が増え、
  わずかにコストが上がります。
- **タスクDBの場所**: `.env` の `DB_PATH`(未指定なら `tasks.db` がbot.pyと同じディレクトリに作られます)。

## 設計上の注意点

- チャット履歴はメモリ上に保持しているだけなので、Bot再起動で会話の文脈はリセットされます
  (タスクデータ自体はSQLiteに永続化されているので消えません)。
- Gemini APIはSDKではなくREST APIを`requests`で直接呼んでいます。SDKのバージョン互換性に
  振り回されにくく、リクエスト/レスポンスの中身が見えるので、挙動を変えたい時にいじりやすいはずです。
