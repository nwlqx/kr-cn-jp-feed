#!/usr/bin/env python3
"""Build feed.xml: a daily KR / CN / JP vocabulary RSS feed for the Wodle.

Standard library only. Usage:
    python3 build_feed.py                  # today's feed -> feed.xml
    python3 build_feed.py --date 2026-10-20 --out /tmp/feed.xml

Settings live in config.json, word sets in words.csv (see README).
"""
import argparse
import csv
import json
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).parent
REQUIRED_COLUMNS = ["id", "meaning", "ko", "ko_rom", "zh", "zh_pinyin", "ja", "ja_rom",
                    "ex_ko", "ex_zh", "ex_ja", "ex_en"]


# ---------------------------------------------------------------- loading

def load_config(path=ROOT / "config.json"):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_words(path=ROOT / "words.csv"):
    """Read words.csv, skipping blank rows. Order in the file = order shown."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            sys.exit(f"words.csv is missing columns: {', '.join(missing)}")
        rows = [{k: (v or "").strip() for k, v in row.items() if k}
                for row in reader]
    rows = [r for r in rows if r["ko"] or r["zh"] or r["ja"]]
    if not rows:
        sys.exit("words.csv has no word rows")
    return rows


# ---------------------------------------------------------------- schedule

def pick_positions(day_number, offsets):
    """Which schedule positions to show, newest first.

    day_number is days since start_date (0 on the start date). Normally item k
    is the word from offsets[k] days ago. Early on, when that would be before
    the start date, we fill with the next earlier position instead, so the
    three items are always distinct. Positions below 0 wrap to the end of the
    list (handled by the caller with % len(words)).
    """
    positions = []
    for offset in offsets:
        wanted = day_number - offset
        if positions and (wanted < 0 or wanted >= positions[-1]):
            wanted = positions[-1] - 1
        positions.append(wanted)
    return positions


# ---------------------------------------------------------------- formatting

def korean_form(w, cfg, hangul_key, rom_key):
    """Hangul, or its romanization when korean_script is "romanized"
    (the Wodle's font has no Hangul, so Hangul shows as empty boxes)."""
    if cfg.get("korean_script", "hangul") == "romanized":
        return w.get(rom_key, "")
    return w[hangul_key]


def make_title(w, cfg):
    """'학습 学习 学習', or '학생 学生' when Chinese and Japanese are identical.
    With korean_script = "romanized": 'hakseup 学习 学習'."""
    parts = [korean_form(w, cfg, "ko", "ko_rom"), w["zh"]]
    if w["ja"] and w["ja"] != w["zh"]:
        parts.append(w["ja"])
    return " ".join(p for p in parts if p)


def make_description(w, cfg):
    """Meaning first (all the home screen shows), then readings, examples, English."""
    readings = " / ".join(p for p in [w["ko_rom"], w["zh_pinyin"], w["ja_rom"]] if p)
    # A missing romanized example (blank ex_ko_rom) is simply left out.
    parts = [w["meaning"], readings,
             korean_form(w, cfg, "ex_ko", "ex_ko_rom"), w["ex_zh"]]
    if cfg.get("include_ja_example", True):
        parts.append(w["ex_ja"])
    parts.append(w["ex_en"])
    parts = [p for p in parts if p]

    sep = " · " if cfg["description_layout"] == "dot" else "<br/>"
    shown_sep_len = 3 if sep == " · " else 1  # a <br/> shows as one line break

    # Optional length cap: keep whole parts while they fit, trim the last one.
    limit = cfg.get("max_description_chars")
    if limit:
        kept, used = [], 0
        for p in parts:
            extra = len(p) + (shown_sep_len if kept else 0)
            if used + extra <= limit:
                kept.append(p)
                used += extra
            else:
                room = limit - used - (shown_sep_len if kept else 0) - 1
                if room > 0:
                    kept.append(p[:room] + "…")
                break
        parts = kept
    return sep.join(parts)


def build_feed(words, cfg, today):
    """Return the feed XML string and a list of warnings."""
    tz = timezone(timedelta(hours=cfg["utc_offset_hours"]))
    start = date.fromisoformat(cfg["start_date"])
    day_number = (today - start).days
    warnings = []

    items = []
    for pos in pick_positions(day_number, cfg["review_offsets_days"]):
        w = words[pos % len(words)]
        shown_on = start + timedelta(days=pos)  # the day this word was "today"
        pub = datetime(shown_on.year, shown_on.month, shown_on.day,
                       cfg["publish_hour"], tzinfo=tz)
        title = make_title(w, cfg)
        if len(title) > cfg["title_warn_chars"]:
            warnings.append(f"title over {cfg['title_warn_chars']} chars "
                            f"(id {w['id']}): {title} [{len(title)}]")
        body = make_description(w, cfg).replace("]]>", "]]&gt;")
        items.append(f"""  <item>
    <title>{escape(title)}</title>
    <link>{escape(cfg['site_url'])}#{shown_on.isoformat()}</link>
    <guid isPermaLink="false">{shown_on.isoformat()}-{escape(w['id'])}</guid>
    <pubDate>{format_datetime(pub)}</pubDate>
    <description><![CDATA[{body}]]></description>
  </item>
""")

    built = datetime(today.year, today.month, today.day, cfg["publish_hour"], tzinfo=tz)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{escape(cfg['feed_title'])}</title>
  <link>{escape(cfg['site_url'])}</link>
  <description>{escape(cfg['feed_description'])}</description>
  <language>en</language>
  <lastBuildDate>{format_datetime(built)}</lastBuildDate>
  <ttl>360</ttl>

{chr(10).join(items)}</channel>
</rss>
"""
    return xml, warnings


def validate(xml, expected_items):
    """Parse the XML and check the RSS basics; raises ValueError on problems."""
    root = ET.fromstring(xml.encode("utf-8"))  # raises ParseError if malformed
    if root.tag != "rss" or root.get("version") != "2.0":
        raise ValueError("root element must be <rss version=\"2.0\">")
    channel = root.find("channel")
    if channel is None:
        raise ValueError("missing <channel>")
    items = channel.findall("item")
    if len(items) != expected_items:
        raise ValueError(f"expected {expected_items} items, got {len(items)}")
    for it in items:
        for tag in ("title", "description", "guid", "pubDate"):
            if not (it.findtext(tag) or "").strip():
                raise ValueError(f"item missing <{tag}>")
    guids = [it.findtext("guid") for it in items]
    if len(set(guids)) != len(guids):
        raise ValueError("duplicate guids")


# ---------------------------------------------------------------- main

def local_today(cfg):
    """Today's date in the feed's timezone; before publish_hour it's still 'yesterday'."""
    now = datetime.now(timezone(timedelta(hours=cfg["utc_offset_hours"])))
    return (now - timedelta(hours=cfg["publish_hour"])).date()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--date", help="build for this date (YYYY-MM-DD) instead of today")
    ap.add_argument("--out", default=str(ROOT / "feed.xml"))
    args = ap.parse_args()

    cfg = load_config()
    words = load_words()
    today = date.fromisoformat(args.date) if args.date else local_today(cfg)

    xml, warnings = build_feed(words, cfg, today)
    validate(xml, len(cfg["review_offsets_days"]))
    for w in warnings:
        print("WARNING:", w, file=sys.stderr)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")
    print(f"wrote {out} for {today} ({len(words)} words in list)")


if __name__ == "__main__":
    main()
