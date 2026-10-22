import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from failure_detector import PhiAccrualFailureDetector


class TestPhiAccrualFailureDetector(unittest.TestCase):

    def setUp(self):
        self.detector = PhiAccrualFailureDetector(threshold=8.0, min_std_dev=0.5)
        # Seed detector with heartbeats with slight jitter around 1.0s (t=0 to t=10)
        for t in range(11):
            self.detector.heartbeat(timestamp=float(t))

    def test_nominal_heartbeats_low_phi(self):
        # Current time t=10.5 (only 0.5s elapsed, heartbeat expected at 11.0)
        phi_val = self.detector.phi(current_time=10.5)
        self.assertLess(phi_val, 1.0)
        self.assertFalse(self.detector.is_suspect(current_time=10.5))

    def test_progressive_suspicion_growth(self):
        # At mean=1.0, std_dev=0.5:
        # t=11.2 (delta=1.2s), t=11.8 (delta=1.8s), t=12.5 (delta=2.5s)
        phi_1 = self.detector.phi(current_time=11.2)
        phi_2 = self.detector.phi(current_time=11.8)
        phi_3 = self.detector.phi(current_time=12.5)

        self.assertGreater(phi_2, phi_1)
        self.assertGreater(phi_3, phi_2)

    def test_threshold_breach_declares_dead(self):
        # After 10 standard deviations of silence, phi reaches threshold >= 8.0
        self.assertTrue(self.detector.is_suspect(current_time=20.0))
        self.assertGreaterEqual(self.detector.phi(current_time=20.0), 8.0)

    def test_recovery_on_late_heartbeat(self):
        # Node was suspect at t=20
        self.assertTrue(self.detector.is_suspect(current_time=20.0))

        # Node wakes up from GC pause and sends heartbeat at t=20
        self.detector.heartbeat(timestamp=20.0)

        # Immediately at t=20.1, suspicion resets to normal
        self.assertFalse(self.detector.is_suspect(current_time=20.1))
        self.assertLess(self.detector.phi(current_time=20.1), 1.0)


if __name__ == "__main__":
    unittest.main()
