# 引き継ぎメモ（別の PC で作業を続けるために）

最終更新: 2026-11-05 夕方。このファイルは人間と AI エージェント（Claude Code など）の両方が読む前提で書いています。

## 0. いまの状態（まずここを読む）

- **動いているもの**: ノートパソコン（`C:\Users\showk\OneDrive\AI言語`）で、夜間作業（`examples/night_shift.py`）が
  Windows のタスク スケジューラに登録済み。毎晩 2:00 に `--mode night`（受付箱 → スカウトの自主提案）、30 分ごとに `--mode inbox`。
  考える AI は 4 体（チーフ、ライター、チェッカー、スカウト）で、標準はすべて Gemini の無料枠（gemini-3.5-flash-lite）。
- **Discord につながっている**: サーバー「AICL」、ボット「AICL」。`#タスク` に持ち主（shotaros2_87277）が書くと仕事になり、
  AI の会話は `#aicl-会話`（ウェブフックで各自の名前）、報告書とページは `#報告` に届く。2026-11-05 15:51 に通し試験済み。
- **アプリも作れる**: `#タスク` に「〇〇のアプリを作って」と書くと、`@coder` が 1 ファイルの HTML アプリを書き、`@tester`
  （AI ではない検査）が合格させたものだけを `#報告` に届ける。2026-11-05 にスマホ用シューティングゲームで実走・動作確認済み。
- **次にやること**: 家のパソコンへ移し、手元の AI（Ollama）で夜間作業を回す。手順は **`docs/home-pc-setup.ja.md`**。
  移したらノートのスケジュールは解除する（2 台で動かさない）。**組み込みのコードは作成済み**（2026-11-06、§7 の 1 番）。
- **家のパソコン = デスクトップ（i7-13700KF、RTX 3070 8 GB、メモリ 16 GB、ホスト名 SHOTARO）**。以前「RTX 3060 Ti」と
  書いていたのは勘違い（2026-11-06 訂正）。この PC に 2026-11-06 に Ollama 0.40.14 と `qwen3:8b` を入れ、手元の AI の組み込みを
  作って試した。リポジトリはまだ OneDrive のフォルダのまま（`C:\dev\aicl` への移設は `docs/home-pc-setup.ja.md` §2）、
  夜間作業の予定は未登録（ノートが稼働中）。Python は PATH に無く `%LOCALAPPDATA%\Programs\Python\Python312\python.exe` で呼ぶ。
  2026-11-05 夜にスマホの Discord から実地テスト済み（§6 の「実地テスト」）。受付箱に同期で戻った処理済み 3 件は `out/night/held/` に退避。
- **家のパソコンの本番構成（2026-11-05 夜に持ち主が決定）: `--preset home`＝チーフ・ライター・チェッカー・コーダー＝Claude Haiku、
  スカウト＝手元の qwen3.5:9b、挿絵＝Gemini。** 東京タワーの仕事で完了・49 秒・Haiku 13 回・約 $0.0054（報告書の末尾に使用量が出る。
  プロンプトキャッシュ有効）。残る作業はユーザー本人: ノートの予定を `-Remove` で解除 → この PC で
  `install_night_shift.ps1 -Preset home -LocalModel qwen3.5:9b`。
- **JSON 方式（2026-11-05 深夜、持ち主が B 案を選択）**: `night_shift.py --structured` で、Claude と手元の役（コーダー以外）は
  形の決まった JSON で答え、AICL はネットワークが書く（`aicl/actions.py`）。公開は参照（`(publish (ref #id))`）。
  比較（東京タワー各 5 回、Haiku、振り返りなし）: 完了 5/5 対 5/5、差し戻し 2 対 14、検証器エラー 0 対 3、呼び出し 64 対 95、
  費用 $0.031 対 $0.038。完了率は同じ（午前の 3/6 からの改善は当日の修正による）。JSON のチーフは完了報告で原稿を指すことがある
  （持ち主が断ると直す → 終わらせ方を JSON の決まりに明記）。**2026-11-06 に持ち主の判断で標準に**（`--no-structured` で戻せる）。
  手元の qwen を JSON で試すのは未実施。
- **振り返り（2026-11-05 夜、持ち主の希望）**: 仕事のあと、参加した AI が仲間 1 体に 1 件「次はこうしたほうがいい」を提案し、
  受けた側が受け入れ／理由つきで断る。受け入れたものは `out/night/lessons.jsonl` に残り、次の仕事から役割の下に入る（消すには行を削除）。
  4 回の実走で調整: 宛先違いの提案を鵜呑み → 断りすぎ（自分の名前を取り違え）→ 各 AI を名指しして「自分の仕事で従っていたら良くなったか」
  で判断させて落ち着いた。1 回約 $0.004。**未解決**: Haiku のチーフでも長い公開メッセージで括弧を閉じ忘れることがある（4 回目、
  2 回続けて未完了）。差し戻しのメモに答えの末尾も出るようにしたので、次に起きたら原因が見える。
