import base64
import json
import unittest
from datetime import datetime,timezone,timedelta
from explorer_source import official_blockscout,candidate_from_readme,latest_blocks,verify

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
COIN={"title":"ExampleCoin (EXC) GPU Ethash PoW blockchain",
      "body":"GPU Ethash PoW cryptocurrency blockchain","kind":"repository",
      "url":"https://github.com/example/examplecoin","coin_class":"coin_candidate"}
API={"items":[{"height":100,"timestamp":"2026-11-20T09:59:00Z",
               "hash":"0x123","type":"block"},
              {"height":99,"timestamp":"2026-11-20T09:57:00Z",
               "hash":"0x122","type":"block"}]}

class ExplorerTest(unittest.TestCase):
 def test_only_public_hosted_blockscout(self):
  self.assertEqual(official_blockscout("https://exc.blockscout.com/blocks"),"https://exc.blockscout.com")
  for bad in ("http://exc.blockscout.com","https://blockscout.com",
              "https://blockscout.com.evil.test","https://127.0.0.1",
              "https://localhost","https://user:pass@exc.blockscout.com",
              "https://exc.blockscout.com:8080","https://10.0.0.1",
              "https://evil.example"):
   with self.subTest(url=bad):self.assertIsNone(official_blockscout(bad))
 def test_explicit_link_not_guessed(self):
  self.assertEqual(candidate_from_readme(
   "Explorer: https://exc.blockscout.com/blocks\\nPool: https://pool.example.org"),
   "https://exc.blockscout.com")
  self.assertIsNone(candidate_from_readme("Use Ethash on a GPU with any miner"))
 def test_latest_blocks_timestamp_and_canonical(self):
  r=latest_blocks(API,NOW)
  self.assertEqual(r["last_block_height"],100)
  self.assertEqual(r["blocks_in_response"],2)
  with self.assertRaises(ValueError):
   latest_blocks({"items":[{"height":300,
       "timestamp":"2026-01-01T10:00:00Z","type":"block"}]},NOW)
  with self.assertRaises(ValueError):
   latest_blocks({"items":[{"height":300,
       "timestamp":"2026-11-20T09:59:00Z","type":"reorg"}]},NOW)
 def test_no_unrelated_coin_or_miner_and_no_fake_chain_verification(self):
  records={"gh:1":dict(COIN),"gh:2":{"title":"x/gpu-miner","body":"GPU miner for PoW coin",
            "kind":"repository","url":"https://github.com/x/gpu-miner","coin_class":"non_coin"}}
  urls=[]
  def fetch(url):
   urls.append(url)
   if url.endswith("/readme"):
    return json.dumps({"encoding":"base64","content":base64.b64encode(
      b"Explorer: https://exc.blockscout.com/blocks").decode()})
   if url=="https://exc.blockscout.com/api/v2/blocks":return json.dumps(API)
   self.fail("unexpected URL "+url)
  s=verify(fetch,records,{},NOW)
  self.assertEqual(s["explorers_reporting_recent_blocks"],1)
  self.assertEqual(len(urls),2)
  self.assertFalse(records["gh:1"]["explorer_evidence"]["identity_verified"])
  self.assertNotIn("explorer_evidence",records["gh:2"])
 def test_cached_scan_does_not_spam_explorer(self):
  record=dict(COIN,explorer_origin={"url":"https://exc.blockscout.com"},
         explorer_evidence={"checked_at":"2026-11-20T09:50:00Z"})
  s=verify(lambda _:self.fail("unexpected repeated request"),{"gh:1":record},{},NOW)
  self.assertEqual(s["api_checked"],0)
if __name__=="__main__":unittest.main()
