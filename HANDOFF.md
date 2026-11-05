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

1. **記事（最優先）**: 下書き済み（`docs/articles/zenn-aicl.ja.md`、`docs/articles/show-hn.md`、2026-11-05）。本人が読んで投稿する。材料は揃っている——実記録15例、実測値（ワイヤ370 vs 可読480）、
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
10. 自律ネットワークの拡張: 常駐化（中継サーバー `aicl/relay.py` 経由で別プロセス化）、時刻や出来事のトリガー、
    能力の自己申告と相手探し、コードブック圧縮の通信、長時間の予算管理。
9. `examples/browser_relay.py` を ChatGPT の窓でも回し、同じ鍵付き記録を並べる（Gemini web は `examples/20`、Dola は `examples/21` で済）。

## 8. Claude Code と作業するときの約束

- `AGENTS.md` と `CLAUDE.md` にエージェント向けの作業規則があり、Claude Code は自動で読む。
- 変更がテストを通ったら確認なしでコミットしてよい。push、リモート追加、公開リポジトリの作成、PyPI へのアップロードは本人が自分のターミナルで行う（Claude の環境は別アカウントで、かつ安全設定で止まる）。
- `README.md` と `README.ja.md` は同じ内容を保つ。トークン削減を誇張しない（表は実測）。
