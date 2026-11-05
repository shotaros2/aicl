# 家のパソコン（RTX 3070）へ夜間作業を移す手順

最終更新: 2026-11-05。いまはノートパソコン（Core i5-1235U、内蔵 GPU）で動いている夜間作業と Discord 連携を、
家の Windows パソコン（i7-13700KF、メモリ 16 GB、RTX 3070 8 GB、ディスク 1 TB、ホスト名 SHOTARO）に移し、手元の AI（Ollama）と組み合わせるための手順です。
人と AI エージェント（Claude Code など）の両方が読む前提で書いています。

## 0. 移したあとの姿

- 家のパソコンが夜中もついていて、毎晩 2 時の夜間作業と 30 分ごとの受付確認を行う。
- あなたはスマホの Discord で `#タスク` に書き、`#報告` で結果を受け取る。どのパソコンが動いているかは気にしなくてよい。
- 考える AI は、手元の AI（Ollama、GPU で動く）と Gemini の無料枠を組み合わせる。Gemini が使えないときは手元の AI が代わり、
  手元の AI が困ったとき（無効な返答 2 回、差し戻し 2 回、遅すぎ、停止）はその役だけクラウドに上がる。
  **この切り替えのコードは作成済み**（2026-11-06、`aicl/local.py`、`vendors.with_escalation`）。使い方は §6。

## 1. 家のパソコンに入れるもの

1. **Python 3.11 以上**（https://www.python.org/ 。インストール時に「Add python.exe to PATH」にチェック）
2. **Git**（https://git-scm.com/ ）
3. **Ollama**（https://ollama.com/ の Windows 版）。入れたら PowerShell で:

```powershell
ollama pull qwen3:8b
```

   約 5 GB。3070 の 8 GB に収まる大きさ。そのときの最新の 7〜8B 級のおすすめに替えてもよい。動作確認:

```powershell
ollama run qwen3:8b "こんにちは"
```

4. **Claude のデスクトップアプリ**（このリポジトリで Claude Code と作業を続けるため）
5. **Node.js**（https://nodejs.org/ の LTS 版）。アプリ作りのテスター（`@tester`）が JavaScript の文法を確かめるのに使う。
   無くても動くが、そのときは報告書に「文法は未検査」と出る。

## 2. リポジトリを取ってくる

**OneDrive の外**に置く（`.git` の大量のファイルで同期の不具合が起きたことがあるため。HANDOFF.md §6）。

```powershell
git clone https://github.com/shotaros2/aicl.git C:\dev\aicl
```

```powershell
cd C:\dev\aicl
python -m pip install -e ".[crypto,llm,mcp]"
```

```powershell
python -m unittest discover -s tests
```

最後の行が `OK` なら準備完了。続けてコミットの作者を設定する（メールアドレスを公開しないため）:

```powershell
git config user.name shotaros2
git config user.email 329199865+shotaros2@users.noreply.github.com
```

## 3. 秘密の設定（.env）を写す

- ノートの `C:\Users\showk\OneDrive\AI言語\.env` を **USB メモリなど** で家のパソコンの `C:\dev\aicl\.env` に写す。
  **メールやチャット、GitHub には絶対に載せない**（Gemini・Claude のキー、Discord のトークンとウェブフックが入っている）。
- 中身はそのままでよい。Discord の設定（ボット、チャンネル、ウェブフック、あなたのユーザー ID）も同じものを使う。

確認（トークンなどは表示されない）:

```powershell
python -m aicl.discordlink check
```

すべて `ok` なら Discord もつながっている。

## 4. チームの記憶を写す（任意）

`out\` は GitHub に入らないので、夜間作業の記憶と過去の報告は手で写す:

- `out\night\memory.jsonl`（スカウトが「前にやったこと」を思い出すための記憶）
- 必要なら `out\night\` の日付フォルダ（過去の報告）

写さなくても動く。記憶が空から始まるだけ。

## 5. 1 台だけが動くように切り替える（大事）

**両方のパソコンで夜間作業を登録すると、Discord の同じタスクを 2 台がそれぞれ処理してしまう。** 次の順で切り替える。

1. Discord の `#タスク` に未処理の書き込みがないときに行う（受付の開始点はパソコンごとに別々に覚えている）。
2. **ノートで登録を解除**:

