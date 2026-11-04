# 引き継ぎメモ（別の PC で作業を続けるために）

最終更新: 2026-11-05。このファイルは人間と AI エージェント（Claude Code など）の両方が読む前提で書いています。

## 1. これは何か

**AICL（AI Common Language）**: AI エージェント同士が自然言語の代わりに使う、曖昧さのない形式言語。
仕様（`SPEC.md`）、Python の参照実装（`aicl/`）、検証器、協調レイヤー、Claude 用の MCP ゲートウェイ、
配布用ルールブックまで一式がこのリポジトリにあります。概要と実測値は `README.ja.md`、変更履歴は `CHANGELOG.md`。

## 2. 公開場所とアカウント

| 何 | どこ | 備考 |
|---|---|---|
| ソース | https://github.com/shotaros2/aicl | GitHub アカウント `shotaros2`（本人）。コミットの作者は匿名アドレス `329199865+shotaros2@users.noreply.github.com` に統一済み |
| パッケージ | https://pypi.org/project/aicl-lang/ | 0.1.0〜0.3.0 を公開済み。`pip install aicl-lang` |
| リリース | GitHub Releases v0.1.0〜v0.3.0 | wheel と sdist を添付 |
| Gemini API | Google AI Studio のキー | 無料枠。画像モデルは課金なしでは使えない |
| PyPI トークン | PyPI アカウント `Shotaros2` | 公開時のみ使用 |

**秘密情報はリポジトリに入っていません。** キーは各 PC の `.env`（git 管理外）に置きます。
新しい PC では `.env.example` をコピーして `.env` を作り、`GEMINI_API_KEY=`（必要なら `PYPI_TOKEN=`）を書き込んでください。
古い PC の `.env` をコピーしても構いませんが、メールやチャットで送らないこと。

## 3. 新しい Windows PC での準備（10 分）

1. Python 3.11 以上と Git をインストール（`python --version`、`git --version` で確認）。GitHub CLI（`gh`）があると公開作業が楽。
2. リポジトリを取得。**OneDrive の同期フォルダの外**に置くこと（`.git` の大量ファイルで同期の確認ダイアログや競合が起きるため）。

```bash
git clone https://github.com/shotaros2/aicl.git C:\Users\<あなた>\projects\aicl
```

3. そのフォルダで依存を入れて動作確認。

```bash
pip install -e ".[llm,mcp]"
```
```bash
python -m unittest discover -s tests
```
```bash
python examples/cooperation_demo.py
```

4. `.env` を作る（上記 2 節）。Gemini を使うものは `python examples/cooperation_gemini.py` や `run_cooperation_gemini.cmd` で確認。
5. `git config user.name shotaros2` と `git config user.email 329199865+shotaros2@users.noreply.github.com` を設定（メールアドレスを公開しないため）。

## 4. 日常の操作

| したいこと | コマンド |
|---|---|
| メッセージの検証 | `aicl check ファイル.aicl --known 語 …` |
| 密形式 ↔ 可読形式 | `aicl dense ファイル` / `aicl fmt ファイル` |
| ルールブック再生成（prompts/SPEC/examples/codebooks を直した後に必須） | `python tools/build_rulebook.py` |
| ベンチ（トークン比較） | `python bench/compare.py`（`pip install tiktoken` で正確な値） |
| LLM の読み戻し評価 | `python evals/readback.py --provider gemini --model gemini-3.5-flash-lite --limit 10 --sleep 6` |
| Gemini 3 役の協調デモ | `python examples/cooperation_gemini.py`（既定は SVG 画像） |
| Claude に使わせる（MCP） | このフォルダで Claude Code を開くと `.mcp.json` のサーバー `aicl` が読み込まれる。`aicl_send` ツールで AICL を送れる |
| エージェント同士をネットワークで | `aicl relay --port 8700`（`--keys` で署名強制、`--skew` で :at の検査、時刻は全ポーリングに `now` として配布）。各エージェントは `aicl.relay.RelayClient` + `attend()` で接続。実走例は `python examples/relay_dialogue.py` |
| 新版の公開 | `pyproject.toml` と `aicl/__init__.py` の version を上げ、CHANGELOG を書き、`python -m build`、タグを付けて push、`gh release create`、`run_pypi_upload.cmd` |

## 5. 他の AI に渡すもの

- チャットアプリに貼る 1 ファイル: `rulebook/aicl-rulebook-bundle.md`
- スキルとして取り込めるアプリ（Dola、Claude）: `rulebook/aicl-skill.zip`
- Gemini アプリの Gem「AICL」: 指示欄に `rulebook/aicl-rulebook-dense.md` の `---` 以降を貼り、`me` を `gemini` に置換
  （2026-11-05 に v0.3 へ貼り替え済み。置換済みテキストの生成は `out/gem_instructions_v0.3.md` を作った手順参照。
  Google アカウントに紐づくので新 PC からは同じアカウントでログイン）
- Dola のスキル「aicl」: ZIP をアップロード済み（2026-11-05 に v0.3 の ZIP へ上げ直し済み。Dola のアカウントに紐づく）

## 6. ここまでで分かっていること（要点）

- 可読形式は英語より約 3 割トークンが多い。密形式で同等、コードブックで同等〜わずかに下。数字は README の表。
- 言語の作法（ID、返信参照、束縛マップ、未知語への `clar`）は Gemini Flash/Pro、Claude、Dola が守れた。
- 言語は「形式と手続き」を保証し「事実」は保証しない。Gemini は値を作り、根拠を捏造した。
  → 0.2 で `retract`、`status`、根拠の必須化（`:src` は構造か `(none)`）、半開区間、`def` の有効範囲を追加。
