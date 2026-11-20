import unittest
from datetime import datetime,timezone
from discord_sources import parse_channels,parse_messages,fetch_channels
from mining_scan_source import parse_directory,matches_for,refresh

NOW=datetime(2026,11,20,9,0,tzinfo=timezone.utc)
class DiscordTest(unittest.TestCase):
 def test_channels_only_explicit_ids(self):
  self.assertEqual(parse_channels("123456789012345678, 123456789012345678, invalid,987654321012345678"),
                   ["123456789012345678","987654321012345678"])
 def test_announcement_embeds_and_links(self):
  rows=[{"id":"123456789012345679","guild_id":"123456789012345680",
    "timestamp":"2026-11-20T08:00:00Z","content":"",
    "embeds":[{"title":"Coin Name: BlueCoin GPU PoW Ethash mainnet",
      "description":"New GPU cryptocurrency with Ethash proof of work",
      "fields":[{"name":"Pool","value":"https://pool.example.org"}]}]}]
  result=parse_messages(rows,"123456789012345678",NOW)
  self.assertEqual(len(result),1)
  data=next(iter(result.values()))
  self.assertIn("BlueCoin",data["body"])
  self.assertIn("discord.com/channels",data["url"])
 def test_not_configured_no_calls(self):
  rows,status=fetch_channels("","","",fetcher=lambda *_:self.fail("Unexpected request"))
  self.assertFalse(rows)
  self.assertEqual(status["status"],"not_configured")
 def test_permission_denied_logged_only_as_type(self):
  def deny(*_):raise PermissionError("secret embedded in error")
  result,status=fetch_channels("hidden-token","123456789012345678",NOW,fetcher=deny)
  self.assertEqual(result,{})
  self.assertEqual(status["status"],"unavailable")
  self.assertEqual(status["failures"],["PermissionError"])
class MiningScanTest(unittest.TestCase):
 def test_parse_and_filter_algorithms(self):
  payload={"meta":{"generated_at":"2026-11-20T08:55:00Z","state":"operational","stale":False},
  "data":[{"symbol":"NEW","coin_name":"NewCoin","algorithm":"Ethash",
     "pool_count":2,"blocks_48h":3,"last_block_at":"2026-11-20T08:00:00Z"},
    {"symbol":"BTC","coin_name":"Bitcoin","algorithm":"SHA-256","pool_count":3}]}
  listing=parse_directory(payload)
  self.assertEqual(len(listing["coins"]),1)
  topic={"btt:1":{"title":"[ANN] NewCoin (NEW) GPU PoW Ethash mainnet","kind":"announcement",
   "body":"GPU mineable NewCoin proof of work","facts":{"ticker":"NEW"}}}
  matched=matches_for(topic,listing)
  self.assertEqual(matched["btt:1"]["blocks_48h_reported"],3)
 def test_no_fake_zero_if_missing(self):
  payload={"meta":{"state":"operational","stale":False},"data":[{"symbol":"ABC","coin_name":"AlphaCoin","algorithm":"KawPow"}]}
  self.assertIsNone(parse_directory(payload)["coins"][0]["blocks_48h"])
 def test_stale_not_accepted(self):
  with self.assertRaises(ValueError):
   parse_directory({"meta":{"stale":True},"data":[]})
if __name__=="__main__":unittest.main()
