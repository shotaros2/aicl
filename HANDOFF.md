# 引き継ぎメモ（別の PC で作業を続けるために）

最終更新: 2026-11-04。このファイルは人間と AI エージェント（Claude Code など）の両方が読む前提で書いています。

## 1. これは何か

**AICL（AI Common Language）**: AI エージェント同士が自然言語の代わりに使う、曖昧さのない形式言語。
仕様（`SPEC.md`）、Python の参照実装（`aicl/`）、検証器、協調レイヤー、Claude 用の MCP ゲートウェイ、
配布用ルールブックまで一式がこのリポジトリにあります。概要と実測値は `README.ja.md`、変更履歴は `CHANGELOG.md`。

## 2. 公開場所とアカウント

| 何 | どこ | 備考 |
|---|---|---|
| ソース | https://github.com/shotaros2/aicl | GitHub アカウント `shotaros2`（本人）。コミットの作者は匿名アドレス `329199865+shotaros2@users.noreply.github.com` に統一済み |
| パッケージ | https://pypi.org/project/aicl-lang/ | 0.1.0 と 0.2.0 を公開済み。`pip install aicl-lang` |
| リリース | GitHub Releases v0.1.0, v0.2.0 | wheel と sdist を添付 |
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
| 新版の公開 | `pyproject.toml` と `aicl/__init__.py` の version を上げ、CHANGELOG を書き、`python -m build`、タグを付けて push、`gh release create`、`run_pypi_upload.cmd` |

## 5. 他の AI に渡すもの

- チャットアプリに貼る 1 ファイル: `rulebook/aicl-rulebook-bundle.md`
- スキルとして取り込めるアプリ（Dola、Claude）: `rulebook/aicl-skill.zip`
- Gemini アプリの Gem「AICL」: 指示欄に `rulebook/aicl-rulebook-dense.md` の `---` 以降を貼り、`me` を `gemini` に置換（作成済みだが Google アカウントに紐づくので新 PC からは同じアカウントでログイン）
- Dola のスキル「aicl」: ZIP をアップロード済み（Dola のアカウントに紐づく）

## 6. ここまでで分かっていること（要点）

- 可読形式は英語より約 3 割トークンが多い。密形式で同等、コードブックで同等〜わずかに下。数字は README の表。
- 言語の作法（ID、返信参照、束縛マップ、未知語への `clar`）は Gemini Flash/Pro、Claude、Dola が守れた。
- 言語は「形式と手続き」を保証し「事実」は保証しない。Gemini は値を作り、根拠を捏造した。
  → 0.2 で `retract`、`status`、根拠の必須化（`:src` は構造か `(none)`）、半開区間、`def` の有効範囲を追加。
- 実記録: `examples/07`（Claude と Gemini の交渉）、`examples/09`（Dola が本物の画像を AICL で納品）。
- Dola は外部から呼ぶ API がなく、カスタムコネクタも未解放。自動化は Gemini 経由のゲートウェイで、Dola は人の中継で使う。

## 7. 次にやる候補

1. API 課金を有効にして `AICL_IMAGE_MODEL=gemini-nano-banana-2.1` で本物の画像を MCP 経由で Claude に返す（`.env` に 1 行追加するだけ）。
2. `examples/cooperation_gemini.py` を `aicl/gemini.py` を使う形に整理（今は同じコードが二重にある）。
3. SPEC §13 の残課題: 期限の検証可能性（`ok` に `:at` を必須にするか）、領域ごとの標準コードブック、`def` の型付き署名。
4. 読み戻し評価を `gemini-3.7-flash` など標準モデルでも取り、README の表を更新（無料枠は日本時間の夕方にリセット）。
5. 告知: X に投稿済み（文面は会話履歴参照）。Zenn / Show HN 向けの記事は未着手。

## 8. Claude Code と作業するときの約束

- `AGENTS.md` と `CLAUDE.md` にエージェント向けの作業規則があり、Claude Code は自動で読む。
- 変更がテストを通ったら確認なしでコミットしてよい。push、リモート追加、公開リポジトリの作成、PyPI へのアップロードは本人が自分のターミナルで行う（Claude の環境は別アカウントで、かつ安全設定で止まる）。
- `README.md` と `README.ja.md` は同じ内容を保つ。トークン削減を誇張しない（表は実測）。
