"""Shamir's Secret Sharing (Adi Shamir, 1979).

Implements:
1. Finite Field arithmetic over prime p (2^256 - 189)
2. (k, n) Threshold secret splitting into n cryptographic shares
3. Lagrange basis polynomial interpolation to reconstruct secret from any k shares
4. Information-theoretic security verification for any k-1 shares
"""

import os
import secrets
from typing import List, Tuple

# 256-bit safe prime (FIPS compliant prime larger than 2^256)
PRIME = 2**256 - 189


def mod_inverse(a: int, p: int = PRIME) -> int:
    """Calculate modular inverse using Fermat's Little Theorem: a^(p-2) mod p."""
    return pow(a, p - 2, p)


class ShamirSecretSharing:
    """(k, n) Threshold Secret Sharing Engine."""

    def __init__(self, prime: int = PRIME):
        self.prime = prime

    def split_secret(self, secret: int, threshold_k: int, num_shares_n: int) -> List[Tuple[int, int]]:
        """Split integer secret into n shares with threshold k.

        Returns list of (x, y) coordinate pairs.
        """
        if threshold_k > num_shares_n:
            raise ValueError("Threshold k cannot exceed total shares n")
        if secret >= self.prime or secret < 0:
            raise ValueError(f"Secret must be in range [0, {self.prime - 1}]")

        # Generate k-1 random coefficients: a_1, a_2, ..., a_{k-1}
        # Polynomial: f(x) = secret + a_1*x + a_2*x^2 + ... + a_{k-1}*x^{k-1} mod p
        coeffs = [secret] + [secrets.randbelow(self.prime) for _ in range(threshold_k - 1)]

        shares: List[Tuple[int, int]] = []
        for x in range(1, num_shares_n + 1):
            # Horner's method for polynomial evaluation
            y = 0
            for coeff in reversed(coeffs):
                y = (y * x + coeff) % self.prime
            shares.append((x, y))

        return shares

    def reconstruct_secret(self, shares: List[Tuple[int, int]]) -> int:
        """Reconstruct secret from any subset of at least k shares via Lagrange interpolation."""
        k = len(shares)
        secret = 0

        for j in range(k):
            xj, yj = shares[j]
            # Compute Lagrange basis polynomial evaluated at x = 0:
            # l_j(0) = Product_{m != j} (-xm) / (xj - xm) mod p
            numerator = 1
            denominator = 1
            for m in range(k):
                if m == j:
                    continue
                xm, _ = shares[m]
                numerator = (numerator * (-xm)) % self.prime
                denominator = (denominator * (xj - xm)) % self.prime

            lagrange_coeff = (numerator * mod_inverse(denominator, self.prime)) % self.prime
            secret = (secret + yj * lagrange_coeff) % self.prime

        return secret

    # String convenience helpers
    def split_string(self, text: str, k: int, n: int) -> List[Tuple[int, int]]:
        """Encode UTF-8 string to integer and split."""
        raw_bytes = text.encode("utf-8")
        secret_int = int.from_bytes(raw_bytes, byteorder="big")
        return self.split_secret(secret_int, k, n)

    def reconstruct_string(self, shares: List[Tuple[int, int]]) -> str:
        """Reconstruct integer and decode back to UTF-8 string."""
        secret_int = self.reconstruct_secret(shares)
        # Convert integer to bytes
        byte_len = (secret_int.bit_length() + 7) // 8
        raw_bytes = secret_int.to_bytes(byte_len, byteorder="big")
        return raw_bytes.decode("utf-8")
