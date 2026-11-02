import unittest
import os
os.environ.setdefault("BASE_URL", "https://example.invalid/v1")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("MODEL", "test-model")
from agent.policy import inspect_command
from agent.tools.commands import _truncate

class PolicyTests(unittest.TestCase):
    def test_accepts_read_only(self):
        self.assertTrue(inspect_command("wsl", "uname -a").allowed)
    def test_rejects_unknown_target(self):
        self.assertFalse(inspect_command("cloud", "whoami").allowed)
    def test_blocks_shutdown(self):
        self.assertFalse(inspect_command("windows", "Stop-Computer").allowed)
    def test_blocks_sudo(self):
        self.assertFalse(inspect_command("vm", "sudo apt install foo").allowed)
    def test_rejects_empty(self):
        self.assertFalse(inspect_command("wsl", " ").allowed)
    def test_truncates(self):
        self.assertTrue(_truncate("abcdef",3).startswith("abc"))
        self.assertIn("truncated",_truncate("abcdef",3))

if __name__ == "__main__": unittest.main()
