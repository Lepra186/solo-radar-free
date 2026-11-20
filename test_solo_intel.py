import unittest
import math
from solo_intel import mine_probability, extract_declared_facts, extract_links, summary

class SOLOIntelTests(unittest.TestCase):
    def test_probability_one_expected_block(self):
        p = mine_probability(10, 100, 10, 3600)
        self.assertAlmostEqual(p, 1 - math.exp(-1), places=10)
    def test_probability_zero(self):
        self.assertEqual(mine_probability(0, 100, 24, 60), 0)
    def test_probability_invalid(self):
        for args in ((101,100,1,60), (10,0,1,60), (10,100,-1,60), (10,100,1,0)):
            with self.assertRaises(ValueError):
                mine_probability(*args)
    def test_declared_not_verified(self):
        body = "GPU PoW, block reward: 19 NEB, block time: 2 minutes; premine 12%"
        facts = extract_declared_facts(body)
        self.assertEqual(facts["reward"], (19, "NEB"))
        self.assertEqual(facts["block_seconds"], 120)
        self.assertTrue(facts["premine_mentioned"])
        self.assertIn("не проверено", summary(body))
    def test_url_extraction(self):
        urls = extract_links("https://example.com/pool, https://example.com/pool https://github.com/test/repo")
        self.assertEqual(urls, ["https://example.com/pool", "https://github.com/test/repo"])
    def test_no_fake_numbers(self):
        out = summary("New GPU PoW mainnet launches soon")
        self.assertIn("не рассчитывается", out)
        self.assertIn("не найдена", out)

if __name__ == "__main__":
    unittest.main()
