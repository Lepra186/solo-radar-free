import unittest
from datetime import datetime,timezone
from evidence_alerts import transitions,confirmed

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
COIN={"title":"[ANN] NEX Chain GPU PoW Ethash coin","body":"Ethash GPU blockchain coin",
      "kind":"announcement","url":"https://bitcointalk.org/index.php?topic=100",
      "pool_evidence":{"source":"Mining Scan","last_block_at":"2026-11-20T09:30:00Z"},
      "mining_readiness":{"stage":"activity_reported",
          "evidence":["По данным каталога недавно найден блок"]}}
class EvidenceAlerts(unittest.TestCase):
 def test_initial_baseline_sends_nothing(self):
  events,history=transitions({"btt:1":COIN},{},NOW)
  self.assertEqual(events,[])
  self.assertEqual(history["btt:1"]["last_stage"],"activity_reported")
 def test_transition_announces_once(self):
  before={"btt:1":{"last_stage":"announcement_only","last_alert_marker":""}}
  events,history=transitions({"btt:1":COIN},before,NOW)
  self.assertEqual(len(events),1)
  self.assertIn("Не проверены RTX 5070 Ti",events[0][2])
  confirmed(history,events[0][0],events[0][1])
  next_events,_=transitions({"btt:1":COIN},history,NOW)
  self.assertEqual(next_events,[])
 def test_stale_cycle_does_not_repeat_unchanged_evidence(self):
  marker=transitions({"btt:1":COIN},
      {"btt:1":{"last_stage":"announcement_only"}},NOW)[0][0][1]
  before={"btt:1":{"last_stage":"announcement_only","last_alert_marker":marker}}
  events,_=transitions({"btt:1":COIN},before,NOW)
  self.assertEqual(events,[])
 def test_no_miner_software(self):
  bad={"title":"goodminer/gpu-miner","body":"GPU miner for Ethash coin",
       "kind":"repository","mining_readiness":{"stage":"activity_reported"}}
  events,state=transitions({"gh:1":bad},{},NOW)
  self.assertEqual(events,[])
  self.assertEqual(state,{})
if __name__=="__main__":unittest.main()
