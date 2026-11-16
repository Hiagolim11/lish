import os
import unittest
from littleshell import env


class EnvHelperTests(unittest.TestCase):
    def setUp(self):
        for name in (env.SEPARATE, env.FONT, env.SPEECH_MODEL, env.SPEECH_SECONDS):
            os.environ.pop(name, None)

    def test_text_default_and_value(self):
        self.assertEqual(env.text(env.FONT, "Fira"), "Fira")
        os.environ[env.FONT] = "Hack"
        self.assertEqual(env.text(env.FONT, "Fira"), "Hack")

    def test_flag(self):
        self.assertTrue(env.flag(env.SEPARATE, default=True))
        os.environ[env.SEPARATE] = "on"
        self.assertTrue(env.flag(env.SEPARATE))
        os.environ[env.SEPARATE] = "nope"
        self.assertFalse(env.flag(env.SEPARATE))

    def test_number_clamps_and_recovers(self):
        os.environ[env.SPEECH_SECONDS] = "1"
        self.assertEqual(env.number(env.SPEECH_SECONDS, 8, minimum=2), 2)
        os.environ[env.SPEECH_SECONDS] = "garbage"
        self.assertEqual(env.number(env.SPEECH_SECONDS, 8), 8)


if __name__ == "__main__":
    unittest.main()
