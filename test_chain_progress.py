import unittest
from datetime import datetime,timezone,timedelta
from chain_progress import reconcile,record

NOW=datetime(2026,11,20,12,0,tzinfo=timezone.utc)
def coin(when="2026-11-20T12:00:00Z",height=120,coin_id="ExampleCoin"):
    return {"coin_class":"coin_candidate","title":"[ANN] ExampleCoin GPU PoW Ethash",
     "network_evidence":{"coin_id":coin_id,"fetched_at":when,"last_block_height":height}}

class ChainProgressTests(unittest.TestCase):
 def test_initial_snapshot_does_not_claim_active_chain(self):
  found,history,stats=reconcile({"btt:1":coin()}, {}, NOW)
  self.assertEqual(found,{})
  self.assertEqual(stats["new_baselines"],1)
  self.assertEqual(history["btt:1"]["baseline"]["height"],120)
 def test_two_snapshots_height_advance(self):
  _,prior,_=reconcile({"btt:1":coin("2026-11-20T11:20:00Z",100)}, {}, NOW)
  found,_,stats=reconcile({"btt:1":coin("2026-11-20T11:50:00Z",125)}, prior,NOW)
  self.assertEqual(found["btt:1"]["blocks_increased"],25)
  self.assertEqual(stats["advanced"],1)
 def test_same_timestamp_does_not_count(self):
  _,prior,_=reconcile({"btt:1":coin("2026-11-20T11:40:00Z",100)}, {}, NOW)
  found,_,stats=reconcile({"btt:1":coin("2026-11-20T11:40:00Z",999)},prior,NOW)
  self.assertEqual(found,{})
  self.assertEqual(stats["advanced"],0)
 def test_same_height_does_not_count(self):
  _,prior,_=reconcile({"btt:1":coin("2026-11-20T11:10:00Z",100)}, {}, NOW)
  found,_,stats=reconcile({"btt:1":coin("2026-11-20T11:40:00Z",100)},prior,NOW)
  self.assertEqual(found,{})
  self.assertEqual(stats["unchanged"],1)
 def test_different_coin_id_or_height_reorg_rebaseline(self):
  _,prior,_=reconcile({"btt:1":coin("2026-11-20T11:00:00Z",100)}, {}, NOW)
  found,next_history,_=reconcile({"btt:1":coin("2026-11-20T11:30:00Z",110,"OtherCoin")},prior,NOW)
  self.assertEqual(found,{})
  self.assertEqual(next_history["btt:1"]["baseline"]["coin_id"],"OtherCoin")
  found,_,stats=reconcile({"btt:1":coin("2026-11-20T11:50:00Z",105,"OtherCoin")},next_history,NOW)
  self.assertEqual(found,{})
  self.assertEqual(stats["anomalies"],1)
 def test_old_data_not_active(self):
  found,history,stats=reconcile({"btt:1":coin("2026-11-01T11:00:00Z",999)}, {}, NOW)
  self.assertEqual(stats["eligible"],0)
  self.assertEqual(history,{})
 def test_mining_software_stays_out(self):
  bad=coin()
  bad["coin_class"]="non_coin"
  self.assertEqual(reconcile({"gh:1":bad},{},NOW)[0],{})
 def test_forged_negative_and_fractional_height_ignored(self):
  self.assertIsNone(record(coin(height=-12)["network_evidence"]))
  self.assertIsNone(record(coin(height=20.5)["network_evidence"]))
if __name__=="__main__":unittest.main()
