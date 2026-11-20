import unittest
from datetime import datetime, timezone
from telegram_sources import parse_public_channel

class TelegramPublicTests(unittest.TestCase):
    def test_current_announcement(self):
        body = '''<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" data-post="miningrelease/301">
        <div class="tgme_widget_message_text js-message_text" dir="auto">
        ‼️ Coin Name: Nova GPU<br> Ticker: $NGPU<br> Algo: KawPow<br> Mainnet launches soon
        </div><time datetime="2026-11-20T04:00:00+00:00">today</time></div></div>'''
        items = parse_public_channel(body, "miningrelease",
                                     datetime(2026,11,20,5,0,tzinfo=timezone.utc))
        self.assertIn("tg:miningrelease:301", items)
        self.assertIn("KawPow", items["tg:miningrelease:301"]["body"])
    def test_old_announcement_ignored(self):
        body = '''<div data-post="miningrelease/1"><div class="tgme_widget_message_text">Coin Name: Very Old Coin Algo: KawPow</div>
        <time datetime="2025-01-01T00:00:00+00:00"></time></div>'''
        items = parse_public_channel(body, "miningrelease",
                                     datetime(2026,11,20,tzinfo=timezone.utc))
        self.assertEqual(items, {})
    def test_landing_page_not_processed(self):
        self.assertEqual(parse_public_channel("<h1>Mining Release</h1>","miningrelease"), {})

if __name__ == "__main__":
    unittest.main()