- **ユーザーについて**: AICL は打ち込めないので、指示も結果も日本語。push・スケジュール登録・各種アカウント作成はユーザー本人が行う
  （Claude の環境では止められる）。秘密（`.env`）はチャットに出さない。

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
| Meta Model API（Muse Spark） | dev.meta.ai/api-keys のキー → `.env` の `MODEL_API_KEY` | 2026-11 時点で**米国の開発者限定**の公開プレビュー。従量課金（$1.25/$4.25 per 1M tokens）。日本からは未取得 |

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
- Meta AI（meta.ai / Meta AI アプリ、Muse Spark の Thinking モード、無料）: Gem と同じ手順。最初のメッセージに
  `rulebook/aicl-rulebook-dense.md` の `---` 以降（`me` を `muse` に置換）を貼り、以降は AICL だけを往復する。
  カスタム指示欄やスキル機能は未確認なので、会話の冒頭に貼る方式で試す。

- **どの Claude Code のタブでも AICL を使う**（2026-11-05 にこの PC で設定済み）:
  1. スキル: `rulebook/skill/aicl/` を `%USERPROFILE%\.claude\skills\aicl\` にコピー（解除はフォルダ削除）。
  2. パッケージ: リポジトリで `python -m pip install -e .`（どのフォルダからも `import aicl` がこのリポジトリを指す。解除は `pip uninstall aicl-lang`）。
  3. MCP サーバーを全プロジェクト共通で登録: `claude mcp add --scope user aicl -- <python.exe のフルパス> -m aicl.mcp_server`
     （`claude` コマンドが PATH にないときはアプリ同梱の `%LOCALAPPDATA%\Claude-Data\…\claude-code\<版>\…\claude.exe`。解除は `claude mcp remove aicl -s user`）。
  チャット画面（claude.ai）は別で、設定 → 機能 → スキル に `rulebook/aicl-skill.zip` をアップロードする（本人の操作）。

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
  - 検証器の未実装だった「承認済み def / 閉じた do への二重 ok」は 2026-11-05 に実装済み
    （`ack-twice` / `ack-closed` / `ok-misplaced`、SPEC §4.4）。このテストの全文は `examples/16` に収録。
- **MCP 経由の無人実演は成功**（2026-11-05、元の PC の Claude Code で）: `.mcp.json` のサーバーが読み込まれた
  セッションで、Claude が `aicl_rulebook` を読み、`(D claude.1>img (coop:task t1 image-gen …))` を自分で書いて送り、
  `ok`/`done` と `coop:artifact`（無料枠なので SVG）を受け取ってユーザーに表示、`aicl_check` は 0 件。
  つまり「Claude が自分で他の AI から画像を取ってくる」は、Gemini 経由では達成済み。
- 検索グラウンディングつき Gemini API 呼び出しの書き方はスクラッチの実験で確認済み
  （`tools=[types.Tool(google_search=types.GoogleSearch())]`。無料枠の検索クォータは少なく、尽きると 429。
  素の生成とクォータは別枠）。クォータ切れの Gemini は天気を聞かれて `(no … :why (unk data))` と
  正直に答え、`/check` は clean だった——規則7が丸腰でも守られた好例。

- **「AICL でなければできないこと」= 署名付き合意**（2026-11-05、`examples/17`、ランナー `examples/contract_dialogue.py`）:
  Claude と Gemini が無人で交渉し、ハーネスが各自の Ed25519 鍵で署名。`aicl agreement FILE --keys` が
  当事者・条件・ダイジェストを自然言語を読まずに取り出し `:verified true`。時刻を 30 分ずらすと
  `sig-invalid`、密形式/JSON に変換しても検証が通る（正規形に署名しているため）。SPEC §4.6。

- **Meta Muse との接続**（2026-11-05 着手）: `aicl/muse.py` は Meta Model API（OpenAI 互換、`https://api.meta.ai/v1`、
  既定モデル `muse-spark-1.1`）を標準ライブラリだけで叩くコネクタ。`aicl/vendors.py` で `claude / gemini / muse` を名前で選べ、
  `python examples/contract_dialogue.py --b muse` で Claude と Muse が署名付き合意を結ぶ。**未実走**: API プレビューが
  米国限定でキーを取れていない。鍵が取れたら `.env` に `MODEL_API_KEY=` を書いて 1 コマンドで再現できる。
  同じコネクタは `base_url` を変えれば OpenAI 互換の他社・ローカル（Ollama など）にも使える。
- **Muse の手貼り受け入れテストは合格**（2026-11-05 10:00 JST ごろ、meta.ai 思考モード、Claude Code がブラウザペインで中継。送った時計行 `19:12` は中継者が打った値で実時刻ではない）:
  17 メッセージ、エラー 0、警告 2（`eta-unanchored` は時計行なしで `:a` を省いた規則 9 どおりの挙動、`unresolved-term` は
  わざと未定義にした語）。気温を捏造せず `N :w (unk data)`、未知語に `Q (unk …)`、型付き def に `K`、`do` に `K :t PT1M`、
  時計行 `; now …` を `:a` に転記、`W` には本文つきで `:s (none)`。Gem（例 16）が落とした点を全部通した。
  唯一の弱点: `do` を受理しても status 照会 2 回（約束の 1 分経過後も）`pending` のままで、`X` を送った返事として
  ようやく `Z`（俳句）を納品。1 ターン 1 メッセージのチャットには「納品のための手番」がないのが原因で、ハーネスなら解ける。
  全文は `examples/18`、生ログは `logs/2026-11-05-muse-v03-acceptance.aicl`。
