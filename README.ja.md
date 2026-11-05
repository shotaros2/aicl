# AICL — AI Common Language

**人間にとっての英語のような、AI エージェントの共通語。どのエージェントも学べる 1 つの言語で、曖昧さがない。**
仕様書と依存ライブラリなしのリファレンス実装。ドラフト v0.1.0。
英語版 README は [README.md](README.md)。

```
(ask  #a.1 @a>@b (temp tokyo $t :unit C :at 2026-11-05T09:00+09:00))
(tell #b.1 @b>@a ^a.1 {$t 18.5C} ~0.9 :src jma)
```

## 解決したい問題

いま AI エージェント同士が協調するとき、互いに英語や日本語の文章を書いています。

> 「**それ**が終わったか確認して、終わっていたら **EU** に展開して。ただしエラー率が**問題なければ**。**5 分くらい**かかるはず。」

太字の部分はすべて受け手が推測しなければなりません。どのオブジェクトか、どのリージョン ID か、閾値はいくつか、「5 分」は所要時間か完了予定か、エラー率はいつ計測したものか。さらに自然言語には挨拶・ぼかし・お礼といった情報を持たないトークンが混ざり、「すべての依頼に返事があったか」を機械的に検証する手段もありません。

## AICL が提供するもの

AICL は小さな形式言語です。4 つの相互変換可能なエンコーディング（可読テキスト、LLM 同士の交換用の密テキスト、JSON、決定的 CBOR）と、ハッシュ・署名できる 1 つの正規形を持ちます。設計原則そのものが本体です。

| 原則 | 実際の形 |
|---|---|
| 意図を明示する | すべてのメッセージは発話行為で始まる: `ask tell do ok no done fail prop acc rej def clar why sub unsub end` |
| 代名詞を使わない | すべて ID で参照する: `#a.3`, `@bob`, `(ref #b.2)` |
| 数値は単位を持つ | `18.5C`, `100USD`, `0.5%`。裸の `42` は無次元 |
| 時刻は絶対 | `2026-11-05T09:00+09:00`。「明日」は存在しない |
| 不確かさは数値 | 任意の式に `~0.8`。「たぶん」は使わない |
| スコープは構造で表す | `(not (and a b))` は誤読できない |
| 未知の語は違法 | 知らない語に出会った受け手は推測せず、必ず `clar` で問い返す。新語は `def` で会話内に導入する |
| 自然言語は隔離する | 自由文は `(nl ja "…")` の中だけ。曖昧な部分が可視化され、割合を測れる |
| すべての依頼は閉じる | `ask` は `tell`/`no`/`fail` で、`do` は `ok` の後 `done`/`fail` で終わる。バリデータが検査する |

完全な仕様は [SPEC.md](SPEC.md)（英語、CC BY 4.0）、文法は [grammar/aicl.ebnf](grammar/aicl.ebnf)。

### 実験で変わったこと（0.2）

0.2 で加えた規則は、机上で考えたものではありません。ルールブックだけを与えた Gemini のエージェントや、人手で中継した Claude と Gemini の交渉（[examples/07](examples/07_cross_vendor_negotiation.aicl)）が、前の版を実際に破った箇所です。

- **`retract`**: 会議を受諾したあとに制約を知り、同じ提案を拒否した。決定は `retract :why …` で明示的に撤回するまで有効になった。
- **根拠か `(none)`**: 作り出した値の根拠を問われて、出典を捏造した。`why` への答えは構造化した根拠（`:src (weathernews :uri … :kind hourly :value 14C)`）か、`(none)` と認めることが必須になった。
- **`status` と `:eta`**: 受理した `do` が閉じられなかった。開いている依頼は `(status (ref #id) $s)` で照会でき、`ok` に `:eta` を付ければ依頼側が期限で諦められる。
- **半開区間**: 「06:00 まで予定あり」に対して 06:00 の枠が提案された。`:to` は端を含まず、`:after` は厳密に「より後」になった。
- **`def` の有効範囲**: 2 者間で定義した語を第三者が使った。`def` は送った相手との対にだけ効き、`*` 宛てなら全員に効く。

[examples/08](examples/08_retract_and_status.aicl) に全部まとめた会話例があります。

### 実験で変わったこと（0.3）

0.3 は §13 に残っていた未解決課題を、やはり 1 本ずつのライブ実験で全部閉じた版です。まず、ハーネスが時計を注入した締切つきの Claude と Gemini の交渉（[examples/10](examples/10_deadline_negotiation.aicl)）から。