```powershell
powershell -ExecutionPolicy Bypass -File "C:\Users\showk\OneDrive\AI言語\tools\install_night_shift.ps1" -Remove
```

3. **家のパソコンで登録**:

```powershell
powershell -ExecutionPolicy Bypass -File C:\dev\aicl\tools\install_night_shift.ps1
```

4. 家のパソコンで 1 回、手で受付確認を動かしておく（Discord の受付の開始点がここで決まる）:

```powershell
python -X utf8 examples\night_shift.py --mode inbox
```

5. 家のパソコンの電源設定: スリープしてもよいが、シャットダウンはしない。「スリープ解除タイマーの許可」を有効にする
   （コントロールパネル → 電源オプション → プラン設定の変更 → 詳細な電源設定の変更 → スリープ）。

## 6. 手元の AI を使う

組み込みのコードは作成済み。家のパソコンでは次の 2 つで確かめる。

1. 受け入れテスト（例 18 と同じ採点。作法を守れるかのチェック表が出る）:

```powershell
python -X utf8 examples\local_acceptance.py
```

2. 夜間作業を手元の AI で（チーフ・ライター・スカウト＝手元、チェッカー・コーダー・挿絵＝Gemini）:

```powershell
python -X utf8 examples\night_shift.py --mode inbox --preset local
```

   報告書に「手元の AI からクラウドに上げた回数」が出る（料金の目安）。うまく回ったら、§5 の登録を
   `-Preset local` 付きでやり直す（同じ名前の予定が上書きされる）:

```powershell
powershell -ExecutionPolicy Bypass -File C:\dev\aicl\tools\install_night_shift.ps1 -Preset local
```

   登録スクリプトは PATH にある Microsoft Store の「python」（実行しても何もしないダミー）を自動で避け、
   `%LOCALAPPDATA%\Programs\Python\Python3*` の本物を使う。表示される `python:` の行で確かめる。
   別のモデルを試すときは `.env` に `AICL_LOCAL_MODEL=llama3.1:8b` のように書く（先に `ollama pull`）。

3. **家のパソコンの本番の設定は `--preset home`**（2026-11-05 の実地テストで決定）: チーフ・ライター・チェッカー・
   コーダー＝Claude Haiku（有料・安価）、スカウト＝手元の AI、挿絵＝Gemini。RTX 3070 の qwen3.5:9b ではチーフと
   ライターが務まらなかった（HANDOFF §6）。登録は:

```powershell
powershell -ExecutionPolicy Bypass -File C:\dev\aicl\tools\install_night_shift.ps1 -Preset home -LocalModel qwen3.5:9b
```

## 7. どのフォルダでも AICL を使う設定（任意）

ノートで行った設定を家でも行う場合（HANDOFF.md §5 の最後）:

1. `C:\dev\aicl\rulebook\skill\aicl\` を `%USERPROFILE%\.claude\skills\aicl\` にコピー
2. MCP サーバーの共通登録はノートでは解除した。必要になったら Claude に頼む。

## 8. 移行が終わったかの確認

- [ ] `python -m unittest discover -s tests` が `OK`
- [ ] `python -m aicl.discordlink check` がすべて `ok`
- [ ] `Get-ScheduledTask -TaskName "AICL*"` で 2 つの予定が家のパソコンにだけある
- [ ] ノートの予定は解除済み
- [ ] スマホから `#タスク` に書くと 30 分以内に 📥 が付き、`#報告` に結果が届く
- [ ] `#タスク` に「〇〇のアプリを作って」と書くと、`#報告` に `.html` が届き、スマホのブラウザで開ける
- [ ] `node --version` が表示される（テスターの文法検査に必要）
