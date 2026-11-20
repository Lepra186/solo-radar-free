import unittest
from datetime import datetime,timezone,timedelta
from mineability import evaluate,evaluate_all

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
COIN={"kind":"announcement","title":"[ANN] NovaCoin (NVC) GPU PoW Ethash mainnet",
      "body":"New GPU PoW blockchain coin mining Ethash"}
class MineabilityTests(unittest.TestCase):
 def test_announcement_not_mineable_proof(self):
  r=evaluate("btt:1",dict(COIN),NOW)
  self.assertEqual(r["stage"],"announcement_only")
  self.assertEqual(len(r["gpu_family_coverage"]["family_status"]),5)
  self.assertTrue(all(x["status"]=="not_verified" for x in r["gpu_family_coverage"]["family_status"]))
 def test_catalog_listing_not_proof(self):
  record=dict(COIN,pool_evidence={"checked_at":"2026-11-20T09:00:00Z",
                                  "pools_reported":2,"blocks_48h_reported":0})
  r=evaluate("btt:1",record,NOW)
  self.assertEqual(r["stage"],"pool_listed")
  self.assertTrue(any("блоки" in x for x in r["missing"]))
 def test_recent_block_is_reported_not_confirmed(self):
  record=dict(COIN,pool_evidence={"checked_at":"2026-11-20T09:00:00Z",
       "pools_reported":1,"blocks_48h_reported":1,
       "last_block_at":"2026-11-20T09:05:00Z"})
  r=evaluate("btt:1",record,NOW)
  self.assertEqual(r["stage"],"activity_reported")
  self.assertIn("сообщения",r["label"])
 def test_stale_data_cannot_claim_activity(self):
  record=dict(COIN,pool_evidence={"checked_at":"2026-11-01T09:00:00Z",
       "pools_reported":4,"blocks_48h_reported":200,
       "last_block_at":"2026-11-20T09:05:00Z"})
  self.assertEqual(evaluate("btt:1",record,NOW)["stage"],"announcement_only")
 def test_network_height_with_recent_snapshot(self):
  record=dict(COIN,network_evidence={"fetched_at":"2026-11-20T08:00:00Z",
            "last_block_height":1234,"difficulty":654})
  self.assertEqual(evaluate("btt:1",record,NOW)["stage"],"activity_reported")
 def test_no_coin_miner_application(self):
  record={"kind":"repository","title":"x/good-miner",
           "body":"NVIDIA GPU miner for Ethash coin and pool"}
  self.assertEqual(evaluate("gh:22",record,NOW)["stage"],"excluded")
 def test_bulk_status(self):
  subjects={"btt:1":dict(COIN),"gh:22":{"title":"x/miner","body":"GPU miner for ETH","kind":"repository"}}
  counts=evaluate_all(subjects,NOW)
  self.assertEqual(counts["announcement_only"],1)
  self.assertEqual(counts["excluded"],1)
  self.assertIn("mining_readiness",subjects["btt:1"])
if __name__=="__main__": unittest.main()