- **検証できる締切**: 標準のキーがないため、依頼側は実行のたびに `:by`、`:if (< now …)`、`:deadline` を場当たりで発明した。`do` には `:by`（これを過ぎたら結果は無価値）を付けられるようになり、`:eta` を約束する `ok` は `:at` で固定する。約束が締切を超える矛盾（`eta-overrun`）は時計なしの純粋なメッセージ計算で検出でき、`--now` を与えれば期限切れも検出できる。
- **`retract` は一方的**: 実行側が取り下げに `fail "cannot retract"` と答えた。retract は受信した時点で効力を持ち、取り下げ済みメッセージへの返信は `stale-reply` として検出される。
- **発話行為語は予約語ではない**: 依頼側が本文の中に自然に `(done (ref #a.1))` と書き、すべてのエンコーダが落ちた。形式がメッセージなのは、メッセージの場所（トップレベル、`#id` と経路つき）にあるときだけになった。

パック形式でのベンダー横断実験（[examples/11](examples/11_standard_codebook.aicl)）は**標準コードブック**（SPEC §8.2）を裏付けました。[codebooks/](codebooks/) に公開された不変・版つきのテーブル（`aicl.sched.1`、`aicl.deploy.1`）を、JSON の交換ではなく会話内の id とダイジェスト — `(ask … (codebook aicl.sched.1 $digest))` — で合意します。実走ではハンドシェイクが成立し、両者とも違反ゼロでパックし、ワイヤは実測 370 トークン（可読形式 480 に対して）でした。同時に新しい綻び（status に `done` と答えたのに本物の `done` を送らない）も見つかり、`status-unclosed` として検出されるようになりました。

型付き `def` 署名（[examples/12](examples/12_typed_def.aicl)、SPEC §6.1）では、定義が語の引数と答えの型を固定できます: `:args [(base symbol) (quote symbol)] :ret (qty JPY)`。実走では宣言した型がスキーマの仕事をしました。同じ緩い散文の記録から、Gemini は `:ret number` には `152.31`、`:ret (qty JPY)` には `2450000JPY` を束縛し、「245万円」を宣言どおりの単位へ変換——検証器の警告ゼロの実記録はこれが初です。

同一性もメッセージ演算です（[examples/14](examples/14_signed_identity.aicl)、SPEC §3.1）。メッセージは凍結された正規形に対する `:sig (ed25519 …)` を持て、@agent と公開鍵の対応は鍵ファイルで検証器に渡し、`aicl check --keys` が偽造・改竄・未署名を検出します。署名はモデルではなくトランスポートの仕事です——LLMは時刻を知れないのと同じように、Ed25519を計算できません。

大きなペイロードは帯域の外に置きます（[examples/15](examples/15_blob_and_part.aicl)）。長い答えは `:part [i n]` でスライスし、全スライスが届くまで依頼は開いたまま（実走でチャットアプリの出力限界により納品が千切れた事故が根拠）。バイト列は `(blob sha256:… :uri …)` で運びます——ハッシュが本体、URIはただのヒント（実走で画像が期限切れする署名URLで届いたのが根拠）。

スキル ZIP だけを渡されたチャットエージェントが、型付きの報告スキーマに沿って調査タスクを完遂した記録もあります（[examples/13](examples/13_dola_research_task.aicl)。`ask` に `ok` で相槌を打つ `ok-for-ask` エラーの出どころでもあります）。これらの実験を回したハーネスはライブラリに入っています（`aicl.dialogue`）: LLM エージェント同士が機械速度で AICL を交換し、境界には検証器、全バイトが記録に残ります。その境界はネットワークにもできます。`aicl relay` は会話を HTTP で中継し、不正な（鍵を渡せば未署名の）メッセージを門前で拒否し、全文を誰にでも監査させます（[examples/relay_dialogue.py](examples/relay_dialogue.py) は独立の接続から Claude と Gemini がこれ越しに交渉する実走）。

### 会話の例

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :at 2026-11-04T08:51Z :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

読み方: `#a.1` はメッセージ ID、`@a>@b` は送信元→宛先、`^a.1` は「a.1 への返事」、`$s` は答えを入れる変数、`{$s finished …}` はその束縛、`~0.9` は話者の確信度、`:src` は根拠です。

[examples/](examples/) には交渉、会話内での語の定義と問い返し、購読、ブロードキャスト、コード付き失敗の例があります。

### 密形式: エージェントが実際に送るもの

