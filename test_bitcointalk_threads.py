import unittest
from datetime import datetime,timezone
from bitcointalk_threads import parse,topic_id,enrich

NOW=datetime(2026,11,20,10,0,tzinfo=timezone.utc)
HTML="""<html><body>
<div class="post" id="msg_one">NEX Chain (NEXC)<br>Ethash PoW GPU coin
Premine: 10,000,000 NEXC (10%). Block reward 5 NEXC.
<a href="https://explorer.example.com">Explorer</a></div>
<div class="post" id="msg_two">Available on pool with PPLNS.
<a href="https://pool.example.com">Pool</a></div>
<div class="post" id="msg_three">There is no NEX liquidity on the swap at the moment</div>
<div class="post" id="msg_four">Withdrawals are not happening. Funds stuck.</div>
</body></html>"""

class ForumThreadTests(unittest.TestCase):
 def test_premine_and_risk_with_attribution(self):
  result=parse(HTML,"https://bitcointalk.org/index.php?topic=5599371.0",NOW)
  self.assertEqual(result["posts_read"],4)
  self.assertEqual(result["premine_percent_claimed_by_announcement"],10)
  self.assertTrue(any(x["type"]=="withdrawal_complaint" for x in result["discussion_warnings"]))
  self.assertTrue(any(x["type"]=="liquidity_concern" for x in result["discussion_warnings"]))
  self.assertIn("https://pool.example.com",result["links_mentioned"])
  self.assertTrue(all("не проверено" in x["attribution"] for x in result["discussion_warnings"]))
 def test_bounded_safe_only_bitcointalk_topic_ids(self):
  self.assertIsNone(topic_id("gh:123"))
  self.assertIsNone(topic_id("btt:1;https://malicious.example"))
  self.assertEqual(topic_id("btt:5599371"),"5599371")
 def test_noncoin_not_refetched(self):
  records={"btt:5599371":{"coin_class":"non_coin","title":"miner app"}}
  called=[]
  enrich(lambda url:called.append(url),records,NOW)
  self.assertEqual(called,[])
 def test_cache_and_fixed_url(self):
  records={"btt:5599371":{"coin_class":"coin_candidate","title":"[ANN] NEX Chain"}}
  urls=[]
  def fetch(url):
    urls.append(url)
    return HTML
  s=enrich(fetch,records,NOW)
  self.assertEqual(s["threads_parsed"],1)
  self.assertEqual(urls,["https://bitcointalk.org/index.php?topic=5599371.0"])
  s2=enrich(fetch,records,NOW)
  self.assertEqual(s2["threads_checked"],0)
 def test_no_posts_is_failed_parse_not_fake_evidence(self):
  with self.assertRaises(ValueError):
    parse("<div>No valid posts</div>","https://bitcointalk.org",NOW)

if __name__=="__main__":unittest.main()
