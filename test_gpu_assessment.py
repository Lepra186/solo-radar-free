import unittest
from datetime import datetime, timezone, timedelta
from gpu_assessment import assess, signal, description, extract_utc_launch

NOW = datetime(2026, 11, 20, 5, 0, tzinfo=timezone.utc)

class GPUAssessmentTests(unittest.TestCase):
    def test_amd_gpu_mainnet_early(self):
        s = "Coin Name: NewCoin, GPU AMD Radeon, proof of work. Mainnet launch 2026-11-21 10:30 UTC, solo pool"
        self.assertEqual(signal(s, NOW), "EARLY")
        self.assertIn("NVIDIA/AMD", description(s, NOW))
        self.assertEqual(extract_utc_launch(s), datetime(2026,11,21,10,30,tzinfo=timezone.utc))
    def test_nvidia_gpu_solo_watch(self):
        self.assertEqual(signal("New GPU proof of work NVIDIA CUDA solo mining available", NOW), "WATCH")
    def test_cpu_only_excluded(self):
        self.assertIsNone(signal("RandomX CPU-only PoW mainnet launch 2026-11-21 10:30 UTC", NOW))
    def test_token_airdrop_excluded(self):
        self.assertIsNone(signal("GPU mining airdrop ICO mainnet 2026-11-21 10:30 UTC", NOW))
    def test_unverified_timezone_not_assumed(self):
        self.assertIsNone(extract_utc_launch("GPU PoW mainnet launch 2026-11-21 10:30 Moscow time"))
    def test_old_launch_not_early(self):
        self.assertNotEqual(signal("GPU proof of work mainnet launch 2026-10-21 10:30 UTC", NOW), "EARLY")
    def test_pool_hold_without_solo(self):
        sample = "New GPU proof of work coin mainnet launch with PPLNS pool and stratum"
        self.assertEqual(signal(sample, NOW), "HOLD")
        self.assertIn("Пул:", description(sample, NOW))
    def test_early_mainnet_without_solo(self):
        sample = "GPU proof of work mainnet launch 2026-11-21 10:30 UTC pool mining"
        self.assertEqual(signal(sample, NOW), "EARLY")
    def test_not_only_cpu(self):
        self.assertIsNone(signal("CPU only RandomX proof of work mainnet launch with pool", NOW))
    def test_gpu_explicitly_denied_not_early(self):
        s="New GPU KawPow PoW coin mainnet launch 2026-11-21 10:30 UTC; GPU mining not supported"
        self.assertIsNone(signal(s,NOW))
        self.assertTrue(assess(s,NOW)["excluded"])
    def test_pending_mainnet_not_early(self):
        s="New GPU PoW coin mainnet launch 2026-11-21 10:30 UTC; mainnet pending"
        self.assertIsNone(signal(s,NOW))
    def test_unknown_time_reference_not_early(self):
        self.assertNotEqual(signal("GPU PoW mainnet launch 2020-01-01 10:30 UTC"),"EARLY")
    def test_vendor_independent(self):
        self.assertNotIn("5070", description("GPU PoW mining", NOW))

if __name__ == "__main__":
    unittest.main()