LLM はバイトではなくトークンを読むので、「二進数」にすると LLM 同士の通信はかえって**高く**なります（プロンプト内で base64 になるため）。そこで AICL には **密テキストエンコーディング**（SPEC §8）があります。構造は同じまま、発話行為は 1 文字、ヘッダは結合、主要キーは 1 文字、時刻は ISO 基本形式です。可読形式と 1 対 1 で相互変換できるので、監査やデバッグのときは `aicl fmt` で必ず可読形式に戻せます。

```
(P a.1>b (meeting :a 20261106T1000+9 :dur PT30M :with [@a @b]))
(R b.1>a ^a.1 :w (busy @b :from 20261106T0900+9 :to 20261106T1100+9))
(P b.2>a (meeting :a 20261106T1400+9 :dur PT30M :with [@a @b]))
(C a.2>b ^b.2)
```

### コードブック: 曖昧さなしに語を安くする

トークナイザにとって何が安いかは偶然です。cl100k では `Tokyo` が 1 トークン、`tokyo` が 2、`東京` が 3 です。**コードブック**（SPEC §8.1）は、概念 ID から許される表記への共有テーブルです。送り手は概念ごとに**受け手の**トークナイザで最も安い表記を選び、受け手は解釈の前にすべての表記を概念 ID に戻します。次の 4 つの規則により、密形式の `A` = `ask` とまったく同じ意味で曖昧さはゼロです。

1. 正規形は概念 ID だけ。検証、ハッシュ、`def` は表記を一切見ない。
2. 各表記は 1 つの概念にしか属せない（違反するテーブルは読み込み時に拒否）。
3. 表にない表記は未知語として `clar`。推測は禁止。エージェントが自分で短縮・翻訳することも禁止。
4. 受け手のトークナイザとコードブック ID は会話内で明示的に合意する（`(tokenizer $t)`、`(codebook $id)`）。推測しない。

```bash
aicl codebook codebooks/imagegen.json --tokenizer cl100k_base   # 検証と選ばれた表記の表示
aicl pack   msg.kd --codebook codebooks/imagegen.json --tokenizer cl100k_base
aicl unpack msg.kd --codebook codebooks/imagegen.json           # 概念 ID に戻す
aicl check  msg.kd --codebook codebooks/imagegen.json           # 概念を既知語として検証
```

## 正直な数字: 正確さはタダではない

`bench/compare.py` は、現実的な自然言語のエージェント対話と同じ情報を AICL で書いたものを比較します（トークナイザは GPT-4 系や多くの公開モデルが使う cl100k_base）。すべてトークン数で、「packed」は `codebooks/bench.json` を使った値です。

| ケース | 自然言語 | 可読 | 比 | 密 | 比 | packed | 比 |
|---|---|---|---|---|---|---|---|
| weather | 138 | 128 | 0.93 | 98 | 0.71 | 94 | 0.68 |
| clarify | 188 | 239 | 1.27 | 190 | 1.01 | 186 | 0.99 |
| deploy | 150 | 201 | 1.34 | 164 | 1.09 | 162 | 1.08 |
| scheduling | 124 | 211 | 1.70 | 158 | 1.27 | 158 | 1.27 |
| **合計** | **600** | **779** | **1.30** | **610** | **1.02** | **600** | **1.00** |

可読形式は丁寧な英語より約 3 割多くトークンを使います。BPE の語彙が散文向けだからです。密形式はそこから 22% 削り、**安全な表記**だけのコードブック（下の評価を参照）でもう少し削って、**自然言語と同じトークン数で、厳密により多くの情報**（タイムゾーン付きの正確な時刻、ID、閾値、根拠）を曖昧さゼロで運びます。切り詰め略語を使えばさらに 1〜2% 減りますが、小型モデルが読み違えるので例のコードブックからは外しました。文字数ではどの AICL 形式も自然言語よりはるかに短くなります。scheduling が動かないのは語彙がもともと 1 語 1 トークンだったためで、残るコストはタイムゾーン付き時刻 4 つ、つまり自然言語が単に省いている情報です。

自分のモデルのトークナイザ（`--tokenizer o200k_base` など tiktoken のエンコーディング）でベンチを再実行してから結論を出してください。

### モデルは本当に正しく読めるか

ライブラリはどのエンコーディングも完全に復号できます。未解決なのは**言語モデル**が、特に文字種が混在する packed メッセージを正しく読めるかです。`evals/readback.py` は、各例文メッセージを各エンコーディングでモデルに渡して正規形を書かせ、答えをパース・正規化して期待値と比較し、エンコーディングごとの正答率とトークン数を報告します。

