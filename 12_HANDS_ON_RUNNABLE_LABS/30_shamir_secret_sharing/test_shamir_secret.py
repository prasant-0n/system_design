"""Tests for Shamir's (k, n) Threshold Secret Sharing."""

import unittest
import itertools
from .shamir_secret import ShamirSecretSharing, PRIME


class TestShamirSecretSharing(unittest.TestCase):

    def setUp(self):
        self.sss = ShamirSecretSharing()

    def test_integer_secret_reconstruction(self):
        secret = 1234567890987654321
        k = 3
        n = 5
        shares = self.sss.split_secret(secret, threshold_k=k, num_shares_n=n)
        self.assertEqual(len(shares), 5)

        # Any combination of exactly k shares must reconstruct the secret
        for subset in itertools.combinations(shares, k):
            reconstructed = self.sss.reconstruct_secret(list(subset))
            self.assertEqual(reconstructed, secret)

    def test_string_secret_reconstruction(self):
        secret_text = "Master-Root-Private-Key-2026-X99"
        k = 4
        n = 7
        shares = self.sss.split_string(secret_text, k=k, n=n)

        # Take any 4 shares
        chosen_shares = [shares[0], shares[2], shares[4], shares[6]]
        recovered = self.sss.reconstruct_string(chosen_shares)
        self.assertEqual(recovered, secret_text)

    def test_insufficient_shares_fail_to_reconstruct(self):
        secret = 9876543210
        k = 4
        n = 6
        shares = self.sss.split_secret(secret, threshold_k=k, num_shares_n=n)

        # Taking k-1 shares (3 shares) and assuming an arbitrary 4th share
        # reconstructs a random incorrect value (Information-Theoretic Security)
        insufficient = shares[:3]
        fake_share = (99, 123456)
        reconstructed = self.sss.reconstruct_secret(insufficient + [fake_share])
        self.assertNotEqual(reconstructed, secret)


if __name__ == "__main__":
    unittest.main()