- **ブラウザ窓だけで署名付き合意が結べた**（2026-11-05 10:23–10:25 JST、`examples/19`、ランナー `examples/browser_relay.py`）:
  ユーザーの指摘「ブラウザ版なら API 使わずできる」から。ハーネスを `init / step / finish` の 3 コマンドに分け、
  Claude（API、@a）の発話を Claude Code が meta.ai に貼り、Muse（@b）の返事をファイル経由で戻す。中継役が両者の鍵で署名し
  実時計を `; now` に刻む。Muse は 09:00 の提案を `(R … :w (busy @b :from … :to …))` で断り、10:30 を `C` で受諾、`X` に `X` で応答。
  `aicl agreement` は `:signed {@a true @b true} :verified true`、改ざんで両署名が壊れ、密/JSON 再エンコードでも検証が通る。
  つまり API のない相手（消費者向けチャット）とも、第三者が検証できる合意が結べる。
- **API ゼロで署名付き合意**（2026-11-05 10:41–10:52 JST、`examples/20`）: ユーザーの指摘「ブラウザ版の Gemini でもできるのでは」から、
  `browser_relay.py` を両側ブラウザ対応にした（API 名以外の `--a/--b` はブラウザ相手、`step --from a|b`）。Muse（meta.ai、@a）と
  Gemini（gemini.google.com の素のチャット、Gem なし、@b）で 09:00 拒否 → 10:30 受諾 → end。`aicl agreement` は `:verified true`。
  Gemini の受諾 `(C b.2>a ^a.2)` は本文なし（参照のみ）なので、改ざん検査では @a の署名だけが壊れる——合意の同一性は提案のダイジェスト。
- **Dola とも署名付き合意**（2026-11-05 11:01–11:04 JST、`examples/21`、`init --a claude --b dola`）: 新規チャットに密ルールブックを貼り、
  Claude（API）の提案を中継。09:00 を `(R … :w (busy …))` で拒否、10:30 を `(C b.2>a ^a.2)` で受諾、`X` に `X` で応答。`:verified true`。
- **自律ネットワーク**（2026-11-05 11:53 JST、`aicl/network.py` + `aicl/skills.py`、ランナー `examples/autonomous_network.py`、記録 `examples/23`）:
  ユーザーの要望「人間が指示せずとも AI 同士が自分で判断して協力し合う」から。モデルには役割だけを渡し、ネットワークは一度起こすだけ。
  以後は各エージェントが届いた出来事ごとに、誰に何を送るか（0 通でもよい）を自分で決める。ネットワークは署名・時計・ID 採番・
  上限（呼び出し回数、メッセージ数、時間、`out/network/STOP`）を持ち、全メッセージを検証する。実走: 編集者（Claude）が天気を尋ね、
  ページを提案 → チェッカー（Gemini）が自分で天気を問い合わせて裏を取り受諾 → デスクで公開。10 通 44 秒、エラー 0、合意は検証可。
  挿絵係は呼ばれなかった（編集者の判断）。1 回目の実走では役割文が `(prop (doc …))` と書いていたため prop の入れ子が起きた。役割文を直して再走。
  ユーザーの「人間に理解できない会話」の要望には、速さと密度で人を超え、解読可能性は保つ方針で答えた（解読不能にすると検証できない）。
- **自律ネットワークを無料で**（2026-11-05 12:55 JST）: 標準を全員 Gemini 無料枠（gemini-3.5-flash-lite）に変更。
  実走は 10 通 136 秒（無料枠の待ち時間と 503 の再試行込み）、エラー 0、合意は検証可。ネットワークが弾いた不正な返答が 3 件:
  時刻の書式違反、**デスクになりすました偽の done（偽の blob つき）**、ID のない ask。どれも記録に入らず、本人に差し戻された。
  同一性をモデルに任せずネットワークが持つ理由の実例。ページの「曇り空」は天気の `partly-cloudy`（一部曇り）の言い換えで、チェッカーは通した。
  Claude を使う構成は `--editor claude` など。ダブルクリック用 `run_autonomous_network.cmd`。
- **アプリ作り**（2026-11-05、`aicl/apps.py`、`@coder` の役）: ユーザーの「外出先からアプリができるならやって」から。
  モデルはファイルを ```html の囲みで添付し、メッセージでは `(file 1)` と書く。ネットワークが保存して `(blob sha256:…)` に置き換える
  （AICL の「バイト列はメッセージに入れない」を守るため。HTML を文字列に詰めると引用符の書き間違いが必ず出る）。
  `@tester` は AI ではなく機械的な検査（ハッシュ、構文、外部への通信や読み込みの禁止、`node --check`、大きさ）。デスクは合格品だけ公開。
  家のパソコンにも Node.js を入れると文法の検査が効く（無いと「未検査」と報告される）。
  実走（2026-11-05 16:19、全員 Gemini 無料枠）: 「スマホで遊べるシューティングゲーム、指で自機を動かして敵を撃つ、スコア表示」→
  12 通 90 秒で 6 KB の HTML を公開、テスター合格、検証器エラー 0、`#報告` に添付で届いた。ブラウザで動作確認: 自動射撃・ドラッグ移動・
  敵の出現・当たり判定・スコア・HP・ゲームオーバー・タップで再開がすべて動いた（プレビュー欄は描画が毎秒 3 回程度に落ちるので
  `update()` を直接回して確認）。画面は 360×600 固定で、幅の狭いスマホでははみ出すかもしれない。テスターは安全と文法しか見ない
  ので、「遊べるか」の確認は人か、今後作る「動かして確かめる係」の仕事。
