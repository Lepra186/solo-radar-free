import unittest
from telegram_recipients import parse_recipients

class RecipientTests(unittest.TestCase):
    def test_one_existing_user(self):
        self.assertEqual(parse_recipients("123"),["123","812612452"])
    def test_two_users(self):
        self.assertEqual(parse_recipients("123","456"),["123","812612452","456"])
    def test_duplicates_removed(self):
        self.assertEqual(parse_recipients("123","123, 456;456"),["123","812612452","456"])
    def test_preapproved_user_is_unique(self):
        self.assertEqual(parse_recipients("812612452","812612452"),["812612452"])
    def test_bad_input_rejected(self):
        with self.assertRaises(ValueError):
            parse_recipients("123","@some_username")
    def test_preapproved_user_without_optional_secrets(self):
        self.assertEqual(parse_recipients("",""),["812612452"])
if __name__=="__main__":
    unittest.main()
