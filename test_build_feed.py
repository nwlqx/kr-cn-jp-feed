"""Tests for build_feed.py. Run with:  python3 -m unittest -v"""
import re
import unittest
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from email.utils import parsedate_to_datetime

import build_feed as bf

CFG = bf.load_config()
WORDS = bf.load_words()
START = date.fromisoformat(CFG["start_date"])
N_ITEMS = len(CFG["review_offsets_days"])
SUMMARY_TITLE_MAX = 24
HANGUL = re.compile("[\uac00-\ud7a3\u1100-\u11ff\u3130-\u318f]")


def items_for(day, cfg=CFG):
    xml, _ = bf.build_feed(WORDS, cfg, day)
    bf.validate(xml, len(cfg["review_offsets_days"]))
    return ET.fromstring(xml).find("channel").findall("item")


class FeedTests(unittest.TestCase):
    # Start date, the early "fill" days, a normal day, and past a full loop.
    DATES = [START + timedelta(days=d)
             for d in (0, 1, 2, 3, 5, 7, 10, len(WORDS), len(WORDS) * 2 + 4)]

    def test_item_count_and_valid_xml(self):
        for d in self.DATES:
            self.assertEqual(len(items_for(d)), N_ITEMS, d)

    def test_newest_first(self):
        for d in self.DATES:
            dates = [parsedate_to_datetime(i.findtext("pubDate")) for i in items_for(d)]
            self.assertEqual(dates, sorted(dates, reverse=True), d)
            self.assertEqual(len(set(dates)), len(dates), d)

    def test_item_one_is_todays_word(self):
        for d in self.DATES:
            n = (d - START).days
            expected = bf.make_title(WORDS[n % len(WORDS)], CFG)
            self.assertEqual(items_for(d)[0].findtext("title"), expected, d)

    def test_review_items_follow_offsets(self):
        d = START + timedelta(days=20)
        titles = [i.findtext("title") for i in items_for(d)]
        expected = [bf.make_title(WORDS[(20 - o) % len(WORDS)], CFG)
                    for o in CFG["review_offsets_days"]]
        self.assertEqual(titles, expected)

    def test_titles_fit_summary_page(self):
        # Over title_warn_chars (home screen) only prints a warning; over
        # ~24 chars (two lines on the Summary page) fails, for both scripts.
        for script in ("hangul", "romanized"):
            cfg = {**CFG, "korean_script": script}
            too_long = [bf.make_title(w, cfg) for w in WORDS
                        if len(bf.make_title(w, cfg)) > SUMMARY_TITLE_MAX]
            self.assertEqual(too_long, [], script)

    def test_identical_zh_ja_shown_once(self):
        w = {"ko": "학생", "ko_rom": "haksaeng", "zh": "学生", "ja": "学生"}
        self.assertEqual(bf.make_title(w, {**CFG, "korean_script": "hangul"}), "학생 学生")
        self.assertEqual(bf.make_title(w, {**CFG, "korean_script": "romanized"}), "haksaeng 学生")

    def test_romanized_has_no_hangul(self):
        cfg = {**CFG, "korean_script": "romanized"}
        xml, _ = bf.build_feed(WORDS, cfg, START + timedelta(days=9))
        self.assertIsNone(HANGUL.search(xml), "Hangul found in romanized feed")
        for w in WORDS:
            self.assertTrue(w["ko_rom"] and w["ex_ko_rom"], f"id {w['id']} missing romanization")

    def test_layouts_and_length_cap(self):
        w = WORDS[0]
        dot = bf.make_description(w, {**CFG, "description_layout": "dot"})
        self.assertIn(" · ", dot)
        self.assertTrue(dot.startswith(w["meaning"]))
        capped = bf.make_description(w, {**CFG, "description_layout": "dot",
                                          "max_description_chars": 40})
        self.assertLessEqual(len(capped), 40)
        no_ja = bf.make_description(w, {**CFG, "include_ja_example": False})
        self.assertNotIn(w["ex_ja"], no_ja)


if __name__ == "__main__":
    unittest.main()