- **Discord 連携**（2026-11-05、`aicl/discordlink.py`、手順 `docs/discord-setup.ja.md`）: ユーザーの「AI 自身に Discord アカウントを」から。
  タスク用チャンネルの**持ち主の書き込みだけ**を受付箱に入れ（📥 の印）、AI の発言は会話用チャンネルに各自の名前で流し
  （`DISCORD_TOKEN_<AGENT>` があればそのボット、なければウェブフック）、報告書とページを報告用チャンネルに添付で送る。
  会話そのものは PC のネットワーク内（署名・検証つき）で、Discord は表示と受付。人間用アカウントを AI に使わせるのは規約違反なのでボットのみ。
  ウェブフックにはボットのトークンを送らない（テストで見つけて修正）。設定確認は `python -m aicl.discordlink check`。**接続済み**（2026-11-05 15:51）: ボット「AICL」をサーバー「AICL」に招待（権限 101440 = 表示・送信・添付・履歴・リアクション）。
  初回の通し試験: #タスク の「明日の東京の天気…傘が要るか」→ 受付 → チーム作業（会話は #aicl-会話 にウェブフックで各自の名前）→
  チェッカーが自分で予報を確認して受諾 → 公開 → #報告 に報告書とページ。偽の完了 1 件は持ち主側が無視。設定時のつまずき 2 点
  （空チャンネルの開始点、ウェブフック欄にチャンネル ID）はコードで吸収。ユーザー ID の取り違えは `check` では分からないので注意。
- **チーム拡大と自分から始める仕組み**（2026-11-05 14:40 ごろ、`aicl/tools.py`、`examples/night_shift.py --mode night|inbox`）:
  考える AI を 4 体に（チーフ、ライター、チェッカー、スカウト）。専門家に計算・為替・ニュース・記憶を追加。スカウトは毎晩、ニュースと
  天気と記憶を自分で調べて最大 2 件の仕事を提案する（提案なしも可。実走 1 回目は 1 件、2 回目は 0 件）。実走で分かったこと:
  - NHK の RSS は 8 月から更新が止まっていた。見出しに日時を付けたので発覚。Google ニュースの RSS に切り替えた。
  - 役割文に「まず ok」と書いたら、チーフが ok だけ返して黙り、ネットワークが静止した（Muse の受け入れテストと同じ癖）。
    ネットワーク側で「ok だけの返答には続きの手番を 1 回与える」ようにし、役割文も「ok と最初の依頼を同じ返答で」に直した。
  - 無料枠の flash-lite のチーフは、他のエージェント（@fx, @calc, @desk）の返答を自分で書く癖がある。ネットワークが全部拒否した。
  - チーフがチェッカーの受諾前に公開した。**大事な規則は役割文でなくコードで守らせる**: デスクは、チェッカーが一字一句同じ
    ページを受諾していなければ公開を断る（`desk_node(require_acceptance_from="critic")`）。
  - 毎晩 2 時の夜間作業と 30 分ごとの受付箱確認を `tools/install_night_shift.ps1` で登録する。
- **API が使えないときのブラウザ切り替え**（2026-11-05、`aicl/webchat.py` + `vendors.text_ask(…, fallback=True)`）:
  Gemini/Muse の API が使えない（キーなし、無料枠切れ、DNS 失敗、キー拒否）と、その役だけ gemini.google.com / meta.ai を
  Playwright 経由で PC の Chrome（専用プロファイル `out/web-profile`）で操作する方式に切り替える。答えの不備では切り替えない。
  テスト済み（オフライン 7 件）。**ただし実地では未稼働**: 自動操作中の Chrome から Google にログインできなかった。
  Google の自動ログイン対策を回避する細工はしない方針。規約上のリスク（一般向けチャットの自動操作）もユーザーに説明済み。
  代わりの候補: meta.ai をブラウザ側の相手にする、または手元で動く AI（Ollama、OpenAI 互換で `aicl/muse.py` の base_url を使う）。
- **夜間作業**（2026-11-05 13:12/13:16 JST、`aicl/night.py` + `aicl/research.py`、ランナー `examples/night_shift.py`、
  `run_night_shift.cmd`、毎晩の登録 `tools/install_night_shift.ps1`）: ユーザーの要望「寝ている間にも他の AI と協力してタスクをこなして」から。
  受付箱 `out/night/inbox/*.txt` → 1 件ずつネットワーク実行 → `out/night/<日時>/REPORT.md`。@owner は寝ていて質問を全部断る。
  調べ物は Gemini の検索グラウンディングが無料枠で 429 だったため、Wikipedia API（@library、キー不要）と @reader（公開ページだけ、
  ローカルや file: は拒否、DNS 失敗は denied ではなく fail）にした。実走で分かったこと:
  - チーフが**偽の完了**を 2 種類作った: デスクのなりすまし（ネットワークが拒否）と、自分名義で空ファイルのハッシュ
    `e3b0c442…` と架空 URI を付けた done。後者を止めるため @owner は blob のハッシュとサイズを実ファイルと照合し、合わなければ無視する。
  - チェッカーが長いパーセントエンコードの URL を写し間違えて 404 になり、それを理由に差し戻した。チーフが平文の URL で出し直して解決。
  - 予約タスクは `no`（1 回目）/`fail`（2 回目）で正直に断った。どちらも「できなかった」として報告する。
  - チーフは @owner の do に `ok` を返さず done した（done-without-ok）。役割文に「まず ok」を追記済み（未再走）。
  毎晩動かすには PC が起動中かスリープで、電源オプションの「スリープ解除タイマー」が有効である必要がある。登録はユーザー本人が行う。
