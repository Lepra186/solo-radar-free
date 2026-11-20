import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from telegram_commands import digest, command_name, process_commands

NOW=datetime(2026,11,20,5,0,tzinfo=timezone.utc)
ITEM={"title":"GPU Coin launch", "body":"GPU Nvidia AMD proof of work SOLO mainnet launch 2026-11-21 10:30 UTC", "url":"https://example.org/launch","source":"test"}
class TelegramCommandTests(unittest.TestCase):
    def test_start_recognized(self):
        self.assertEqual(command_name({"text":"/start"}),"/start")
        self.assertEqual(command_name({"text":"/start@solo_radar_hunter_bot"}),"/start")
        self.assertIsNone(command_name({"text":"hello"}))
    def test_digest_includes_candidates(self):
        result=digest({"a":ITEM},NOW)
        self.assertIn("GPU Coin launch", result)
        self.assertIn("https://example.org/launch",result)
    def test_empty_digest(self):
        self.assertIn("пока нет",digest({},NOW))
    def test_private_owner_only(self):
        state={}
        messages=[
          {"update_id":50,"message":{"chat":{"id":999},"text":"/start"}},
          {"update_id":51,"message":{"chat":{"id":123},"text":"/start"}},
          {"update_id":52,"message":{"chat":{"id":123},"text":"/status"}},
        ]
        output=[]
        with patch("telegram_commands.get_updates",return_value=messages):
            count=process_commands("token","123",state,{"a":ITEM},NOW,output.append)
        self.assertEqual(count,2)
        self.assertEqual(len(output),2)
        self.assertEqual(state["telegram_update_offset"],53)
    def test_repeated_update_skipped(self):
        state={"telegram_update_offset":22}
        with patch("telegram_commands.get_updates",return_value=[
            {"update_id":21,"message":{"chat":{"id":123},"text":"/start"}}]):
            self.assertEqual(process_commands("token","123",state,{},NOW,lambda _:self.fail("duplicate")),0)
if __name__=="__main__":
    unittest.main()