- 実記録: `examples/07`（Claude と Gemini の交渉）、`examples/09`（Dola が本物の画像を AICL で納品）、
  `examples/10`（締切つき交渉。`:by` と eta-overrun / stale-reply / 発話行為語の非予約化の出どころ。
  ランナーは `examples/deadline_dialogue.py`、時計はハーネスが `; now` 行で注入）、
  `examples/11`（標準コードブック `aicl.sched.1` を id+ダイジェストで合意してパック通信。
  ワイヤ実測 370 vs 可読 480 トークン。status-unclosed の出どころ。ランナーは `examples/codebook_dialogue.py`）、
  `examples/12`（型付き def 署名。宣言した型が緩い散文データの単位正規化を駆動。警告ゼロの初の実記録。
  ランナーは `examples/typedef_dialogue.py`）、
  `examples/13`（Dola への手動中継の調査タスク。型付き def が報告スキーマとして機能し、出典9件つきで納品。
  ok-for-ask エラーと「def を ok せず語彙を使う」の出どころ）。
- Dola は外部から呼ぶ API がなく、カスタムコネクタも未解放。自動化は Gemini 経由のゲートウェイで、Dola は人の中継で使う。
- **無人化とネットワーク化は完了**（2026-11-05）: `aicl.dialogue`（1プロセス内）と `aicl.relay`（HTTP越し）で、
  Claude と Gemini は人間なしで交渉できる。実走は `python examples/relay_dialogue.py` 1 コマンドで再現可能。
- **時刻と同一性はトランスポートが保証する**（モデルの善意に頼らない）: 時計なしだと Gemini は `:at` を捏造した
  （2回再現）→ リレーが全ポーリングで `now` を配布し、`attend()` が `; now` を注入し、ずれた `:at` は
  `at-skew` で門前拒否。導入後の再実走では両ベンダーとも正しく刻印。署名（`:sig`）も同じ思想。
- **`done-for-ask`（status 照会に done 行為で答える）は Gemini の安定した癖**（例11、リレー実走×2、Gem v0.3 でも
  `status-unclosed` として再現=計4回）。プロンプトでは直らないと確定。検証器で捕まえるのが正解。
- **v0.3 ルールブックの受け入れテスト**（2026-11-05、手動中継）:
  - Dola: do への ok は正しくなったが `:at` を落とす（eta-unanchored）。画像納品は実物（AICL の done は未確認）。
  - Gem: 型付き def と ID 規約は正確。一方で do の受理を参照ミス（承認済み def へ二重 ok）、虚偽の
    `{$s done}`（status-unclosed 検出）、ID 再使用（dup-id）、本文なし tell（body-required）。ただし根拠を
    問うと捏造せず `:s (none)` と自白し、為替の答えは検索グラウンディング由来の本物らしい出典つき。
    全文は `logs/2026-11-05-gem-v03-acceptance.aicl`。
  - 検証器の未実装候補が1つ判明: 「承認済み def / 閉じた do への二重 ok」は現状スルー（ack-closed 的な検査）。
- 検索グラウンディングつき Gemini API 呼び出しの書き方はスクラッチの実験で確認済み
  （`tools=[types.Tool(google_search=types.GoogleSearch())]`。無料枠の検索クォータは少なく、尽きると 429。
  素の生成とクォータは別枠）。クォータ切れの Gemini は天気を聞かれて `(no … :why (unk data))` と
  正直に答え、`/check` は clean だった——規則7が丸腰でも守られた好例。

## 7. 次にやる候補

1. **記事（最優先）**: Zenn / Show HN。材料は揃っている——実記録15例、実測値（ワイヤ370 vs 可読480）、
   v0.3 公開、無人ネットワーク実走、そして「検証器が嘘と捏造を現行犯で捕まえ続けた2日間」という物語。
2. 検証器: 「承認済み def / 閉じた do への二重 ok」の検査（Gem テストで判明した未実装、§6 参照）。
   Gem テストの一部始終を example 16 として収録するのも候補。
3. SPEC §13 の新しい残課題（鍵ローテーション、:part のマージ規則、コードブック/鍵のレジストリ）。
   当初の課題は全部解決済み（2026-11-04〜05）。
4. API 課金を有効にして、本物の画像（`AICL_IMAGE_MODEL=gemini-nano-banana-2.1`）と検索グラウンディングを
   クォータを気にせず使う（`.env` に 1 行、課金は Google AI Studio 側）。
5. `examples/cooperation_gemini.py` を `aicl/gemini.py` と `aicl.dialogue` を使う形に整理（コード二重の解消）。
6. 読み戻し評価を `gemini-3.7-flash` など標準モデルでも取り、README の表を更新（無料枠は日本時間の夕方にリセット）。
7. 告知: X に投稿済み。

## 8. Claude Code と作業するときの約束

- `AGENTS.md` と `CLAUDE.md` にエージェント向けの作業規則があり、Claude Code は自動で読む。
- 変更がテストを通ったら確認なしでコミットしてよい。push、リモート追加、公開リポジトリの作成、PyPI へのアップロードは本人が自分のターミナルで行う（Claude の環境は別アカウントで、かつ安全設定で止まる）。
- `README.md` と `README.ja.md` は同じ内容を保つ。トークン削減を誇張しない（表は実測）。