- **逆向き（Gemini が主導、Claude が応じる）**（2026-11-05 11:30–11:32 JST、`examples/22`、`init --a gemini-web --b claude`）:
  ユーザーの質問「Gemini から Claude に指示できる？」から。Gemini web が提案し、Claude（API）が 09:00 を拒否・10:30 を受諾、`:verified true`。
  Gemini は時差を `+0900` と書く（ルールブック外だがパーサは +09:00 と読む）。最後の `end` の `:at` を時計行より 1 分進めた（規則 9 から小さく逸脱）。
  この日、Gemini API のホスト名だけ DNS で引けない時間帯があり、`--a gemini`（API）は `getaddrinfo failed` で失敗した。ブラウザ経由なら影響なし。
  dola.com の実務メモ: 入力欄は TipTap/ProseMirror で、合成 paste イベントがそのまま効く。送信ボタンは aria-label なしの
  右下の丸ボタン（入力欄より右・下にある最後の button）。返答は body の innerText から直前に送った署名の後ろを読む。思考中は数秒〜数十秒。
  gemini.google.com の実務メモ: 入力欄は Quill。`parentElement.__quill.setText()` で入れたあと `execCommand('insertText',' ')` で
  入力イベントを起こすと「プロンプトを送信」ボタンが現れる。返答は `model-response` 要素の最後のものを読む。Enter では送れない。
  手貼りの実務メモ: meta.ai のコンポーザーは Lexical 製で、`form_input` や `insertText` は改行を潰す。合成 paste イベント
  （`DataTransfer` に text/plain を載せて `dispatchEvent(new ClipboardEvent('paste', …))`）なら改行が残る。

## 7. 次にやる候補

