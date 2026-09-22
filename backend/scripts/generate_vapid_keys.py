"""Local developer utility: generate a VAPID key pair for Web Push.

Run ONCE from the backend directory (never during application startup)::

    python scripts/generate_vapid_keys.py

Prints the public key (for VAPID_PUBLIC_KEY) and the private key PEM
(for VAPID_PRIVATE_KEY). Nothing is written to the repository.
"""

import base64
import sys


def main() -> int:
    try:
        from py_vapid import Vapid
    except ImportError:
        print("pywebpush is not installed. Run: pip install -r requirements.txt", file=sys.stderr)
        return 1

    vapid = Vapid()
    vapid.generate_keys()

    public_numbers = vapid.public_key.public_numbers()
    uncompressed = (
        b"\x04"
        + public_numbers.x.to_bytes(32, "big")
        + public_numbers.y.to_bytes(32, "big")
    )
    public_key = base64.urlsafe_b64encode(uncompressed).decode().rstrip("=")
    private_pem = vapid.private_pem().decode().strip()

    print("PUBLIC KEY:")
    print(public_key)
    print()
    print("PRIVATE KEY:")
    print(private_pem)
    print()
    print("Store these as Railway environment variables. Do not commit them.")
    print("  VAPID_PUBLIC_KEY=<the public key above>")
    print("  VAPID_PRIVATE_KEY=<the full PEM block above, newlines preserved>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
