# シネマインプレッション（個人開発 Part2）

普通の映画感想サイト。観た映画の感想と考察を1日1本ずつ更新する。
サイトの見た目はあくまで普通の感想サイトで、キューや本数などの裏側の都合は表に出さない。

## 構成
- `index.html` — トップページ（記事へのリンク集）
- `articles/<番号>.html` — 記事ページ（1記事1URL）。`tools/build_pages.py` が下書きから生成する
- `data.js` — 作品リスト全573本（裏側の管理用。表示順はキューの下から）
- `drafts.json` / `drafts.js` — 記事データ（概要・作品情報・感想・考察・公開状態）。現在は概要3本分
- `impressions/` — 感想・考察の置き場。声メモの流れは `impressions/README.md`
- `tools/next_draft.py` — 概要の下書き自動化（1日1本）
- `tools/set_impression.py` — 編集済みの感想・考察を記事へ反映
- `tools/publish.py` — 公開処理（編集済みの感想が無い記事は公開できない）
- `.github/workflows/daily-draft.yml` — 毎日1回、自動で次の1本の下書きを作る

## 公開までの流れ
1. 概要の下書きができる（自動・1日1本）
2. 声メモ → 文字起こし（原文は `impressions/<番号>.raw.txt` に保存、公開しない）→ 編集済みを `impressions/<番号>.md` に作る
3. `set_impression.py` で記事へ反映 → `publish.py` で公開状態に
4. サイトを公開ホスティングに載せる（GitHub Pages 予定、リポジトリ未作成）

## 自動化（1日1本）
- `next_draft.py` はキューの下から次の1本だけを対象に、Wikipedia APIでリード文を取得して概要の下書きを作り、出典を付けて `drafts.json` に追加する。キューの status は drafted に更新される
- 1日1本に絞るのは意図的：大量生成はAdSense／検索の量産判定に引っかかりやすい
- `GEMINI_API_KEY` を設定すると、概要を「事実を変えずに短くまとめた文章」に整形する（なければ Wikipedia のリード文冒頭を使う）
- 感想・考察は自動生成しない。本人が書く
- 動作確認：`python3 tools/next_draft.py --dry-run` で次の対象（現在は #570 インターステラー）だけ表示する

## リポジトリ化するときの注意
- GitHub に上げる際は `../filmarks-queue/filmarks_watched_queue.csv` を `data/queue.csv` としてリポジトリに入れる（スクリプトはそちらを優先して読む）
- Actions を使うには GEMINI_API_KEY を Secrets に登録（任意）

## ルール
- 事実情報は出典明記。感想は本人の言葉だけ。他人のレビューの寄せ集めはしない