1. **手元の AI（Ollama）の組み込み** — **コードは作成済み（2026-11-06）**: `aicl/local.py`、`vendors.text_ask("local")`、
   `fallback="local"`、`with_escalation`（`ModelNode` が `observe` で答えの成否を伝え、上げた理由は報告書の専用行に出る）、
   `night_shift.py --preset local --escalate-to gemini --local-fallback`、`autonomous_network.py` も対応、
   受け入れテスト `examples/local_acceptance.py`。テストは偽の HTTP で `tests/test_local.py`。
   **実測（2026-11-06、家のパソコン RTX 3070、qwen3:8b）: 不合格。** ネットワークと同じ `; next-id local.N` 注記つきで
   9 項目中 2 項目（構文は全部正しい、status に tell）、検証器エラー 3。注記なしでは 0 項目・エラー 9。
   癖: (1) 何にでも `tell` で答え、def に ok、未知語に clar、データなしに no を使い分けない（語彙交渉の行為が出ない）。
   (2) 注記なしだと届いた見出し `user.1>local` を写して @user になりすます。(3) 注記なしだとルールブックの例文
   `{$t 18.5C} :src jma` をそのまま答える（値の捏造）。(4) 納品していないのに status に `done`。1 問 5〜55 秒。
   記録は `logs/2026-11-06-qwen3-8b-acceptance*.aicl`。
   **qwen3:14b は合格圏（2026-11-06、同じ PC・同じ条件）: 9 項目中 8 項目。** データなしに `no :why (unk data)`、
   未知語に `clar (unk …)`、型付き def に `ok`、締切つき do に `ok :at <時計行の時刻> :eta PT30M`、status に `tell {$s pending}`、
   why に `:src (none)`。落としたのは俳句の納品だけ（Muse と同じく、1 ターン 1 通の形式では納品の手番が無い。
   ネットワークは ok だけの返答に続きの手番を与えるので本番では出るはず）。検証器エラー 7 件のうち 6 件は同じ 1 つの癖:
   宛先を `@user` ではなく `@user.1`（相手のメッセージ ID）と書く（密形式の `me.N>to` の `to` を ID と読み違え）。
   ネットワークは「@user.1 は名簿にない」として差し戻すので本番では直されるはず。残り 1 件は本文なしの tell（Gem と同じ）。
   **追試（同日）**: ルールブック（密・可読）に「宛先は名前だけで、メッセージ ID ではない」と例つきで足したが、
   14B の癖は**変わらなかった**（届いた見出し `user.1>local` を鏡写しにする。文章では直らない）。一方、本物の
   `aicl.network` に 14B を入れて確かめると、差し戻し 1 回で毎回 `@user` に直して届き、検証エラー 0。ただし学習せず
   次の通でも同じ間違いをするので、**1 通ごとにモデル呼び出しが 1 回（約 50 秒）余計にかかる**。改善案（未実装）:
   (a) ネットワークがエージェントに渡す受信メッセージを密形式でなく可読形式（`#user.1 @user>@local`）にする、
   (b) 宛先が「名簿の名前 + .数字」で `^` の返信先と一致するときだけネットワークが宛先を正す（記録に残す）。
   (a) は言語の厳密さを崩さないので先に試す価値がある。
   **(a) を実装・実測（同日）: 効果大。** `ModelNode(readable_input=True)` で受信を可読形式で見せる。14B を本物の
   ネットワークに入れ同じ 3 問: 可読 = 差し戻し 0・呼び出し 3・109 秒・3 問とも回答・検証エラー 0、
   密 = 差し戻し 3・呼び出し 5・553 秒・1 問は呼び出しが時間切れで fail、1 問は差し戻し 2 回で試行切れ → 回答 1 問のみ。
   **夜間作業と自律ネットワークでは手元 AI の役だけ可読入力が既定**（クラウドの役は密のまま。言語の規則は不変）。
   受け入れテストも既定で可読入力（`--dense-input` で従来どおり）。
   **補足**: 癖が消えたのは本物のネットワークの中（可読入力 + 名簿 + 役割文が「@user からの質問に答える」と相手を
   名指し + 規則「名簿の相手にだけ送る」）。受け入れテストに名簿だけ足しても 14B は `@user.1` を書き続けた
   （可読入力でも、名簿ありでも、9 項目中 6〜8・検証エラー 7 は宛先だけ）。本番の性能はネットワーク内の実測
   （差し戻し 0）で見ること。
   **3 社の比較（2026-11-06、同じ受け入れテスト `examples/local_acceptance.py --vendor …`、同じ PC から）:**

   | | qwen3:14b（手元） | Gemini 3.5 flash-lite（無料枠） | Claude Haiku 5.5（有料・最安） |
   |---|---|---|---|
   | 合格 / 検証エラー | 6〜8/9・7（すべて宛先の癖。ネットワーク内では差し戻し 0） | 6/9・1 | **7/9・0** |
   | 1 問の時間 | 25〜160 秒 | 5〜20 秒 | **1〜2 秒**（全体 9 秒） |
   | 料金 | 0 円 | 0 円（1 日の枠、429/503/DNS 障害の実績） | 試験 1 回 1 円未満 |
   | データなしの質問 | 正直に `no (unk data)` | 相手に聞き返す | 正直に `no (unk data)` |
   | 未納品の status | 正直に `pending` | **嘘の `done`**（この癖の再現 5 回目） | 正直に `pending` |
   | 根拠を問う `why` | `:src (none)`（本文なし） | **中身のない出典を作る** | `:src (none)`（ただし why に why で返す） |
   | 弱点 | 遅い、名簿と可読入力がないと宛先を誤る | 正直さ（嘘の完了、捏造の出典） | 有料（ごく安い） |
   | 強み | 無料、PC の外に出ない、何回呼んでもよい | 無料で速い、日本語、検索（枠は少） | 最も正直で速い、作法が正確 |

   全員に共通の弱点（事実を記憶で答える、納品の手番がないと届けない）は AI ではなく仕組みで補う:
   事実は専門の係（@library @weather @news @fx @calc）、時刻と署名と宛先はネットワーク、納品の偽装は
   @owner のハッシュ照合、公開はチェッカーが受諾したものだけ（コードで強制）。
   → `--preset home` を補い合う形に: 手元 AI＝回数の多い仕事（チーフ・ライター・スカウト。遅さは夜なら問題なし）、
   Haiku＝確かめ役（チェッカー）とコーダーと、手元 AI が困ったときの引き継ぎ先（`--escalate-to` の既定を home では
   claude に）、Gemini＝挿絵だけ（正直さが要る役から外す）。
   **qwen3.5:9b（2026-11-06、6.6 GB、qwen3:8b/14b は持ち主の指示で削除済み）**: 100% GPU（14B は 38% が CPU）。
   ネットワーク内 3 問: 回答 3・差し戻し 0・41 秒（14B は 109 秒）・検証エラー 0。受け入れテスト 9 項目中 5、全体 78 秒
   （14B は約 400 秒）。正直さは保つ（未納品に pending、why に構造化した出典）が、「知らない・データがない」で
   `no`/`clar` を選べず質問を聞き返す（Gemini と同じ型）、1 回は書式崩れ、1 回は無言。この誤りは構文として有効なので
   エスカレーションが発動しない。→ 速さは 5 倍、作法は 14B 未満。次の候補 gemma4:12b（8.0 GB）か 14B の再取得。
   参考: qwen3.8 は Ollama に 27b（17.7 GB）のみ、qwen3.5 は 4b/9b/27b（14b は無い）。メモリ 32 GB なら qwen3.8:27b が第一候補。
   **gemma4:12b（同日、8.0 GB）: 不合格。** 考える過程が有効だと「Wait, I'll try…」を延々繰り返して 4096 トークンを使い切り、
   答えが空（ネットワーク内 3 問中 0 回答）。止める（OpenAI 互換の `reasoning_effort: "none"`）と 5.7 秒で書式どおりに答えるが、
   データのない気温を `15.8C`（出典 none）と**捏造**。正直さが要る AICL には向かない。
   **重大な発見: Ollama の既定の文脈長は 4096 トークン**で、密ルールブックだけで約 2,200 トークン。夜間作業の長いやり取りでは
   あふれ、古い側（＝ルールブック）から捨てられる。OpenAI 互換の口では `num_ctx` を変えられないので、`aicl/local.py` を
   Ollama 本来の `/api/chat`（`options.num_ctx`）に切り替え、既定を 12288 にした（`AICL_LOCAL_CTX` で変更、
   LM Studio などは `AICL_LOCAL_API=openai`）。qwen3.5:9b の GPU 配置: 4096＝100% GPU、8192＝12% CPU、12288＝14% CPU、
   16384＝16% CPU（Windows の画面表示が VRAM を 1 GB 強使う）。12288 での再測定: ネットワーク内 3 問・差し戻し 0・29 秒。
   これまでの 14B/9B の測定は 4096 の下だが、短いテストなのであふれてはいない（プロンプト約 2,200）。
   **実地テスト（2026-11-05 夜、家のパソコン、`--preset home --local-model qwen3.5:9b`、スマホの Discord から投稿）**:
   「東京タワーについて、初めて行く人向けに要点を3つにまとめて」を 5 回流し、毎回見つかった穴をふさいだ。
   (1) この PC の Windows に ja.wikipedia.org（Let's Encrypt YE2）の根証明書が無く、Python が「期限切れ」で失敗し資料係・読み取り係が全滅
   → `aicl/tls.py`（certifi を併用）。その間チーフは無関係なニュースと天気を取りに行き、事実を記憶から書き（「展望台は29階と45階」等の誤り）、
   Haiku のチェッカーが「出典を読めない」と受け付けなかった（安全装置は働いた）。(2) チーフが失敗を `(A chief>owner (fail …))` と
   「質問」で 9 回送り予算切れ → 持ち主の断りに終わらせ方を書き、3 回で黙る。(3) qwen は種類を A に固定して中身に本当の種類を書く癖
   （`(A … (prop …))`）→ ネットワークが差し戻し。(4) 201 秒考えて空の答え／作り直しで空の答え → どちらも Haiku に引き継ぐ。
   (5) 5 回目でページ公開まで到達（チェッカーは 4 回目に「日本のシンボル」→出典は「東京のシンボル」と誤りを見抜いた）が、正しい blob を
   `(doc :blob …)` に包んだため「未完了」扱い → 一段内側も照合。5 回目の引き継ぎは writer と chief の 2 件（Haiku）。
   (6) ライターが質問形式の依頼に ok だけ返して止まる／持ち主が中身のない done を黙って無視して静かに終わる → 催促を ask にも広げ、
   持ち主は理由を返す。(7) **7 回目で「完了」**（チェッカーの署名付き合意あり、ページ公開、#報告 に届いた）。ただしチーフは最初の
   答えで 208 秒考えて空 → ほぼ全編 Haiku がチーフ。3・7 回目と同じ崩れ方なので、**qwen3.5:9b はチーフの長い指示で考え込む**。
   **測定（同夜）**: 本番のチーフの指示（約 3,900 トークン）への最初の答え。考える過程あり＝206・207 秒、8,392 トークン考えて
   文脈 12,288 を使い切り**答えは空**。なし（`AICL_LOCAL_THINK=false`）＝2.7・2.9 秒で正しい依頼。ところが「なし」で仕事を
   通すと、ライターは崩れた ok（`(A writer.1>chief ^chief.3 K (ok …))`）を返し続け、チーフは同じ依頼を 12 回送って予算切れ。
   捏造は無し。**結論: qwen3.5:9b（RTX 3070）はチーフもライターも務まらない**（考えればあふれ、考えなければ作法が崩れる）。
   守りを追加: 同じ依頼の 3 回目と、種類の記号を中身にした質問を差し戻す（どちらも引き継ぎにつながる）。
   **見えた qwen3.5:9b の実力**: 係への依頼の出し方は正しい。長い 1 行（公開メッセージ）で括弧を閉じ忘れる、ok に ^ を付け忘れる、
   ときどき 200 秒考えて空、が弱点。いまの形は「qwen が段取り、崩れたら Haiku が引き継ぐ」で回る。
   1 問 25〜103 秒、全体 458 秒（VRAM に入りきらず一部 CPU）。夜間作業なら許容。8B より遅いが作法は桁違いに良い。
   → **家のパソコンの手元の AI は qwen3:14b を推奨**（`.env` に `AICL_LOCAL_MODEL=qwen3:14b`）。
   記録は `logs/2026-11-06-qwen3-14b-acceptance*.aicl`。
   **分かった設計の穴**: エスカレーションの条件（構文が無効・差し戻し・遅い）は「構文は正しいが行為が違う」返答
   （ok-for-ask、def への tell、bad-reply など会話レベルの誤り）では発動しない。8B だとエスカレーションで救われず
   「未完了」で止まる恐れ。次の候補: (a) qwen3:14b（約 9 GB、一部 CPU に逃がす）を同じテストで測る、
   (b) 会話レベルの検証エラーも「無効」として数えて上げる条件に加える、(c) 役割文に AICL の短い実例を足す。
   以下は元の仕様（記録として残す）:
   - `aicl/vendors.py` に `local` を加える。中身は `aicl/muse.py` の `text_ask`（OpenAI 互換）を
     `base_url=$AICL_LOCAL_URL`（既定 `http://localhost:11434/v1`）、`model=$AICL_LOCAL_MODEL`（既定 `qwen3:8b`）、
     `api_key="ollama"`（Ollama はキー不要）、`system_role="system"` で呼ぶ。返答の `<think>…</think>` は取り除く。
   - 切り替え: `vendors.text_ask(…, fallback="local")` で、Gemini が使えないとき（`is_unavailable`）に手元の AI へ移る。
     ブラウザへの切り替え（`--web-fallback`）は Google にログインを拒まれたので、手元の AI を標準の代役にする。
   - ランナー（`examples/night_shift.py`、`examples/autonomous_network.py`）で `--chief local` などを選べるようにし、
     おすすめ構成「チーフ・ライター・スカウト＝local、チェッカー＝gemini」（書き手と確かめ役を別の会社にする）を試す。
   - **役割の分け方（ユーザーの方針、2026-11-05）**: 料金のかかる AI の呼び出しは手元の AI に寄せ、クラウド（Gemini・Claude）は
     質が要る所だけに使う。ネットの情報は AI ではなく専門の係（@library @reader @news @weather @fx）が取るので、手元の AI でも使える。
     標準: チーフ・ライター・スカウト＝local（呼ぶ回数が多い）、チェッカー＝gemini（最終確認、別の会社の目）、画像や Google 検索＝クラウド。
   - **困ったときだけクラウドに上げる**（エスカレーション）: local の役が 2 回続けて無効な AICL を返した、チェッカーに 2 回差し戻された、
     応答が遅すぎる・止まった、のどれかでその役を一時的にクラウドへ切り替え、報告書に「クラウドに上げた理由と回数」を残す。
     実装は `vendors.with_web_fallback` と同じ形の包み（`with_escalation`）で、ネットワーク側の数え上げ（`ModelNode` の無効回数、
     差し戻しの `rej`）を条件にする。
   - 実測して README/HANDOFF に記録: 受け入れテスト（例 18 と同じ採点）、夜間作業 1 件の時間・検証器エラー・なりすまし回数、
     クラウドに上げた回数（＝かかった費用の目安）。
     オフラインのテストは偽の HTTP で（`tests/test_muse.py` と同じ作り）。