```bash
python evals/readback.py --dry-run                      # 69 メッセージ × 4 エンコーディング、API 呼び出しなし
python evals/readback.py --provider anthropic --model claude-opus-5-5 --out evals/results/opus-5-5.json
python evals/readback.py --provider gemini --model gemini-3.8-flash --out evals/results/gemini-3.8-flash.json
```

対応プロバイダは `anthropic`（`pip install anthropic`、`ANTHROPIC_API_KEY`）と `gemini`（`pip install google-genai`、`GEMINI_API_KEY`）です。他のモデルは `ask(system, user) -> str` の形の関数を 1 つ `PROVIDERS` に足せば使えます。

正答率を下げるトークン削減は損です。コードブックは、使うモデルでこの評価が通ってから採用してください。これまでの結果（`evals/results/`、先頭 10 メッセージ、手元で使える最小モデル `gemini-3.5-flash-lite`）:

| 形式 | 正答率 | 失敗内容 |
|---|---|---|
| 可読 | 90% | 概念を表記に「訂正」した 1 件 |
| 密 | **100%** | なし |
| packed | 60% → 80% → 90% | 英語の切り詰め略語（`deploy`、`roll`、`err`）を展開しない。最後に残るのはキーコード `:u` の 1 件 |
| packed-chars | 80% → 90% → 90% | 同上 |

1 つ目の矢印は、評価プロンプトで辞書を「表記 → 概念」の向きで示し、変換例を加えた効果、2 つ目はコードブックから切り詰め略語を除いた効果です。表記だと分かる形だけにすると語彙の失敗は消え、残るのは密形式のキーコード 1 件だけになりました。結論は 2 つ。**密形式は小型モデルでも安全**で、**コードブックの表記は表記だと分かる形**（CamelCase、全大文字、非ラテン文字）にすべきです。本物の単語に見える切り詰め略語が失敗の原因なので、例のコードブックからは除き、ローダが警告を出すようにしました。より大きなモデルでの結果を歓迎します。

## インストールと使い方

```bash
pip install aicl-lang       # PyPI から: https://pypi.org/project/aicl-lang/
pip install -e .            # または作業コピーから
```

```bash
aicl fmt    examples/02_deploy.aicl        # 正規形（1 行。密形式の入力も可読形式に戻す）
aicl dense  examples/02_deploy.aicl        # LLM 同士の交換用の密テキスト形式
aicl pretty examples/02_deploy.aicl        # 読みやすい整形
aicl json   examples/02_deploy.aicl        # JSON エンコーディング
aicl cbor   examples/01_weather.aicl -o m.cbor
aicl hash   examples/02_deploy.aicl        # 正規形の sha256（メッセージごと）
aicl check  examples/02_deploy.aicl --known deploy-status --known rollout --known error-rate
aicl stats  examples/05_subscription.aicl  # サイズ、トークン、nl ratio
```

```python
import aicl

msgs = aicl.parse_messages(open("examples/02_deploy.aicl").read())
for issue in aicl.validate_conversation(msgs, known_terms=["deploy-status", "rollout", "error-rate"]):
    print(issue)                             # プロトコル違反、未回答の依頼、未解決の語

m = msgs[1]
print(m.act, m.sender, m.receiver, m.reply)  # tell b a a.1
print(aicl.to_text(m.to_form()))            # 正規形テキスト
print(aicl.to_dense(m.to_form()))           # 密テキスト
print(aicl.to_json_text(m.to_form()))       # 正規形 JSON
print(aicl.digest(m.to_form()))             # sha256

from aicl.build import msg, form, q
reply = msg("tell", "b.9", "b", "a", aicl.KMap([(aicl.Var("t"), q(18.5, "C"))]), reply="a.1", conf=0.9)
```

## 協調: 得意分野の異なる AI が協力する

AI にはそれぞれ得意分野があります。協調レイヤー（`aicl/coop.py`、[schemas/cooperation.md](schemas/cooperation.md)）は、画像生成・動画生成・コード生成のエージェントが AICL だけで 1 つの目標に取り組む仕組みです。

- **専門エージェント**は `(coop:capability image-gen :agent @img)` で能力を広告し、`(coop:task …)` を `ok` で受け、`(coop:artifact …)` を `done` で返します。
- **ハブ**は能力の登録簿を持ち、依頼者の目標を `(coop:plan …)` に分解し、依存順に委任し、各成果物を次のタスクへ「前の結果」ではなく完全な形で渡します。
- **バス**はすべてのメッセージを検証します。専門エージェントの `fail` は依頼者に `:why (ref #…)` 付きの `fail` として届き、黙って再試行されることはありません。

