import json
import unittest
from datetime import datetime, timezone
from pool_validation import parse_pool_directory,match_pools,stratum_by_coin,update

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
POOL={"id":"p1","name":"New Pool","domain":"newpool.example",
      "status":"confirmed","coins":["NEXC"],"fee":1.5,
      "payout_schemes":["SOLO","PPLNS"],"miners":10,
      "blocks_found":12345,"last_metric_at":"2026-11-20T09:00:00Z"}
PAYLOAD={"meta":{"generated_at":"2026-11-20T09:01:00Z","state":"operational","stale":False},
         "data":[POOL]}
PROJECT={"coin_class":"coin_candidate","title":"[ANN] NEX Chain (NEXC) GPU PoW Ethash",
         "pool_evidence":{"symbol":"NEXC","name":"NEX Chain"}}

class Pools(unittest.TestCase):
 def test_real_directory_parses_only_confirmed_pools(self):
  data=parse_pool_directory(PAYLOAD,NOW)
  self.assertEqual(len(data["pools"]),1)
  self.assertTrue(data["pools"][0]["fresh_metrics"])
  self.assertNotIn("blocks_found",data["pools"][0])
 def test_poolwide_does_not_prove_coin_mined(self):
  records=match_pools({"btt:1":PROJECT},parse_pool_directory(PAYLOAD,NOW),NOW)
  entry=records["btt:1"]["pools"][0]
  self.assertEqual(entry["fee_percent_poolwide"],1.5)
  self.assertEqual(entry["payout_schemes_poolwide"],["SOLO","PPLNS"])
  self.assertEqual(entry["stratum"],"не подтверждён")
  self.assertNotIn("blocks_24h",entry)
 def test_no_ambiguous_ticker_matches_without_name(self):
  records=match_pools({"btt:1":{**PROJECT,"title":"[ANN] Other Coin NEXC"}},parse_pool_directory(PAYLOAD,NOW),NOW)
  self.assertEqual(records,{})
 def test_no_old_pool_data(self):
  stale={"meta":{"generated_at":"2026-11-01T00:00:00Z","stale":False},"data":[POOL]}
  with self.assertRaises(ValueError):
   parse_pool_directory(stale,NOW)
 def test_pool_coin_endpoint_requires_exact_name_and_ticker(self):
  info=match_pools({"btt:1":PROJECT},parse_pool_directory(PAYLOAD,NOW),NOW)["btt:1"]
  visits=[]
  def fetch(url):
   visits.append(url)
   return json.dumps({"data":[
    {"symbol":"NEXC","coin_name":"Other Coin",
     "stratum_endpoints":[{"url":"stratum+tcp://bad.example:1111"}]},
    {"symbol":"NEXC","coin_name":"NEX Chain",
     "stratum_endpoints":[{"url":"stratum+tcp://pool.example:3333"},
                           {"url":"https://phishing.example/secret"},
                           {"url":"stratum+tcp://user:pass@pool.example:4444"}]}]})
  checked=stratum_by_coin(fetch,info)
  self.assertEqual(checked,1)
  self.assertEqual(info["pools"][0]["stratum_endpoints"],["stratum+tcp://pool.example:3333"])
  self.assertEqual(visits,["https://mining-scan.com/pools/newpool.example/coins"])
 def test_stale_pool_catalog_throttled(self):
  calls=[]
  stale={"meta":{"generated_at":"2026-11-01T09:00:00Z","stale":False},"data":[POOL]}
  def fetch(url):
   calls.append(url)
   return json.dumps(stale)
  result,changed=update(fetch,{},NOW)
  self.assertTrue(changed)
  self.assertEqual(result["status"],"source_unavailable")
  next_result,changed=update(fetch,{"pool_directory":result},NOW)
  self.assertFalse(changed)
  self.assertEqual(len(calls),1)
 def test_stale_cache_refresh(self):
  count=[]
  def fetch(url):
   count.append(url)
   return json.dumps(PAYLOAD)
  data,changed=update(fetch,{},NOW)
  self.assertTrue(changed)
  same,changed=update(fetch,{"pool_directory":data},NOW)
  self.assertFalse(changed)
  self.assertEqual(len(count),1)

if __name__=="__main__":unittest.main()
