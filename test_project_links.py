import unittest
from datetime import datetime, timezone
from project_links import from_telegram_fragment, from_text, format_links, clean_url
from telegram_sources import parse_public_channel
from telegram_commands import digest

NOW = datetime(2026, 11, 20, 5, 0, tzinfo=timezone.utc)

FRAGMENT = '''<div class="tgme_widget_message_wrap">
<div class="tgme_widget_message" data-post="miningrelease/301">
<div class="tgme_widget_message_text">‼️ Coin Name: Filopow<br>Ticker: $FPOW<br>Algo: KawPoW<br> GPU mining PoW mainnet launch</div>
<div class="tgme_widget_message_inline_keyboard">
<a class="tgme_widget_message_inline_button" href="https://filopow.xyz">🌐 Website</a>
<a class="tgme_widget_message_inline_button" href="https://wallet.filopow.xyz">💰 Wallet</a>
<a class="tgme_widget_message_inline_button" href="https://github.com/example/miner">⚒️ Miner</a>
<a class="tgme_widget_message_inline_button" href="https://pool.filopow.xyz">🌋 Pool</a>
<a class="tgme_widget_message_inline_button" href="https://altexplorer.online">🔎 Block Explorer</a>
<a class="tgme_widget_message_inline_button" href="https://discord.gg/ABCxyz">👫 Discord</a>
</div>
<time datetime="2026-11-20T04:00:00+00:00">today</time></div></div>'''

class ProjectLinksTests(unittest.TestCase):
    def test_separate_telegram_buttons(self):
        items = parse_public_channel(FRAGMENT, "miningrelease", NOW)
        self.assertIn("tg:miningrelease:301", items)
        links = items["tg:miningrelease:301"]["links"]
        self.assertEqual(links["discord"], "https://discord.gg/ABCxyz")
        self.assertEqual(links["pool"], "https://pool.filopow.xyz")
        self.assertEqual(links["wallet"], "https://wallet.filopow.xyz")
        self.assertEqual(links["miner"], "https://github.com/example/miner")
        self.assertEqual(links["explorer"], "https://altexplorer.online")
        self.assertEqual(links["website"], "https://filopow.xyz")
    def test_no_cross_message_mix(self):
        first = FRAGMENT.replace("2026-11-20T04:00:00+00:00", "2026-11-20T04:00:00+00:00")
        second = '''<div data-post="miningrelease/302">
        <div class="tgme_widget_message_text">Coin Name: Second GPU PoW miner</div>
        <a href="https://discord.gg/second">Discord</a>
        <time datetime="2026-11-20T04:30:00+00:00"></time></div>'''
        items = parse_public_channel(first + second, "miningrelease", NOW)
        self.assertEqual(items["tg:miningrelease:301"]["links"]["discord"], "https://discord.gg/ABCxyz")
        self.assertEqual(items["tg:miningrelease:302"]["links"]["discord"], "https://discord.gg/second")
    def test_digest_with_project_links(self):
        item = parse_public_channel(FRAGMENT,"miningrelease",NOW)["tg:miningrelease:301"]
        out = digest({"one": item}, NOW)
        self.assertIn("https://discord.gg/ABCxyz", out)
        self.assertIn("https://pool.filopow.xyz", out)
    def test_plain_text_labeled_links(self):
        src = "Discord: https://discord.gg/mycoin\nPool: https://pool.example.org\nExplorer: https://scan.example.org"
        found = from_text(src)
        self.assertEqual(found["discord"],"https://discord.gg/mycoin")
        self.assertEqual(found["pool"],"https://pool.example.org")
        self.assertEqual(found["explorer"],"https://scan.example.org")
    def test_no_fabricated_urls(self):
        self.assertEqual(from_telegram_fragment("<span>Discord: coming soon</span>"),{})
        self.assertEqual(format_links({}),"")
    def test_reject_untrusted_url_schemes(self):
        self.assertIsNone(clean_url("javascript:alert(1)"))
        self.assertIsNone(clean_url("https://user:pass@discord.gg/fake"))
        self.assertIsNone(clean_url("http://discord.gg/fake"))
    def test_no_duplicate_discord(self):
        links = from_telegram_fragment('<a href="https://discord.gg/first">Discord</a><a href="https://discord.gg/second">Discord</a>')
        self.assertEqual(links["discord"],"https://discord.gg/first")

if __name__=="__main__":
    unittest.main()