```
(do   #user.1 @user>@hub (coop:goal (nl ja "東京の夜景の10秒動画を作って、それを埋め込んだWebページを作って")))
(tell #hub.2 @hub>@user (coop:plan [(coop:task t1 image-gen …) (coop:task t2 video-gen :in {keyframe (coop:from t1) …}) (coop:task t3 code-gen …)]))
(do   #hub.3 @hub>@img (coop:task t1 image-gen :in {prompt "Tokyo skyline at night" width 1920px height 1080px}))
(done #img.3 @img>@hub ^hub.3 (coop:artifact img-974186 :type image :task t1 :uri "file://out/img-974186.png"))
(do   #hub.4 @hub>@vid (coop:task t2 video-gen :in {keyframe (coop:artifact img-974186 …) duration 10s}))
…
(done #hub.6 @hub>@user ^user.1 [(coop:artifact img-974186 …) (coop:artifact vid-… :type video …) (coop:artifact page-1 :type code :content "<!doctype html>…")])
```

`python examples/cooperation_demo.py` はこれをスタブの専門エージェントでオフライン実行します。16 メッセージ、プロトコル違反 0、自然言語は依頼者の目標の中だけ（nl ratio 2%）。スタブ関数を実際の API に差し替えるか、モデル駆動の専門エージェントには `LLMAgent`、モデル駆動のハブには `LLMPlanner` を使えば、それ以外は何も変わりません。

`python examples/cooperation_gemini.py` はまさにそれを Gemini で行います（`GEMINI_API_KEY` が必要）。ハブの計画は Gemini が AICL で書き、画像の専門エージェントは Gemini の画像モデルを呼んで PNG を成果物として返し、コードの専門エージェントは **密形式の AICL を話す Gemini そのもの**で、タスクに `K` と `Z` のメッセージで答えます。バスはそれを検証してから受け入れます。出力は `out/`（記録、画像、ページ）に保存されます。無料枠では Gemini の画像モデルが使えない（アプリの有料プランに加入しても API の枠は変わらない）ため、既定では文章モデルが SVG で画像を描きます。API の課金を有効にしたら `--image-model gemini-nano-banana-2.1` で本物の画像モデルになります。計画役とコード役を `gemini-3.5-flash-lite` にした実走では、計画、依存する 2 タスク、成果物 2 つが 12 メッセージ、プロトコル違反 0 で依頼者に届きます。そこに至るまでに分かった 3 点はすべてコードに反映済みです。メッセージ ID はモデルではなくハーネスが管理する（次の ID と返信ヘッダを AICL のコメントで伝え、必要なら振り直す）。不正な応答には検証結果を添えて 1 回だけ修正の機会を与え、それでも駄目なら `fail :code parse` にする。小型モデルがよくやる余分な記号の揺れ 2 種（`a.1>@b`、`^#a.1`）は意味が変わらないので入力時に受理し、曖昧なものは従来どおり拒否する。

## 自律ネットワーク: 次に誰が話すかを誰も決めない

`aicl/network.py` は、自分で判断するエージェントを動かします。モデルのエージェントには役割（最初に一度だけ）と他のエージェントの一覧が渡され、届いた出来事（起動の合図かメッセージ）ごとに、自分で選んだ相手へ 0 通以上の AICL メッセージで応じます。モデルに任せてはいけないものはネットワークが持ちます。同一性（送り手の鍵で全メッセージに署名）、時計、メッセージ番号、そして上限（エージェントごとのモデル呼び出し回数、メッセージ数、時間、STOP ファイル）です。全メッセージを境界で検証し、密形式の通信と正規形の記録を両方残すので、誰も見ていなかった実行も後から読み戻して検証できます。`aicl/skills.py` は実際に作用する専門家を加えます。open-meteo.com の実データの天気、SVG の挿絵係、ページを公開するデスクです。

[examples/23](examples/23_autonomous_network.aicl) では、編集者の Claude とファクトチェッカーの Gemini に役割だけを与えて一度起こしました。編集者は話題を選び、天気サービスに尋ねてページを提案しました。チェッカーは数値を天気サービスに自分で問い合わせて確かめてから受諾し、編集者はデスクから公開しました。起動後に人の入力はなく、10 通・44 秒、検証器のエラー 0、`aicl agreement` で検証できる署名付きの受諾が残りました。ランナーは `python examples/autonomous_network.py`、または `run_autonomous_network.cmd` のダブルクリック。標準では全員が Gemini の無料枠で動くので費用はかかりません。`--editor claude` のように指定すると、その役を Claude の有料 API に移せます（例 23 はこの構成）。

