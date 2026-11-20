import unittest
from coin_filter import classify,is_coin

def item(title,body=None,kind="repository"):
    return {"title":title,"body":body if body is not None else title,"kind":kind}

class CoinOnlyTests(unittest.TestCase):
    def test_reject_real_false_positives(self):
        bad=[
          ("gh:1457287638",item("good-mining/good-miner","Rust cryptocurrency miner for NVIDIA, AMD and Intel GPUs and CPUs. One binary, auto profit switching, built-in dashboard.")),
          ("gh:1449663269",item("gacanga/crypto-connection-miner","Crypto Connection Miner free open-source miner no dev fee NVIDIA GPUs for GOSTcoin")),
          ("gh:1457230305",item("kobold-dev/kobold-miner","NVIDIA GPU miner for Pearl (PRL), Ravencoin (RVN) and other coins")),
          ("gh:1455827083",item("MrM002/NexusSwitch","Open-Source Crypto Auto Profit-Switcher with a Self-Hosted Telegram Bot")),
          ("btt:100",item("[ANN] GPU miner v2.3 for KawPow coin released",kind="announcement")),
          ("pool:2026-11-20:0",item("New GPU mining pool for KawPow Coin",kind="news")),
          ("btt:200",item("[ANN] YSKAR - SHA-256d PoW | Mine on phone CPU or GPU",kind="announcement")),
          ("btt:201",item("[ANN] Block Zero | RandomX CPU mining coin",kind="announcement")),
          ("btt:202",item("[ANN] Meme token launched Solana Pump.fun",kind="announcement")),
        ]
        for key,record in bad:
            with self.subTest(key=key):
                self.assertFalse(is_coin(key,record),classify(key,record))
    def test_keep_mineable_coin_announcements(self):
        good=[
          ("btt:5600215",item("[ANN] Quinvium (QU) | GPU PoW Ethash | No premine | Mainnet",kind="announcement")),
          ("btt:5599371",item("[ANN] NEX Chain (NEXC) | Ethash PoW | GPU & CPU | Free Solo Miner | EVM + DEX",kind="announcement")),
          ("gh:1457186269",item("Lakylife/quinvium","Quinvium (QU): a programmable proof-of-work blockchain with GPU mining Ethash, full node, wallet, explorer and miner")),
          ("tg:miningrelease:20",item("Coin Name: NewCoin | Ticker: NC | KawPow GPU mining mainnet",kind="announcement")),
        ]
        for key,record in good:
            with self.subTest(key=key):
                self.assertTrue(is_coin(key,record),classify(key,record))
    def test_unknown_not_reported_as_coin(self):
        self.assertFalse(is_coin("gh:10",item("user/gpu-tool","GPU mining NVIDIA AMD")))
        self.assertEqual(classify("gh:10",item("user/gpu-tool","GPU mining NVIDIA AMD"))[0],"insufficient")

if __name__=="__main__":
    unittest.main()
