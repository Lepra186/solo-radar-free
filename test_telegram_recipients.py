import unittest
from telegram_recipients import parse_recipients

class RecipientTests(unittest.TestCase):
    def test_one_existing_user(self):
        self.assertEqual(parse_recipients("123"),["123"])
    def test_two_users(self):
        self.assertEqual(parse_recipients("123","456"),["123","456"])
    def test_duplicates_removed(self):
        self.assertEqual(parse_recipients("123","123, 456;456"),["123","456"])
    def test_bad_input_rejected(self):
        with self.assertRaises(ValueError):
            parse_recipients("123","@some_username")
    def test_missing_config(self):
        with self.assertRaises(ValueError):
            parse_recipients("","")
if __name__=="__main__":
    unittest.main()
