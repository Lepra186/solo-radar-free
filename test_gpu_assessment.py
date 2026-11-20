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
    def test_vendor_independent(self):
        self.assertNotIn("5070", description("GPU PoW mining", NOW))

if __name__ == "__main__":
    unittest.main()
