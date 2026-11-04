# Koine（コイネー）

**AI エージェント同士が、曖昧さなしに会話するための言語。**
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

## Koine が提供するもの

Koine は小さな形式言語です。3 つの相互変換可能なエンコーディング（コンパクトなテキスト、JSON、決定的 CBOR）と、ハッシュ・署名できる 1 つの正規形を持ちます。設計原則そのものが本体です。

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

完全な仕様は [SPEC.md](SPEC.md)（英語、CC BY 4.0）、文法は [grammar/koine.ebnf](grammar/koine.ebnf)。

### 会話の例

```
(ask  #a.1 @a>@b (deploy-status build-4821 $s :finished-at $at))
(tell #b.1 @b>@a ^a.1 {$s finished $at 2026-11-04T08:50Z} :src ci-api)
(do   #a.2 @a>@b (rollout build-4821 :region eu-west-1)
      :if (< (error-rate build-4821 :window PT10M) 0.5%))
(ok   #b.2 @b>@a ^a.2 :eta PT5M)
(tell #b.3 @b>@a (error-rate build-4821 0.3% :window PT10M) :src metrics)
(done #b.4 @b>@a ^a.2 (rollout build-4821 :region eu-west-1 :at 2026-11-04T09:04:12Z))
```

読み方: `#a.1` はメッセージ ID、`@a>@b` は送信元→宛先、`^a.1` は「a.1 への返事」、`$s` は答えを入れる変数、`{$s finished …}` はその束縛、`~0.9` は話者の確信度、`:src` は根拠です。

[examples/](examples/) には交渉、会話内での語の定義と問い返し、購読、ブロードキャスト、コード付き失敗の例があります。

## 正直な数字: 正確さはタダではない

`bench/compare.py` は、現実的な自然言語のエージェント対話と同じ情報を Koine で書いたものを比較します（トークナイザは GPT-4 系や多くの公開モデルが使う cl100k_base）。

| ケース | 自然言語 文字 | 自然言語 トークン | Koine 文字 | Koine トークン | トークン比 |
|---|---|---|---|---|---|
| weather | 551 | 138 | 220 | 128 | 0.93 |
| clarify | 721 | 188 | 564 | 239 | 1.27 |
| deploy | 597 | 150 | 432 | 201 | 1.34 |
| scheduling | 433 | 124 | 402 | 211 | 1.70 |
| **合計** | | **600** | | **779** | **1.30** |

Koine は**文字数・バイト数では短く**、曖昧さをすべて取り除きますが、現在の BPE トークナイザでは丁寧な英語より**約 3 割多くトークンを使います**。語彙が散文向けに最適化されているためで、オフセット付き ISO 時刻は約 16 トークン、ヘッダ `#a.1 @a>@b ^a.1` は約 11 トークンです。scheduling には時刻が 4 つあり、それだけでトークンの 4 分の 1 以上を占めます。情報密度が高い weather ではすでに Koine が勝っています。

したがって主張は「トークンが減る」ではありません。主張は **推測ゼロ、機械検証できるプロトコル、曖昧な部分の割合（nl ratio）を測れること** です。トークンコストは工学的課題として公開で取り組みます（ロードマップ参照）。モデル固有のトークナイザやトークナイザを意識した ID 規約を使う場合は、ベンチを再実行してください。

## インストールと使い方

```bash
pip install -e .            # 公開後は: pip install koine-lang
```

```bash
koine fmt    examples/02_deploy.koine        # 正規形（1 行）
koine pretty examples/02_deploy.koine        # 読みやすい整形
koine json   examples/02_deploy.koine        # JSON エンコーディング
koine cbor   examples/01_weather.koine -o m.cbor
koine hash   examples/02_deploy.koine        # 正規形の sha256（メッセージごと）
koine check  examples/02_deploy.koine --known deploy-status --known rollout --known error-rate
koine stats  examples/05_subscription.koine  # サイズ、トークン、nl ratio
```

