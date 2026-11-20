import unittest
from datetime import datetime,timezone,timedelta
from evm_rpc_source import NETWORKS,poll_network,update,unhex

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
HASH="0x"+"a"*64
class PublicRPC(unittest.TestCase):
 def fake(self,endpoint,method,params):
  if method=="eth_chainId":return "0xccb1" # 52401
  if method=="eth_blockNumber":return "0x64"
  if method=="eth_getBlockByNumber":
   self.assertEqual(params,["0x64",False])
   return {"number":"0x64","timestamp":hex(int(datetime(2026,11,20,9,59,tzinfo=timezone.utc).timestamp())),
           "hash":HASH,"difficulty":"0x10"}
  self.fail(method)
 def test_direct_rpc_validates_chain(self):
  self.assertEqual(unhex("0x64"),100)
  a=poll_network(NETWORKS["quinvium"],NOW,self.fake)
  self.assertEqual(a["chain_id"],52401)
  self.assertEqual(a["last_block_height"],100)
  self.assertEqual(a["difficulty_from_header"],16)
 def test_mismatched_chain_id_rejected(self):
  with self.assertRaises(ValueError):
   poll_network(NETWORKS["quinvium"],NOW,lambda ep,m,p:"0x1")
 def test_bad_or_old_block_rejected(self):
  def bad(ep,m,p):
   if m=="eth_getBlockByNumber":
    return {"number":"0x64","timestamp":"0x1","hash":HASH}
   return self.fake(ep,m,p)
  with self.assertRaises(ValueError):
   poll_network(NETWORKS["quinvium"],NOW,bad)
 def test_multi_source_qunivium_gets_single_network_poll(self):
  c={"coin_class":"coin_candidate","title":"[ANN] Quinvium GPU Ethash blockchain"}
  topics={"gh:1457186269":dict(c),"btt:5600215":dict(c)}
  history,stats=update(topics,{},NOW,self.fake)
  self.assertEqual(stats["rpc_checks"],1)
  self.assertEqual(stats["available"],1)
  self.assertEqual(topics["gh:1457186269"]["rpc_evidence"]["chain_id"],52401)
  self.assertEqual(topics["btt:5600215"]["rpc_evidence"]["chain_id"],52401)
 def test_new_height_after_ten_minutes(self):
  coin={"coin_class":"coin_candidate","title":"GPU PoW Quinvium"}
  records={"gh:1457186269":coin}
  old={"quinvium":{"checked_at":"2026-11-20T09:30:00Z","status":"active",
     "rpc":{"chain_id":52401,"last_block_height":90,"checked_at":"2026-11-20T09:30:00Z"}}}
  history,stats=update(records,{"evm_rpc":old},NOW,self.fake)
  self.assertEqual(stats["height_advanced"],1)
  self.assertEqual(records["gh:1457186269"]["rpc_progress"]["blocks_increased"],10)
 def test_no_coin_software_poll(self):
  records={"gh:1457186269":{"coin_class":"non_coin","title":"GPU miner release"}}
  history,stats=update(records,{},NOW,lambda *args:self.fail("Network request"))
  self.assertEqual(stats["rpc_checks"],0)
if __name__=="__main__":unittest.main()