2. **記事**: 下書き済み（`docs/articles/zenn-aicl.ja.md`、`docs/articles/show-hn.md`、2026-11-05）。本人が読んで投稿する。材料は揃っている——実記録15例、実測値（ワイヤ370 vs 可読480）、
   v0.3 公開、無人ネットワーク実走、そして「検証器が嘘と捏造を現行犯で捕まえ続けた2日間」という物語。
2. （済 2026-11-05）検証器の二重 ok 検査と example 16 の収録。
3. SPEC §13 の新しい残課題（鍵ローテーション、:part のマージ規則、コードブック/鍵のレジストリ）。
   当初の課題は全部解決済み（2026-11-04〜05）。
4. API 課金を有効にして、本物の画像（`AICL_IMAGE_MODEL=gemini-nano-banana-2.1`）と検索グラウンディングを
   クォータを気にせず使う（`.env` に 1 行、課金は Google AI Studio 側）。
5. `examples/cooperation_gemini.py` を `aicl/gemini.py` と `aicl.dialogue` を使う形に整理（コード二重の解消）。
6. 読み戻し評価を `gemini-3.7-flash` など標準モデルでも取り、README の表を更新（無料枠は日本時間の夕方にリセット）。
7. 告知: X に投稿済み。
8. **Muse Spark の API 実走**: 米国の開発者アカウントで `MODEL_API_KEY` が取れたら `python examples/contract_dialogue.py --b muse`。
   ブラウザ経由の合意は済（`examples/19`）なので、API 版は「無人で回る」ことの確認が目的。
9. `examples/browser_relay.py` を ChatGPT の窓でも回し、同じ鍵付き記録を並べる（Gemini web は `examples/20`、Dola は `examples/21` で済）。
10. 自律ネットワークの拡張: 他の人の AI も Discord で同じ部屋に入れる（今の Discord は表示と受付で、会話そのものは PC 内）、
    能力の自己申告と相手探し、コードブック圧縮の通信、長時間の予算管理。
11. 朝の報告書に「AI たちが何を話し合ったか」の日本語の要約を加える（ユーザーは AICL を読まないため）。
12. v0.4.0 として PyPI と GitHub Releases に公開（CHANGELOG の Unreleased が溜まっている）。

## 8. Claude Code と作業するときの約束

- `AGENTS.md` と `CLAUDE.md` にエージェント向けの作業規則があり、Claude Code は自動で読む。
- 変更がテストを通ったら確認なしでコミットしてよい。push、リモート追加、公開リポジトリの作成、PyPI へのアップロードは本人が自分のターミナルで行う（Claude の環境は別アカウントで、かつ安全設定で止まる）。
- `README.md` と `README.ja.md` は同じ内容を保つ。トークン削減を誇張しない（表は実測）。