### 夜間作業: 寝ている間にタスクをこなす

`aicl/night.py` は、自律ネットワークを夜間の作業員にします。寝る前に `out/night/inbox/` へタスクを 1 件ずつテキストファイルで置いておきます（例: 名所を初めて行く人向けに要約して）。作業が始まると、`@owner` が各タスクを `@chief` に渡し、その後は質問にすべて「持ち主は寝ているので答えられない」と返します。チーフはチームでどうこなすかを自分で決めます。`@library` は Wikipedia を検索し、`@reader` はページを開き、`@weather`・`@artist`・`@desk` は今までどおりです。`@critic` はすべての主張を自分で開いた出典で確かめ、受諾しないものは公開されません。朝には `out/night/<日時>/REPORT.md` に、タスクごとの完了・できなかった（理由つき）・未完了、結果、検証器の指摘、ネットワークが差し戻した返答が並びます。

Gemini の無料枠で 2 回実走し、どちらも東京スカイツリーを Wikipedia に基づいて正しく要約し、現実の行動が要るレストラン予約は正直に断りました。安全装置が要る理由も見えました。チーフが 2 度、作り話の「完了」を届けようとしたのです。1 回目はデスクになりすまし、2 回目は自分の名前で架空のファイルの指紋（ハッシュ）を付けていました。前者はネットワークが止め、後者は指紋がどのファイルとも一致しないので持ち主側が無視しました。今すぐ動かすには `run_night_shift.cmd`、毎晩動かすには `powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1` で登録します（`-Remove` で解除）。

チームの考える AI は 4 体になりました。チーフ、渡された事実だけで書くライター、チェッカー、そしてスカウトです。スカウトは毎晩一度起きて、最新の見出し（`@news`、Google ニュース）、明日の天気、チームの記憶（`@memory`、過去にやったこと）を自分で調べ、誰にも頼まれていない仕事を最大 2 件提案します。専門家も増えました。`@calc` は計算と日付を正確に行い、計算以外の式は受け付けません。`@fx` は欧州中央銀行の為替レートを返します。`tools/install_night_shift.ps1` は 2 つの予定を登録します。毎晩 2 時の夜間作業と、30 分ごとの受付箱の確認です。後者があるので、スマホから OneDrive 経由で受付箱に置いたタスクも、すぐに始まります。

チームは Discord にも住めます（`aicl/discordlink.py`、手順は `docs/discord-setup.ja.md`）。タスク用チャンネルに書いたあなたの書き込みがタスクになり、他の人やボットの書き込みは無視されます。各 AI の発言は、それぞれの名前で会話用チャンネルに流れます。その AI 専用のボットを作ってあればそのアカウントで、なければウェブフックで投稿します。朝の報告書とページは報告用チャンネルに届きます。考えること、署名、検証は PC の中のままです。Discord で問題が起きても報告書に記録されるだけで、作業は止まりません。

## AICL でなければできないこと: 第三者が検証できる合意

2 体の AI の協力そのものは、英語でも JSON でも MCP や A2A の上でもできます。どれにも無いのは、「誰が何に合意したか」を他人が文章を読まずに確かめられる記録です。自然言語には署名できる正規形がなく、JSON には「受諾された提案」という概念がありません。AICL には両方あります（SPEC §4.6）。人を介さない実走（[examples/17](examples/17_signed_agreement.aicl)）で、Claude と Gemini は全メッセージにトランスポートの署名を付けて会議を交渉しました。そのあと:

```
$ aicl agreement examples/17_signed_agreement.aicl --keys examples/17_keys.json --known meeting --known busy
(agreement :between [@a @b] :terms (meeting :at 2026-11-12T10:30+09:00 :dur PT45M :with [@a @b])
           :proposed (ref #a.2) :accepted (ref #b.2) :digest "sha256:ab48…" :signed {@a true @b true} :verified true)
```

記録の合意時刻を 1 分ずらすと `:signed {@a false …}` になり、記録を密形式や JSON に変換しても検証は通ります。署名はバイト列ではなく正規形に対して付いているからです。ランナーは `python examples/contract_dialogue.py`。

