import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from daily_ai import candidates,validate,rules_only,message,api_request

NOW=datetime(2026,11,20,8,0,tzinfo=timezone.utc)
EXAMPLE={"key":"tg:mine:1","title":"New GPU KawPow PoW coin",
         "source":"Telegram","publication_or_creation":"2026-11-20T07:00:00Z",
         "claimed_mainnet":"2026-11-21T08:00:00Z","algorithm":"KawPow",
         "score":9,"reasons":["указан алгоритм"],"unknown":["ликвидность неизвестна"],
         "url":"https://t.me/mine/1"}

class DailyAI(unittest.TestCase):
    def test_whitelisted_candidates_only(self):
        raw={"summary":"Interesting","picks":[
            {"key":"fabricated","rationale":"100x"},
            {"key":"tg:mine:1","rationale":"recent","mining":"maybe","risks":"premine"}
        ],"watchouts":["verify"]}
        report=validate(raw,[EXAMPLE])
        self.assertEqual(len(report["picks"]),1)
        self.assertEqual(report["picks"][0]["url"],EXAMPLE["url"])
    def test_no_key_fallback_labeled(self):
        result={"generated_at":"2026-11-20T08:00:00+00:00","mode":"rules_only",
                "candidate_count":1,**rules_only([EXAMPLE])}
        txt=message(result)
        self.assertIn("без ИИ",txt)
        self.assertIn("Mainnet:",txt)
    def test_empty_candidates(self):
        self.assertEqual(rules_only([])["picks"],[])
        self.assertEqual(candidates({"topics":{}},NOW),[])
    def test_bad_model_report_rejected(self):
        with self.assertRaises(ValueError):
            validate({"picks":{}} ,[EXAMPLE])
    def test_no_fake_model_fields(self):
        raw={"summary":"test","picks":[{"key":"tg:mine:1","url":"https://scam.invalid",
            "algorithm":"Magical","launch_claim":"2099-01-01","rationale":"needs checks"}]}
        p=validate(raw,[EXAMPLE])["picks"][0]
        self.assertEqual(p["url"],EXAMPLE["url"])
        self.assertEqual(p["algorithm"],EXAMPLE["algorithm"])
        self.assertEqual(p["launch_claim"],EXAMPLE["claimed_mainnet"])
if __name__=="__main__":
    unittest.main()