```python
import koine

msgs = koine.parse_messages(open("examples/02_deploy.koine").read())
for issue in koine.validate_conversation(msgs, known_terms=["deploy-status", "rollout", "error-rate"]):
    print(issue)                             # プロトコル違反、未回答の依頼、未解決の語

m = msgs[1]
print(m.act, m.sender, m.receiver, m.reply)  # tell b a a.1
print(koine.to_text(m.to_form()))            # 正規形テキスト
print(koine.to_json_text(m.to_form()))       # 正規形 JSON
print(koine.digest(m.to_form()))             # sha256

from koine.build import msg, form, q
reply = msg("tell", "b.9", "b", "a", koine.KMap([(koine.Var("t"), q(18.5, "C"))]), reply="a.1", conf=0.9)
```

## LLM に Koine を話させる

[prompts/system_prompt.md](prompts/system_prompt.md) は約 700 トークンのシステムプロンプトで、指示追従できるモデルならどれでも Koine を話せるようにします。`examples/llm_dialogue.py` は 2 つの Claude が会議の日程を Koine で交渉するデモで、すべてのメッセージは相手に渡す前にパース・検証されます。

```bash
pip install anthropic
python examples/llm_dialogue.py
```

`examples/two_agents_demo.py` はルールベースのエージェントで同じことをネットワークなしで行います。

## リポジトリ構成

```
SPEC.md                 言語仕様（規範）
grammar/koine.ebnf      テキストエンコーディングの文法
koine/                  リファレンス実装（Python 3.11 以上、依存なし）
  lexer.py parser.py    テキスト → 項
  printer.py            正規形・整形出力、sha256
  json_codec.py         JSON エンコーディング
  cbor_codec.py         決定的 CBOR（RFC 8949 §4.2）
  validate.py           メッセージ・会話のバリデータ、nl ratio
  cli.py                `koine` コマンド
examples/               会話例とデモ
prompts/                LLM 用システムプロンプト
bench/                  自然言語との比較
tests/                  unittest（適合性テストを兼ねる）
```

## 先行研究との関係

- **KQML / FIPA-ACL**（1990 年代のエージェント通信言語）が発話行為（performative）を導入しました。Koine はその考えを引き継ぎ、LLM エージェントに必要なもの、すなわち自然言語の隔離、数値の確信度、会話内での語の定義、ハッシュ可能な正規形を加えています。
- **JSON-RPC, MCP, A2A** はトランスポートやツール呼び出しの封筒であり、エージェントが交換する*内容*については何も定めません。Koine メッセージは JSON エンコーディングでそれらの中を流せます。
- **ロジバン、イスクイル** は人間向けの無曖昧言語です。Koine は機械向けで、意図的に極小です。

## 世界に公開する手順

リポジトリはそのまま公開できる状態です（テスト、CI、ライセンス、貢献ガイド込み）。

1. GitHub に空のリポジトリ `koine` を作り、`pyproject.toml` の `YOUR-ORG` を自分のアカウント名に置き換える。
2. このフォルダで以下を実行:

```bash
git init -b main
```
```bash
git add -A
```
```bash
git commit -m "Koine v0.1.0: spec, reference implementation, examples, benchmark"
```
```bash
git remote add origin https://github.com/YOUR-ORG/koine.git
```
```bash
git push -u origin main
```

3. push すると GitHub Actions が Windows / Ubuntu × Python 3.11–3.13 でテストを走らせます。
4. PyPI に出すなら `pip install build twine && python -m build && twine upload dist/*`（パッケージ名 `koine-lang` が取得可能か先に確認）。
5. 仕様への意見募集は Issue の `RFC:` プレフィックスで（[CONTRIBUTING.md](CONTRIBUTING.md)）。

## ロードマップ

- v0.2: 型付き `def` シグネチャ、日程調整・データ問い合わせ・ツール呼び出しの標準スキーマ、会話単位の時刻アンカー（RFC 募集中: 時刻 1 つあたり約 10 トークン減るが文脈依存が生まれる）、トークナイザを意識した ID 規約。
- 他言語への移植: 実装はコメント込みで約 1300 行で、半日で移植できる規模を意図しています。適合基準は SPEC §11。
- ID と署名（`@agent` → 公開鍵）。

## ライセンス

コード: MIT。仕様: CC BY 4.0。「Koine」（κοινή、ヘレニズム世界の共通語）は仮の名前です。
