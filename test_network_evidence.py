import json
import unittest
from datetime import datetime,timezone
from network_evidence import coin_ids,known_coins,extract_data,update

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
SITEMAP='''<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://backpow.com/Quinvium</loc></url>
<url><loc>https://backpow.com/Pearl</loc></url>
<url><loc>https://evil.example/Pearl</loc></url>
</urlset>'''
def coin():
 return {"title":"[ANN] Quinvium (QU) | Ethash GPU PoW mainnet","kind":"announcement",
 "body":"GPU Ethash proof of work cryptocurrency mainnet"}

class NetworkEvidenceTest(unittest.TestCase):
 def test_sitemap_allowlist(self):
  ids=coin_ids(SITEMAP)
  self.assertEqual(ids["quinvium"],"Quinvium")
  self.assertNotIn("evil",ids)
 def test_only_matching_gpu_coin(self):
  entries={"btt:1":coin(),
     "gh:2":{"title":"person/coin-miner","body":"GPU miner software for Pearl","kind":"repository"}}
  self.assertEqual(known_coins(entries,coin_ids(SITEMAP)),[("btt:1","Quinvium")])
 def test_numeric_missing_is_not_zero(self):
  d=extract_data({"Algorithm":"Ethash","Difficulty":12345,"Nethash":None,"Last block":100})
  self.assertEqual(d["difficulty"],12345)
  self.assertIsNone(d["network_hashrate_hs"])
  self.assertEqual(d["last_block_height"],100)
 def test_cannot_guess_unlisted_coin_ids(self):
  self.assertEqual(known_coins({"btt:1":coin()},{"pearl":"Pearl"}),[])
 def test_bounded_fetches_and_day_cache(self):
  calls=[]
  def fetch(url):
   calls.append(url)
   return SITEMAP if url.endswith("sitemap-coins.xml") else json.dumps(
      {"Algorithm":"Ethash","Difficulty":800,"Nethash":20000,"Last block":120})
  state={"topics":{"btt:1":coin()}}
  one,updated=update(fetch,state["topics"],state,NOW)
  self.assertTrue(updated)
  self.assertEqual(one["successful"],1)
  self.assertEqual(len(calls),2)
  two,updated=update(fetch,state["topics"],{"backpow":one},NOW)
  self.assertFalse(updated)
  self.assertEqual(len(calls),2)
if __name__=="__main__":unittest.main()
