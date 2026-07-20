import tempfile
import time
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

    def test_completion_releases_lease_and_persists_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manager = SessionManager(Path(directory) / "sessions.json")
            record = manager.create("build", "/home/tester")
            manager.start(record.session_id)
            manager.attach(record.session_id)
            completed = manager.complete(record.session_id, 17)
            self.assertEqual(completed.state, "exited")
            self.assertEqual(completed.exit_code, 17)
            with self.assertRaisesRegex(SessionError, "cannot attach"):
                manager.attach(record.session_id)
            restored = SessionManager(Path(directory) / "sessions.json")
            self.assertEqual(restored.get(record.session_id).exit_code, 17)

    def test_expired_lease_can_be_reclaimed(self) -> None:
        manager = SessionManager(lease_seconds=30)
        record = manager.create("shell", "/home/tester")
        manager.attach(record.session_id)
        manager._leases[record.session_id].expires_at = time.monotonic() - 1
        replacement = manager.attach(record.session_id)
        self.assertIsInstance(replacement, str)


if __name__ == "__main__":
    unittest.main()
