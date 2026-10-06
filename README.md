# KR · CN · JP daily vocab feed

A daily RSS 2.0 feed for a Wodle e-ink device. Each day it publishes 3 cards. Each card shows one concept in Korean, Simplified Chinese and Japanese, usually as cognates with the same Chinese-character root (학습 / 学习 / 学習).

**Feed URL:** https://nwlqx.github.io/kr-cn-jp-feed/feed.xml

## How it works

| File | What it does |
|---|---|
| `words.csv` | The word sets, shown in file order. |
| `config.json` | Start date, review intervals, layout and length settings. |
| `build_feed.py` | Builds and validates `feed.xml`. Uses only the standard library. |
| `test_build_feed.py` | Builds feeds for several dates and checks item count, ordering and title lengths. |
| `.github/workflows/daily.yml` | Runs every day at 06:00 Singapore time, on every push to `main`, and from the Actions tab using **Run workflow**. It runs the tests, builds the feed, commits it and deploys it to GitHub Pages. You can also turn on an upload to Alibaba Cloud OSS. |

Each day moves forward one row in `words.csv`. The three items are:

1. today's word
2. the word from 3 days ago
3. the word from 7 days ago

When too few days have passed for this, the feed fills the gaps with earlier rows. When it reaches the end of the list it starts again from the top.

Run it locally:

```bash
python3 -m unittest -v
python3 build_feed.py                      # today's feed -> feed.xml
python3 build_feed.py --date 2026-11-01    # preview another day
```

## Adding words

Add rows to the end of `words.csv`. The file must be saved as UTF-8 and keep the same header row. In Excel, choose **CSV UTF-8**.

- `id` must be unique. Use the next number.
- `zh` is Simplified Chinese. `zh_pinyin` uses tone marks (xuéxí). `ko_rom` uses Revised Romanization. `ja_rom` uses Hepburn with macrons (gakushū).
- When `zh` and `ja` are identical, the title shows the form only once (학생 学生).
- `notes` is for you only and never appears in the feed.

You can add rows at any time. Rows added at the end are picked up as the schedule reaches them. One catch: once the schedule has wrapped back to the top at least once, changing the number of rows also changes which row is "today", because the position is calculated as days ÷ rows. If you want a clean restart, set `start_date` to today.

If a title is longer than `title_warn_chars` (13), the build prints a warning and the title-length test fails. That limit is roughly what fits on the home-screen widget.

## Settings (`config.json`)

| Key | Meaning |
|---|---|
| `start_date` | The day row 1 is shown, as `YYYY-MM-DD`. |
| `review_offsets_days` | Days back for each item. The default `[0, 3, 7]` gives today, 3 days ago and 7 days ago. List them in increasing order, starting with 0. The number of entries sets the number of items. |
| `description_layout` | `"br"` puts each part on its own line using `<br/>` inside CDATA. `"dot"` puts everything on one line separated by ` · `. Use `dot` if the Wodle shows `<br/>` as literal text or ignores it. |
| `max_description_chars` | `null` means no limit. With a number, the description keeps as many whole parts as fit and cuts the last one with `…`. |
| `include_ja_example` | Set to `false` to drop the Japanese example sentence, for example if kana don't render. Japanese words and romaji still appear. |
| `title_warn_chars` | The title length that triggers a warning. |
| `utc_offset_hours`, `publish_hour` | When a new day starts. The default is 06:00 at UTC+8. |

The description always starts with the meaning, because that's all the home-screen widget has room for.

## Hosting from mainland China: Alibaba Cloud OSS fallback

The Wodle fetches feeds through servers in mainland China. `github.io` is often reachable from there but not reliably. If the feed won't load, turn on the Hong Kong OSS upload:

1. In the Alibaba Cloud console, create an OSS bucket in **China (Hong Kong)**, `oss-cn-hongkong`. Allow public-read objects: either set the bucket ACL to public-read, or turn off "Block Public Access" so the per-object public-read ACL takes effect.
2. Create a RAM user with programmatic access. Give it only `oss:PutObject` and `oss:PutObjectAcl` on that bucket. Don't use your root account key.
3. In GitHub, open the repo and go to **Settings → Secrets and variables → Actions**.
   - Under **Secrets**, add:
     - `OSS_ACCESS_KEY_ID`: the RAM user's AccessKey ID
     - `OSS_ACCESS_KEY_SECRET`: the RAM user's AccessKey Secret
     - `OSS_BUCKET`: the bucket name
   - Under **Variables**, add `OSS_ENABLED` = `true`.
   - Optionally add `OSS_ENDPOINT`. It defaults to `https://oss-cn-hongkong.aliyuncs.com`.
4. Run the workflow from the Actions tab. The feed will be at `https://<bucket>.oss-cn-hongkong.aliyuncs.com/feed.xml`.

Never paste the keys into code, issues or chat. They should only exist as GitHub secrets.
