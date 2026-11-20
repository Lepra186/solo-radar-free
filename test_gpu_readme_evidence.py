import base64
import json
import unittest
from datetime import datetime,timezone
from gpu_readme_evidence import evidence_from_readme,read_public_readme,enrich

NOW=datetime(2026,11,20,11,0,tzinfo=timezone.utc)
COIN={"title":"myteam/gpucoin","body":"GPU Ethash proof of work cryptocurrency blockchain",
      "kind":"repository","url":"https://github.com/myteam/gpucoin"}
class ReadmeEvidence(unittest.TestCase):
 def test_claims_not_hardware_benchmark(self):
  rows=evidence_from_readme("Supported GPUs: GTX 1060, RTX 2060, RTX 3070 Ti, RTX 4080, RTX 5070 Ti",
                           "https://github.com/myteam/gpucoin#readme")
  self.assertEqual(len(rows),5)
  self.assertTrue(all(x["status"]=="developer_claimed" for x in rows))
 def test_real_readme_from_api(self):
  content=base64.b64encode(b"Miner compatible cards: GTX 1080 Ti and RTX 3060").decode()
  def fetch(url):
   self.assertEqual(url,"https://api.github.com/repos/myteam/gpucoin/readme")
   return json.dumps({"encoding":"base64","content":content,
     "html_url":"https://github.com/myteam/gpucoin/blob/main/README.md"})
  result=read_public_readme(fetch,"myteam/gpucoin")
  self.assertEqual(len(result),2)
 def test_only_coin_repos_and_cache(self):
  data={"gh:1":dict(COIN),
        "gh:2":{"title":"goodminer/gpu-miner","body":"GPU miner for Ethash coin",
                "kind":"repository","url":"https://github.com/goodminer/gpu-miner"}}
  calls=[]
  def fetch(url):
   calls.append(url)
   return json.dumps({"encoding":"base64","content":base64.b64encode(
      b"Compatible models GTX 1080 Ti and RTX 5090").decode()})
  status=enrich(fetch,data,NOW)
  self.assertEqual(status["readmes_checked"],1)
  self.assertEqual(len(calls),1)
  self.assertEqual(len(data["gh:1"]["gpu_support_evidence"]),2)
  again=enrich(fetch,data,NOW)
  self.assertEqual(again["readmes_checked"],0)
 def test_no_guesses_from_gpu_friendly_claim(self):
  self.assertEqual(evidence_from_readme("GPU friendly Nvidia support",
      "https://github.com/a/b#readme"),[])
 def test_untrusted_or_huge_readme_rejected(self):
  bad=json.dumps({"encoding":"base64","content":"QQ"*200000})
  self.assertEqual(read_public_readme(lambda _:bad,"myteam/gpucoin"),[])
if __name__=="__main__":unittest.main()
