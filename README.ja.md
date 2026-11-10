# Otohiroi MCP（音拾い）

[English](README.md) | **日本語**

Otohiroi は、Claude Code、Cursor、Claude Desktop などの [MCP](https://modelcontextprotocol.io) クライアントから、ゲーム用の無料の効果音やBGMを探せるようにするツールです。「短い金属の剣の音」「落ち着いたチップチューンのループ」と頼むと、AIが検索し、あなたが耳で選び、ライセンスの記録つきでプロジェクトに入ります。

Otohiroi は索引と補助の道具で、音声ファイルは一切配布しません。ファイルは元の配布元からあなたのPCに届きます。

```
「短い金属の剣の音」
  └─ search_sounds     キーワード、長さ、ループ、ライセンスで検索
  └─ audition_sounds   番号つきの試聴ページを開く（AIは音を聴けないため）
  └─ fetch_sound       無音カット、音量そろえ、変換、CREDITS.md と sounds.license.json の記録
```

## 導入

[uv](https://docs.astral.sh/uv/) が必要です。[ffmpeg](https://ffmpeg.org) があると、変換と音量そろえが使えます。

```bash
claude mcp add otohiroi -- uvx --from git+https://github.com/koyomivanp/otohiroi-mcp otohiroi
```

ほかのクライアントでは次のように設定します。

```json
{"mcpServers": {"otohiroi": {"command": "uvx", "args": ["--from", "git+https://github.com/koyomivanp/otohiroi-mcp", "otohiroi"]}}}
```

## ツール

| ツール | できること |
|---|---|
| `open_sound_studio` | JavaScript / TypeScript のゲームのピッという音を検出し、ローカルの画面を開きます。チェックして、耳で案を選び、ゲームに反映できます。いつでも元に戻せます。合成音なので、音声ファイルもキーも要りません。 |
| `find_replacements` | JavaScript / TypeScript のゲームで発振器が鳴らしている音を見つけ、自然な音の候補をイベントごとに並べた試聴ページを開きます。ゲームは変更しません。 |
| `scan_game` | 発振器で鳴らしている音と、それを鳴らしている場所を一覧にします。 |
| `suggest_search` | ゲームのイベントや擬音（シュッ、ぽよん）を、効く検索語に変換します。 |
| `search_sounds` | ネットの索引と手元のパックを検索します。種類、長さ、ループ、ライセンスで絞れます。標準はCC0のみです。 |
| `get_sound` | 1つの音の詳しい情報を返します。 |
| `audition_sounds` | 最大12個の候補を番号つきで並べた試聴ページを開きます。 |
| `fetch_sound` | 音をプロジェクトに保存し、ライセンスを記録します。 |
| `add_pack` | 自分でダウンロードしたフォルダ、zip、ファイルを登録し、検索と取り込みができるようにします。 |
| `list_packs` | 登録済みのパックと、Freesoundのダウンロードが有効かを表示します。 |
| `find_elsewhere` | 自分で開いて探すサイトの検索リンクを作ります。 |

## 素材の入手元

| 入手元 | 検索 | 試聴 | ダウンロード |
|---|---|---|---|
| Freesound（[Openverse](https://openverse.org) 経由） | キー不要 | できる | 自分の無料キー `FREESOUND_API_KEY` があれば自動（192kbpsの試聴用音源）。なければページのリンクを案内 |
| Jamendo（Openverse 経由） | キー不要 | できる | ページのリンクを案内 |
| Wikimedia Commons（Openverse 経由） | キー不要 | できる | 自動 |
| 自分のパック（[Kenney](https://kenney.nl/assets/category:Audio) など） | 手元 | できる | 自動 |
| ニコニ・コモンズ、YouTubeオーディオライブラリ、OpenGameArt、Pixabay | リンクのみ | 各サイトで | 手動で入手して `add_pack` |

### リンクのみのサイトがある理由

便利さが落ちても、各サイトのルールに従います。

- **YouTubeオーディオライブラリ：** YouTubeの規約は、自動アクセスと、サービスが認めていないダウンロードを禁止しています。公式ヘルプが説明しているのもYouTube動画での利用だけです。
- **ニコニ・コモンズ：** 公開APIが見当たらず、条件は作品ごとに違います。規約第25条で許諾地域が日本国内に限られているので、海外でも配信するゲームは特に注意が必要です。`add_pack` に `region="JP"` を付けると記録に残せます。
- **OpenGameArt、Kenney：** robots.txt がAIエージェントを拒否しています。ブラウザで自分でダウンロードしてから `add_pack` で登録してください。

## 使うときの注意

ライセンスは投稿者の自己申告です。Otohiroi は他作品から持ってきたように見える名前に警告を出しますが、問題がないことを証明はできません。法的な助言でもないので、大事なものは公開前に確認してください。

Freesound のAPIは非商用なら無料で、商用利用は個別交渉と規約にあります。販売するゲームのために音を取得することがこれに当たるかは書かれていないので、気になる場合は Freesound に問い合わせてください。

## 設定

| 環境変数 | 内容 |
|---|---|
| `FREESOUND_API_KEY` | [Freesound](https://freesound.org/apiv2/apply/) で取得した自分のキー。他人と共有しないでください。 |
| `OTOHIROI_HOME` | パックと試聴ページの保存先。 |

## 開発

```bash
uv sync
uv run pytest
```

## ライセンス

コードは [MIT](LICENSE) です。音にはそれぞれのライセンスが適用されます。

[Sozai Search MCP](https://github.com/kanaworksai-hue/sozai-search-mcp) に着想を得ました。Otohiroi は独立したプロジェクトで、ここに挙げたどのサービスとも提携しておらず、承認も受けていません。
