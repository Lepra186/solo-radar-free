import unittest
from datetime import datetime, timezone, timedelta
from research_agent import analyze, examine, report

NOW=datetime(2026,11,20,8,0,tzinfo=timezone.utc)
PROJECT={
 "title":"Coin Name: New GPU PoW Coin | KawPow Mainnet",
 "body":"GPU proof of work KawPow mainnet launch 2026-11-21 18:00 UTC; SOLO stratum pool",
 "date":"2026-11-20T07:00:00Z",
 "kind":"announcement",
 "url":"https://t.me/miningrelease/123",
 "links":{"pool":"https://pool.example.com"},
 "facts":{"algorithm":"KawPow","gpu_mentioned":True,"solo_mentioned":True,
          "pool_mentioned":True,"publication_utc":"2026-11-20T07:00:00+00:00",
          "launch_claim_utc":"2026-11-21T18:00:00+00:00"},
}
class AgentTests(unittest.TestCase):
    def test_recent_coin_qualifies(self):
        item=examine("tg:miningrelease:123",PROJECT,NOW)
        self.assertIsNotNone(item)
        self.assertGreaterEqual(item["score"],8)
        self.assertIn("не проверены", " ".join(item["unknown"]))
        self.assertIn("Заявлен",report([item],NOW))
    def test_news_not_coin(self):
        item=dict(PROJECT,kind="news")
        self.assertIsNone(examine("pool:2026-11-20:0",item,NOW))
    def test_miner_software_not_coin(self):
        item=dict(PROJECT,title="NVIDIA GPU miner v1.0 software release")
        self.assertIsNone(examine("btt:42",item,NOW))
    def test_old_repo_not_claimed_recent(self):
        item=dict(PROJECT,kind="repository",repo_created="2025-01-01T00:00:00Z",
                  date="2025-01-01T00:00:00Z",facts={})
        self.assertIsNone(examine("gh:42",item,NOW))
    def test_score_no_fake_profit(self):
        item=examine("tg:miningrelease:123",PROJECT,NOW)
        txt=report([item],NOW)
        self.assertNotIn("100x",txt)
        self.assertNotIn("гарант",txt.lower())
        self.assertIn("не проверены",txt)
    def test_source_diversity(self):
        projects={"btt:"+str(i):dict(PROJECT,title="GPU PoW KawPow coin "+str(i))
                  for i in range(10)}
        projects["tg:mine:111"]=dict(PROJECT)
        out=analyze(projects,NOW,limit=8)
        self.assertLessEqual(sum(x["source"]=="Bitcointalk" for x in out),3)
        self.assertTrue(any(x["source"]=="Telegram" for x in out))
    def test_nothing_found(self):
        self.assertIn("пока нет", report([], NOW))
        self.assertEqual(analyze({},NOW), [])
if __name__=="__main__":
    unittest.main()
