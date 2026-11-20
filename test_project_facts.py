import unittest
from datetime import datetime, timezone
from project_facts import get_facts

class ProjectFactTests(unittest.TestCase):
    def test_repository_date_is_not_mainnet(self):
        facts=get_facts("GPU Ethash PoW cryptocurrency",repo_created="2026-11-18T02:15:00Z",
                        repo_updated="2026-11-20T05:00:00Z",kind="repository")
        self.assertEqual(facts["repo_created_utc"],"2026-11-18T02:15+00:00")
        self.assertIsNone(facts["launch_claim_utc"])
        self.assertEqual(facts["algorithm"],"Ethash")
    def test_announced_mainnet_is_labeled_claim(self):
        facts=get_facts("Coin Name: NewChain\nTicker: NEWC\nAlgo: KawPow\nmainnet launch 2026-11-22 18:00 UTC\nSOLO pool",
                        publication="2026-11-20T06:10:00+00:00",kind="announcement")
        self.assertEqual(facts["ticker"],"NEWC")
        self.assertEqual(facts["algorithm"],"KawPow")
        self.assertEqual(facts["launch_claim_utc"],"2026-11-22T18:00+00:00")
        self.assertTrue(facts["solo_mentioned"])
        self.assertTrue(facts["pool_mentioned"])
    def test_unknown_details_remain_unknown(self):
        facts=get_facts("New open source blockchain project",kind="repository")
        self.assertIsNone(facts["repo_created_utc"])
        self.assertIsNone(facts["launch_claim_utc"])
        self.assertIsNone(facts["algorithm"])
    def test_publication_not_creation(self):
        facts=get_facts("GPU PoW",publication="2026-11-20T08:00:00Z",kind="announcement")
        self.assertIsNone(facts["repo_created_utc"])
        self.assertEqual(facts["publication_utc"],"2026-11-20T08:00+00:00")

if __name__=="__main__":
    unittest.main()
