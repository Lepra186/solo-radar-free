import unittest
from datetime import datetime,timezone,timedelta
from mining_economics import energy_eur_day,estimate_daily_coins,assess_economics,calculate_all

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
COIN={"title":"[ANN] Nova GPU PoW Ethash coin","kind":"announcement",
      "body":"GPU PoW Ethash cryptocurrency blockchain","facts":{"algorithm":"Ethash"}}
NETWORK={"fetched_at":"2026-11-20T09:00:00Z","network_hashrate_hs":1e9,
         "block_reward":2.0,"block_time_seconds":60}
MEAS={"device":"RTX 5070 Ti","origin":"measured_hiveos","algorithm":"ethash",
      "hashrate_hs":100e6,"measured_at":"2026-11-20T09:00:00Z",
      "wall_power_w":200,"pool_fee_fraction":0.01}

class Economics(unittest.TestCase):
 def test_energy_is_total_wall_draw_assumption(self):
  self.assertAlmostEqual(energy_eur_day(200),0.48)
  self.assertAlmostEqual(energy_eur_day(300),0.72)
  self.assertIsNone(energy_eur_day(0))
 def test_no_fake_profits_or_hashrate(self):
  econ=assess_economics("btt:1",dict(COIN),NOW)
  self.assertEqual(econ["status"],"insufficient_data")
  self.assertIsNone(econ["net_eur_day"])
  self.assertIsNone(econ["expected_coin_day"])
  self.assertFalse(econ["gpu_measured"])
  self.assertTrue(econ["power_scenarios_are_assumptions"])
 def test_expected_coin_only_with_verified_inputs(self):
  sample=dict(COIN,network_evidence=NETWORK,gpu_measurement=MEAS)
  econ=assess_economics("btt:1",sample,NOW)
  self.assertEqual(econ["status"],"conditional_estimate")
  self.assertAlmostEqual(econ["expected_coin_day"],0.1*1440*2*0.99)
  self.assertEqual(econ["power_cost_eur_day"],0.48)
  self.assertIsNone(econ["net_eur_day"])
 def test_stale_and_cross_algorithm_measurement_rejected(self):
  bad=dict(MEAS,algorithm="kawpow")
  econ=assess_economics("btt:1",dict(COIN,network_evidence=NETWORK,gpu_measurement=bad),NOW)
  self.assertIsNone(econ["expected_coin_day"])
  stale=dict(NETWORK,fetched_at="2026-10-10T09:00:00Z")
  econ2=assess_economics("btt:1",dict(COIN,network_evidence=stale,gpu_measurement=MEAS),NOW)
  self.assertIsNone(econ2["expected_coin_day"])
 def test_pool_fee_required(self):
  bad=dict(MEAS)
  bad.pop("pool_fee_fraction")
  self.assertIsNone(assess_economics("btt:1",dict(COIN,network_evidence=NETWORK,gpu_measurement=bad),NOW)["expected_coin_day"])
 def test_no_miner_software(self):
  rejected={"title":"good-mining/good-miner","body":"NVIDIA GPU miner for Ethash coin",
   "kind":"repository"}
  self.assertEqual(assess_economics("gh:1",rejected,NOW)["status"],"excluded")
 def test_older_geforce_card_is_supported_as_measured_input(self):
  older=dict(MEAS,device="GTX 1080 Ti",hashrate_hs=50e6)
  econ=assess_economics("btt:1",dict(COIN,network_evidence=NETWORK,gpu_measurement=older),NOW)
  self.assertEqual(econ["status"],"conditional_estimate")
  self.assertEqual(econ["measured_devices"][0]["family"],"GTX 10xx")
  self.assertAlmostEqual(econ["expected_coin_day"],0.05*1440*2*0.99)
 def test_mixed_multigpu_rig_hashrate_is_sum_only_of_measurements(self):
  cards=[
   {"device":"GTX 1080 Ti","origin":"measured_hiveos","algorithm":"ethash",
    "hashrate_hs":20e6,"measured_at":"2026-11-20T09:00:00Z"},
   {"device":"RTX 3070","origin":"measured_hiveos","algorithm":"ethash",
    "hashrate_hs":30e6,"measured_at":"2026-11-20T09:00:00Z"},
   {"device":"RTX 4070 SUPER","origin":"measured_hiveos","algorithm":"ethash",
    "hashrate_hs":40e6,"measured_at":"2026-11-20T09:00:00Z"},
   {"device":"RTX 5070 Ti","origin":"measured_hiveos","algorithm":"ethash",
    "hashrate_hs":10e6,"measured_at":"2026-11-20T09:00:00Z"}]
  rig={"devices":cards,"wall_power_w":600,"pool_fee_fraction":0.01}
  result=assess_economics("btt:1",dict(COIN,network_evidence=NETWORK,gpu_measurement=rig),NOW)
  self.assertEqual(result["status"],"conditional_estimate")
  self.assertEqual(result["measured_rig_hashrate_hs"],100e6)
  self.assertEqual(len(result["measured_devices"]),4)
  self.assertAlmostEqual(result["power_cost_eur_day"],1.44)
 def test_incomplete_rig_never_reports_full_rig_yield(self):
  rig={"devices":[dict(MEAS),dict(MEAS,device="RTX 2060",hashrate_hs=None)],
       "wall_power_w":400,"pool_fee_fraction":0.01}
  result=assess_economics("btt:1",dict(COIN,network_evidence=NETWORK,gpu_measurement=rig),NOW)
  self.assertIsNone(result["expected_coin_day"])
  self.assertFalse(result["gpu_measured"])
 def test_bad_inputs(self):
  self.assertIsNone(estimate_daily_coins(0,1000,2,60))
  self.assertIsNone(estimate_daily_coins(2000,1000,2,60))
  self.assertIsNone(estimate_daily_coins(100,1000,2,60,-0.1))
  self.assertIsNone(estimate_daily_coins(100,1000,2,60,1))
  self.assertIsNone(energy_eur_day(200,-0.1))
 def test_batch_does_not_invent_coin_price(self):
  data={"btt:1":dict(COIN)}
  counts=calculate_all(data,NOW)
  self.assertEqual(counts["insufficient_data"],1)
  self.assertIsNone(data["btt:1"]["economics"]["net_eur_day"])

if __name__=="__main__":unittest.main()
