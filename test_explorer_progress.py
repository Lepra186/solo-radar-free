import unittest
from datetime import datetime,timezone,timedelta
from explorer_progress import measure,update

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
def topic(height,stamp="2026-11-20T09:59:00Z",provider="https://coin.blockscout.com",block_time="2026-11-20T09:10:00Z"):
 return {"coin_class":"coin_candidate","explorer_evidence":{
   "explorer":provider,"checked_at":stamp,"last_block_height":height,
   "last_block_time":block_time,"identity_verified":False}}
class ExplorerGrowth(unittest.TestCase):
 def test_one_snapshot_baseline_not_evidence(self):
  a={"gh:1":topic(100)}
  history,stats=update(a,{},NOW)
  self.assertEqual(stats["baselines"],1)
  self.assertNotIn("explorer_progress",a["gh:1"])
 def test_delta_with_matching_source(self):
  a={"gh:1":topic(100,"2026-11-20T09:20:00Z")}
  history,_=update(a,{},NOW)
  latest={"gh:1":topic(112,"2026-11-20T09:50:00Z",block_time="2026-11-20T09:45:00Z")}
  _,stats=update(latest,history,NOW)
  self.assertEqual(stats["increased"],1)
  self.assertEqual(latest["gh:1"]["explorer_progress"]["delta_blocks"],12)
  self.assertFalse(latest["gh:1"]["explorer_progress"]["identity_verified"])
 def test_different_explorer_and_same_height_no_false_progress(self):
  a={"gh:1":topic(100,"2026-11-20T09:20:00Z")}
  history,_=update(a,{},NOW)
  other={"gh:1":topic(999,"2026-11-20T09:50:00Z","https://other.blockscout.com")}
  self.assertEqual(update(other,history,NOW)[1]["increased"],0)
  same={"gh:1":topic(100,"2026-11-20T09:50:00Z")}
  self.assertEqual(update(same,history,NOW)[1]["stalled"],1)
 def test_height_rise_without_new_block_time_is_not_proof(self):
  first={"gh:1":topic(100,"2026-11-20T09:20:00Z")}
  history,_=update(first,{},NOW)
  later={"gh:1":topic(200,"2026-11-20T09:50:00Z")}
  _,stats=update(later,history,NOW)
  self.assertEqual(stats["increased"],0)
  self.assertNotIn("explorer_progress",later["gh:1"])
 def test_future_block_timestamp_rejected(self):
  record=topic(100,"2026-11-20T09:20:00Z",block_time="2026-11-20T09:45:00Z")
  self.assertIsNone(measure(record,NOW))
 def test_stale_block_or_missing_identity_not_accepted(self):
  a=topic(100)
  a["explorer_evidence"]["last_block_time"]="2026-10-01T00:00:00Z"
  self.assertIsNone(measure(a,NOW))
  a["coin_class"]="non_coin"
  self.assertEqual(update({"gh:1":a},{},NOW)[1]["eligible"],0)
if __name__=="__main__":unittest.main()
