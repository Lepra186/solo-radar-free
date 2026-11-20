import json
import unittest
from datetime import datetime,timezone
from coincalculators_source import directory,matched,update

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
DATA={"coins":{
  "NEX Chain":{"tag":"NEXC","algorithm":"Ethash","nethash":10000000,
              "block_time":60,"block_reward":2,"difficulty":"10M"},
  "Fake Same Ticker":{"tag":"NEXC","algorithm":"Ethash","nethash":9},
  "Bitcoin":{"tag":"BTC","algorithm":"SHA-256","nethash":1e18}
}}
ITEM={"coin_class":"coin_candidate",
      "title":"[ANN] NEX Chain (NEXC) GPU PoW Ethash",
      "facts":{"algorithm":"Ethash"},
      "pool_evidence":{"name":"NEX Chain","symbol":"NEXC"}}
class CoinCalculatorsTests(unittest.TestCase):
 def test_filter_gpu_algo_only(self):
  rows=directory(DATA,NOW)["coins"]
  self.assertEqual(len(rows),2)
  self.assertTrue(all(r["ticker"]=="NEXC" for r in rows))
 def test_exact_identity_not_ticker_only(self):
  m=matched({"btt:1":ITEM},directory(DATA,NOW),NOW)
  self.assertEqual(m["btt:1"]["network_hashrate_hs_reported"],10000000)
  self.assertTrue(m["btt:1"]["provider_time_unknown"])
  self.assertNotIn("network_evidence",m["btt:1"])
 def test_ambiguous_algorithm_not_accepted(self):
  wrong={**ITEM,"facts":{"algorithm":"KawPow"}}
  self.assertEqual(matched({"btt:1":wrong},directory(DATA,NOW),NOW),{})
 def test_no_unverified_coin_name(self):
  unknown={**ITEM,"pool_evidence":{"symbol":"NEXC"}}
  self.assertEqual(matched({"btt:1":unknown},directory(DATA,NOW),NOW),{})
 def test_preserve_nulls(self):
  r=directory({"coins":{"XenoCoin":{"tag":"XEN","algorithm":"Ethash"}}},NOW)
  self.assertIsNone(r["coins"][0]["nethash_hs_reported"])
 def test_cache_without_repeated_fetch(self):
  seen=[]
  def fetch(url):
   seen.append(url)
   return json.dumps(DATA)
  first,changed=update(fetch,{},NOW)
  self.assertTrue(changed)
  second,changed=update(fetch,{"coin_calculators":first},NOW)
  self.assertFalse(changed)
  self.assertEqual(len(seen),1)
if __name__=="__main__":unittest.main()
