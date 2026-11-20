import unittest
from gpu_families import identify_model,summary,FAMILIES

class Coverage(unittest.TestCase):
 def test_all_five_series(self):
  cases={
    "GeForce GTX 1060":"GTX 10xx",
    "GTX 1080 Ti":"GTX 10xx",
    "RTX 2060 SUPER":"RTX 20xx",
    "GeForce RTX 3070 Ti":"RTX 30xx",
    "RTX 4090":"RTX 40xx",
    "RTX 5070 Ti":"RTX 50xx",
    "RTX 5090":"RTX 50xx"}
  for device,family in cases.items():
   with self.subTest(device=device):
    self.assertEqual(identify_model(device)["family"],family)
 def test_no_gpu_assumed_from_random_string(self):
  for bad in ("AMD RX 6800","GTX 5070 Ti","RTX 1060","RTX 6090","NVIDIA GPU"):
   with self.subTest(device=bad):
    self.assertIsNone(identify_model(bad))
 def test_all_families_without_hardware_proof(self):
  r=summary({"title":"[ANN] Ethash GPU PoW coin"})
  self.assertEqual(len(r["family_status"]),5)
  self.assertTrue(all(x["status"]=="not_verified" for x in r["family_status"]))
 def test_claims_are_separate_from_measured_tests(self):
  r=summary({"gpu_support_evidence":[
    {"device":"RTX 3060","status":"developer_claimed","source_url":"https://example.org/announcement"},
    {"device":"GTX 1080 Ti","status":"tested","source_url":"https://example.org/rig-test"},
    {"device":"RTX 4090","status":"tested","source_url":"file:///private/local"}]})
  statuses={x["family"]:x["status"] for x in r["family_status"]}
  self.assertEqual(statuses["RTX 30xx"],"developer_claim_only")
  self.assertEqual(statuses["GTX 10xx"],"tested_model_reported")
  self.assertEqual(statuses["RTX 40xx"],"not_verified")
if __name__=="__main__":unittest.main()
