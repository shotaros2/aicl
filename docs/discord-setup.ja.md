# AICL チームを Discord につなぐ手順

AI のチームに Discord のアカウント（ボット）を持たせます。つないだあとは、

- `#タスク` に日本語で書くと、それがチームの仕事になります（あなたの書き込みだけ。他の人やボットの書き込みは無視します）。
- `#aicl-会話` に、AI たちのやり取りが、それぞれの名前で流れます。
- `#報告` に、朝の報告書と、できあがったページがファイルで届きます。

考える部分（Gemini や Claude）と、署名・検証は、これまでどおり PC の中で動きます。Discord はチームの部屋と郵便受けです。

> トークンとウェブフックの URL はパスワードと同じです。`.env` にだけ書き、チャットや画面共有には出さないでください。

## 1. 自分専用のサーバーとチャンネルを作る

1. Discord で「サーバーを追加」→「オリジナルの作成」→「自分と友達のため」。名前は何でもかまいません（例: `AICL チーム`）。
2. テキストチャンネルを 3 つ作ります: `タスク`、`aicl-会話`、`報告`。

## 2. 家のボット（受付と報告の係）を作る

1. ブラウザで https://discord.com/developers/applications を開き、「New Application」→ 名前 `AICL` → 作成。
2. 左の「Bot」→「Reset Token」→ 表示されたトークンをコピーし、`.env` に書きます:
   `DISCORD_BOT_TOKEN=（コピーしたもの）`
3. 同じ「Bot」の画面で **MESSAGE CONTENT INTENT** をオンにして保存します（これがないと、あなたの書き込みが空で届きます）。
4. 左の「OAuth2」→「URL Generator」→ SCOPES で `bot` にチェック → BOT PERMISSIONS で
   `View Channels`、`Send Messages`、`Read Message History`、`Attach Files`、`Add Reactions` にチェック。
   一番下の URL を開き、1. のサーバーを選んで「認証」。

## 3. ID を調べて `.env` に書く

1. Discord の「ユーザー設定」→「詳細設定」→「開発者モード」をオン。
2. `タスク` チャンネルを右クリック →「チャンネル ID をコピー」→ `DISCORD_TASKS_CHANNEL=…`
3. `報告` チャンネルを右クリック →「チャンネル ID をコピー」→ `DISCORD_REPORTS_CHANNEL=…`
4. 自分の名前を右クリック →「ユーザー ID をコピー」→ `DISCORD_OWNER_ID=…`

## 4. AI たちが話すチャンネルのウェブフックを作る

1. `aicl-会話` チャンネルの歯車 →「連携サービス」→「ウェブフック」→「新しいウェブフック」→「ウェブフック URL をコピー」。
2. `.env` に書きます: `DISCORD_WIRE_WEBHOOK=…`

これで、各 AI が `@chief`、`@critic` などの名前で書き込みます。

## 5.（任意）AI ごとに本物のボットアカウントを持たせる

チーフなどに「自分のアカウント」を持たせたいときは、2. と同じ手順で別のアプリ（例: `chief`）を作り、同じサーバーに招待します。

- `.env` に `DISCORD_TOKEN_CHIEF=（chief のトークン）` を書きます。ライターなら `DISCORD_TOKEN_WRITER`、チェッカーは `DISCORD_TOKEN_CRITIC`、スカウトは `DISCORD_TOKEN_SCOUT`。
- `aicl-会話` チャンネルの ID も書きます: `DISCORD_WIRE_CHANNEL=…`

トークンを書いた AI は自分のボットで、書いていない AI はウェブフックの名前で話します。

## 6. つながったか確かめる

PowerShell で:

```powershell
cd "C:\Users\showk\OneDrive\AI言語"
python -m aicl.discordlink check
python -m aicl.discordlink hello
```

`check` はトークンなどを表示せずに、何がつながったかだけを並べます。`hello` は `#報告` にあいさつを、`#aicl-会話` に各 AI の名乗りを書き込みます。

## 使い方

- `#タスク` に、たとえば「明日の東京の天気と、傘が要るかをまとめて」と書きます。受け付けると 📥 の印が付きます。
- 30 分ごとの確認（`tools/install_night_shift.ps1` で登録）か、毎晩 2 時の夜間作業で処理され、結果が `#報告` に届きます。
- 止めたいときは `.env` の `DISCORD_` の行を消すか、`python examples/night_shift.py --no-discord` で動かします。