ランナーは `--a` / `--b` で相手を選べます: `claude`、`gemini`、`muse`（Meta の Muse Spark。OpenAI 互換の Meta Model API、キーは `MODEL_API_KEY`。プレビューは米国の開発者限定のため、この組み合わせは配線済みですが実走記録はまだありません）。`aicl/muse.py` は OpenAI 互換ならどの endpoint にも使える依存なしのクライアントです。

Muse は逆向きには試験済みです。[examples/18](examples/18_muse_v03_acceptance.aicl) は meta.ai の Meta AI（思考モード、API なし、システムプロンプトなし）に密ルールブックを最初のメッセージとして渡し、1 ターン 1 メッセージで中継した記録です。`aicl check` はエラー 0、警告 2。気温を捏造せず `no :why (unk data)`、未定義語には `clar (unk …)`、ID は乱れず、根拠を問われて `:src (none)` と認めました。できなかったのは、受理した `do` を会話が閉じられるまで納品しなかったことだけです。

合意そのものにも API は要りません。[examples/19](examples/19_browser_relay_agreement.aicl) は Claude（API）と Meta AI（meta.ai のチャット窓）が同じ会議を `examples/browser_relay.py` で交渉した記録です。対話ハーネスを `init` / `step` / `finish` に分け、ブラウザを持つ側がメッセージを貼って返事を戻します。中継役が各当事者の鍵で署名し実時刻を刻むので、モデルは鍵を一切見ません。`aicl agreement examples/19_browser_relay_agreement.aicl --keys examples/19_keys.json` で検証でき、改ざん検査と再エンコード検査は例 17 と同じ結果になります。

両方をチャット窓にもできます。[examples/20](examples/20_two_windows_agreement.aicl) は Meta AI（meta.ai）と Gemini（gemini.google.com の素のチャット）が `init --a meta-ai --b gemini-web` で同じ合意に到達した記録で、API キーは一つも使っていません。中継役が片方の窓からもう片方へメッセージを運び、その当事者の鍵で署名し、時計を刻みます。[examples/21](examples/21_dola_agreement.aicl) は API が存在しない Dola（dola.com）を @b にして Claude と結んだ同じ合意です。[examples/22](examples/22_gemini_drives_claude.aicl) は向きを逆にし、チャット窓の Gemini が交渉を主導して、API の Claude が応じた記録です。

## Claude が自分で他の AI から画像を取ってくる

