import tempfile
import unittest
from pathlib import Path

from common.session_manager import SessionError, SessionManager


class SessionManagerTests(unittest.TestCase):
    def test_manifest_and_lifecycle_survive_reload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.json"
            manager = SessionManager(path)
            record = manager.create("AI deployment", "/home/tester")
            lease = manager.attach(record.session_id)
            manager.detach(record.session_id, lease)
            restored = SessionManager(path)
            self.assertEqual(restored.get(record.session_id).state, "detached")
            self.assertEqual(restored.get(record.session_id).label, "AI deployment")

    def test_only_one_controller_and_pause_resume_require_lease(self) -> None:
        manager = SessionManager()
        record = manager.create("shell", "/home/tester")
        lease = manager.attach(record.session_id)
        with self.assertRaisesRegex(SessionError, "locked"):
            manager.attach(record.session_id)
        manager.pause(record.session_id, lease)
        manager.resume(record.session_id, lease)
        with self.assertRaises(SessionError):
            manager.pause(record.session_id, "wrong")

    def test_labels_and_paths_are_bounded(self) -> None:
        manager = SessionManager()
        with self.assertRaises(SessionError):
            manager.create("\nnot safe", "/home/tester")
        with self.assertRaises(SessionError):
            manager.create("x" * 97, "/home/tester")


if __name__ == "__main__":
    unittest.main()
