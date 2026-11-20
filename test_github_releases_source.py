import json
import unittest
from datetime import datetime,timezone
from github_releases_source import repo_name,check_releases

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)

def project(name="someorg/gpucoin"):
 return {"title":name,"body":"GPU Ethash proof of work blockchain cryptocurrency mainnet",
         "kind":"repository","url":"https://github.com/"+name}

class GitHubReleasesTest(unittest.TestCase):
 def test_extract_repo_name(self):
  self.assertEqual(repo_name(project()),"someorg/gpucoin")
  self.assertIsNone(repo_name({"url":"https://other.example.com/project"}))
 def test_coin_only_and_recent_releases(self):
  topics={
   "gh:101":project(),
   "gh:102":{"title":"dev/kobold-miner","body":"NVIDIA GPU miner for Pearl coin",
      "kind":"repository","url":"https://github.com/dev/kobold-miner"}}
  urls=[]
  def fetch(url):
   urls.append(url)
   return json.dumps([
    {"name":"Coin mainnet wallet v1","published_at":"2026-11-19T12:00:00Z",
      "html_url":"https://github.com/someorg/gpucoin/releases/tag/v1"},
    {"name":"Old release","published_at":"2024-01-01T00:00:00Z",
      "html_url":"https://github.com/someorg/gpucoin/releases/tag/old"},
    {"name":"Development preview","published_at":"2026-11-19T12:00:00Z","prerelease":True}
   ])
  summary=check_releases(fetch,topics,NOW)
  self.assertEqual(summary,{"checked":1,"projects_with_releases":1})
  self.assertEqual(len(urls),1)
  self.assertIn("github_release_evidence",topics["gh:101"])
  self.assertNotIn("github_release_evidence",topics["gh:102"])
 def test_release_does_not_create_coin(self):
  noncoins={"gh:102":{"title":"x/miner","body":"GPU miner for KawPow coin",
          "kind":"repository","url":"https://github.com/x/miner"}}
  s=check_releases(lambda _:self.fail("no fetch"),noncoins,NOW)
  self.assertEqual(s["checked"],0)

if __name__=="__main__":unittest.main()
