"""Identity decisions for installed client public keys.

Identities come only from the operator file. There is no registration path.
"""


def decision(pubkey, installed):
    """Return 'allow' only when pubkey is a non-empty installed key."""
    if not pubkey:
        return "deny"
    if pubkey in installed:
        return "allow"
    return "deny"
