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
 def test_reported_chain_growth_has_separate_stage(self):
  record=dict(COIN,
    network_evidence={"fetched_at":"2026-11-20T09:00:00Z",
       "coin_id":"NovaCoin","last_block_height":120},
    chain_progress={"source":"BackPoW","coin_id":"NovaCoin",
       "blocks_increased":20,"last_observed_at":"2026-11-20T09:00:00Z"})
  result=evaluate("btt:1",record,NOW)
  self.assertEqual(result["stage"],"height_advanced")
  self.assertTrue(result["chain_height_progression"])
  self.assertTrue(any("выросла" in x for x in result["evidence"]))
 def test_foreign_chain_progress_does_not_upgrade(self):
  record=dict(COIN,
    network_evidence={"fetched_at":"2026-11-20T09:00:00Z",
       "coin_id":"NovaCoin","last_block_height":120},
    chain_progress={"source":"BackPoW","coin_id":"OtherCoin",
       "blocks_increased":20,"last_observed_at":"2026-11-20T09:00:00Z"})
  result=evaluate("btt:1",record,NOW)
  self.assertNotEqual(result["stage"],"height_advanced")
 def test_fresh_public_rpc_head_is_evidence_not_payout(self):
  record=dict(COIN,rpc_evidence={
     "provider":"public project JSON-RPC","chain_id":52401,
     "last_block_height":37066,"last_block_time":"2026-11-20T09:40:00Z",
     "checked_at":"2026-11-20T09:45:00Z"})
  r=evaluate("btt:1",record,NOW)
  self.assertEqual(r["stage"],"rpc_head_reported")
  self.assertFalse(r["rpc_height_progression"])
 def test_two_project_rpc_reads_can_upgrade(self):
  record=dict(COIN,rpc_evidence={
     "provider":"public project JSON-RPC","chain_id":52401,
     "last_block_height":37100,"last_block_time":"2026-11-20T09:40:00Z",
     "checked_at":"2026-11-20T09:45:00Z"},
     rpc_progress={"source":"project public JSON-RPC",
       "chain_id":52401,"blocks_increased":34,"last_checked":"2026-11-20T09:45:00Z"})
  self.assertEqual(evaluate("btt:1",record,NOW)["stage"],"rpc_height_advanced")
 def test_no_coin_miner_application(self):
  record={"kind":"repository","title":"x/good-miner",
           "body":"NVIDIA GPU miner for Ethash coin and pool"}
  self.assertEqual(evaluate("gh:22",record,NOW)["stage"],"excluded")
 def test_infinite_pool_metrics_do_not_claim_activity(self):
  record=dict(COIN,pool_evidence={"checked_at":"2026-11-20T09:00:00Z",
      "pools_reported":float("inf"),"blocks_48h_reported":float("inf")})
  self.assertEqual(evaluate("btt:1",record,NOW)["stage"],"announcement_only")
 def test_bulk_status(self):
  subjects={"btt:1":dict(COIN),"gh:22":{"title":"x/miner","body":"GPU miner for ETH","kind":"repository"}}
  counts=evaluate_all(subjects,NOW)
  self.assertEqual(counts["announcement_only"],1)
  self.assertEqual(counts["excluded"],1)
  self.assertIn("mining_readiness",subjects["btt:1"])
if __name__=="__main__": unittest.main()