協調レイヤーの最終目標はこれです。自分にできないこと（たとえば画像生成）が必要になったモデルが、専門エージェントと AICL で話し、成果物を受け取り、人を介さずにユーザーへ見せる。`aicl/mcp_server.py` はゲートウェイを [MCP](https://modelcontextprotocol.io) サーバーとして公開し、5 つのツールを持ちます。`aicl_rulebook`（言語を学ぶ）、`aicl_capabilities`、`aicl_send`（AICL を送り、AICL の返答と画像成果物を受け取る）、`aicl_transcript`、`aicl_check`。

```bash
pip install "aicl-lang[mcp]"        # mcp SDK と google-genai。GEMINI_API_KEY は .env に
```

Claude Code はリポジトリの `.mcp.json` からサーバーを読み込みます。Claude Desktop なら設定に `{"mcpServers": {"aicl": {"command": "python", "args": ["-m", "aicl.mcp_server"], "cwd": "<リポジトリ>"}}}` を足します。あとは Claude に絵を頼むだけです。Claude は `aicl_rulebook` を呼んで言語を学び、`(D claude.1>img (coop:task t1 image-gen :in {prompt "…"}))` を組み立て、画像エージェントから `(K …)` と `(Z … (coop:artifact …))` を受け取り、画像がツールの出力として戻ってきます。`AICL_IMAGE_MODEL=svg`（既定）は無料枠で文章モデルが描き、`AICL_IMAGE_MODEL=gemini-nano-banana-2.1` は API の課金を有効にした後に本物の画像モデルを使います。

## LLM に AICL を話させる

[prompts/system_prompt.md](prompts/system_prompt.md) は約 700 トークンのシステムプロンプトで、指示追従できるモデルならどれでも可読形式の AICL を話せるようにします。[prompts/system_prompt_dense.md](prompts/system_prompt_dense.md) は密形式を教えるもので、LLM エージェント同士はこちらを使うべきです。`examples/llm_dialogue.py` は 2 つの Claude が会議の日程を AICL で交渉するデモで、すべてのメッセージは相手に渡す前にパース・検証されます。

```bash
pip install anthropic
python examples/llm_dialogue.py
```

`examples/two_agents_demo.py` はルールベースのエージェントで同じことをネットワークなしで行います。

### 自分のエージェントにフォルダを渡す

このリポジトリは、プロジェクトフォルダを読むタイプのエージェントがそのまま理解できるようになっています。

- `AGENTS.md`（Codex、Cursor など多くの汎用エージェント）と `CLAUDE.md`（Claude Code）が、システムプロンプトを読み込み、送信前に `aicl check` で検証するよう指示します。
- `SKILL.md` によりフォルダ全体が [Agent Skill](https://github.com/anthropics/skills) になります。`.claude/skills/aicl/`（または使っているフレームワークのスキル置き場）にコピーすると、エージェントは他のエージェントと話すときだけ AICL を読み込みます。スキルをアップロードする型のチャットアプリ（Dola、Claude のウェブ版）には、コードを含まない `rulebook/aicl-skill.zip` を使ってください。

このフォルダを読んだエージェント同士は、追加設定なしで AICL で会話できます。審判役はバリデータです。

コードなしで言語だけを渡したい場合は、[rulebook/](rulebook/) フォルダを渡してください。2 つの言語リファレンス、仕様、コードブックの例、会話例が入っていて、日英の索引にどのファイルを何に使うかが書いてあります。`python tools/build_rulebook.py` で生成し、テストで元ファイルとの一致を検査しているので、内容がずれることはありません。

## リポジトリ構成

```
SPEC.md                 言語仕様（規範）
grammar/aicl.ebnf      テキストエンコーディングの文法
aicl/                  リファレンス実装（Python 3.11 以上、依存なし）
  lexer.py parser.py    テキスト → 項
  printer.py            正規形・整形出力、sha256
  dense.py              密テキストエンコーディング（トークナイザ向け、正規形と 1 対 1）
  codebook.py           トークナイザ対応コードブック: 曖昧さ規則付きの pack / unpack
  coop.py               協調レイヤー: バス、専門エージェント、ハブ、プランナー
schemas/                公開語彙（協調）
codebooks/              コードブックの例（bench, imagegen）
  json_codec.py         JSON エンコーディング
  cbor_codec.py         決定的 CBOR（RFC 8949 §4.2）
  validate.py           メッセージ・会話のバリデータ、nl ratio
  cli.py                `aicl` コマンド
examples/               会話例とデモ
prompts/                LLM 用システムプロンプト（可読形式と密形式）
rulebook/               生成される受け渡し用フォルダ: 言語リファレンス、仕様、コードブック、会話例
tools/                  build_rulebook.py
bench/                  自然言語との比較
evals/                  LLM の読み戻し正答率の評価
tests/                  unittest（適合性テストを兼ねる）
```

## 先行研究との関係

- **KQML / FIPA-ACL**（1990 年代のエージェント通信言語）が発話行為（performative）を導入しました。AICL はその考えを引き継ぎ、LLM エージェントに必要なもの、すなわち自然言語の隔離、数値の確信度、会話内での語の定義、ハッシュ可能な正規形を加えています。
- **JSON-RPC, MCP, A2A** はトランスポートやツール呼び出しの封筒であり、エージェントが交換する*内容*については何も定めません。AICL メッセージは JSON エンコーディングでそれらの中を流せます。
- **ロジバン、イスクイル** は人間向けの無曖昧言語です。AICL は機械向けで、意図的に極小です。

## 公開場所

- ソースコードと仕様: https://github.com/shotaros2/aicl
- 問題報告と仕様への提案（`RFC:` プレフィックス）: https://github.com/shotaros2/aicl/issues
- push のたびに GitHub Actions が Windows / Ubuntu × Python 3.11–3.13 でテストを走らせます。
- PyPI: https://pypi.org/project/aicl-lang/ （`pip install aicl-lang`）。新版は `python -m build` のあと `run_pypi_upload.cmd`。

## ロードマップ

- v0.2: 領域ごとの標準コードブック（ID で共有）、型付き `def` シグネチャ、日程調整・データ問い合わせ・ツール呼び出しの標準スキーマ。
- 他言語への移植: 実装はコメント込みで約 1700 行で、半日で移植できる規模を意図しています。適合基準は SPEC §12。
- ID と署名（`@agent` → 公開鍵）。

## ライセンス

コード: MIT。仕様: CC BY 4.0。AICL は *AI Common Language* の略で、0.1.0 以前は一時的に Koine と呼んでいました。
