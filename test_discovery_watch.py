import json
import unittest
from datetime import datetime, timezone, timedelta
from urllib.parse import unquote
from github_discovery import gather,refresh_tracked
from project_watch import reconcile

NOW=datetime(2026,11,20,8,0,tzinfo=timezone.utc)
REPO={"id":101,"full_name":"newcoin/gpu-pow","created_at":"2026-11-19T08:00:00Z",
      "pushed_at":"2026-11-20T07:00:00Z","html_url":"https://github.com/newcoin/gpu-pow",
      "description":"GPU proof of work KawPow coin mainnet launch with SOLO stratum pool",
      "fork":False,"archived":False,"stargazers_count":7,"forks_count":2}
class GitHubDiscoveryTests(unittest.TestCase):
    def test_multiple_queries_deduplicate(self):
        urls=[]
        def fake_fetch(url):
            urls.append(unquote(url))
            return json.dumps({"items":[REPO,dict(REPO,id=102,full_name="bad/fork",fork=True)]})
        found,count=gather(fake_fetch,NOW)
        self.assertEqual(count,3)
        self.assertEqual(len(urls),3)
        self.assertEqual(len(found),1)
        self.assertEqual(found["gh:101"]["github"]["stars"],7)
        self.assertEqual(found["gh:101"]["kind"],"repository")
        self.assertIn("repo_created",found["gh:101"])
    def test_public_repo_update_without_following(self):
        topics={"gh:101":{"url":REPO["html_url"],"kind":"repository","title":"GPU PoW coin",
                 "github":{"name":REPO["full_name"]}}}
        called=[]
        def fetch(url):
            called.append(url)
            return json.dumps(REPO)
        n=refresh_tracked(fetch,topics,["gh:101"],NOW)
        self.assertEqual(n,1)
        self.assertEqual(topics["gh:101"]["github"]["stars"],7)
        self.assertEqual(called,["https://api.github.com/repos/newcoin/gpu-pow"])
    def test_automatic_add_remove_local_monitoring(self):
        facts={"algorithm":"KawPow","gpu_mentioned":True,
               "publication_utc":"2026-11-19T08:00:00+00:00",
               "solo_mentioned":True,"pool_mentioned":True}
        body="GPU proof of work KawPow mainnet launch SOLO mining pool"
        topics={"tg:test:1":{"title":"New GPU KawPow PoW coin","body":body,
                "kind":"announcement","date":"2026-11-19T08:00:00Z",
                "facts":facts,"url":"https://t.me/test/1"}}
        current,stats=reconcile(topics,{},NOW)
        self.assertEqual(stats["added"],1)
        self.assertIn("tg:test:1",current)
        topics["tg:test:1"]["title"]="GPU miner v1.0 software release"
        nxt,changes=reconcile(topics,current,NOW)
        self.assertNotIn("tg:test:1",nxt)
        self.assertEqual(changes["removed"],1)
    def test_stale_project_does_not_stay_tracked(self):
        old={"title":"GPU KawPow PoW coin","body":"GPU KawPow PoW solo pool",
             "kind":"announcement","date":"2026-04-01T00:00:00Z"}
        prev={"tg:old":{"name":"old","score":10}}
        result,stats=reconcile({"tg:old":old},prev,NOW)
        self.assertEqual(result,{})
        self.assertEqual(stats["removed"],1)
if __name__=="__main__":
    unittest.main()
