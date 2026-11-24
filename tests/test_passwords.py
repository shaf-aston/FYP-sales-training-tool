"""Password hashes saved today must still check tomorrow: a change to the salt or key length, or to how the
key is made, would lock every existing user out while the round-trip tests stayed green."""

from core.accounts.passwords import check_password, hash_password

# made by hash_password("correct horse") on 24 Nov 2026; must keep verifying forever
SAVED = ("scrypt$16384$8$1$5e0fa8cca13409e353ed6a76f333497f"
         "$fe3c3710358ba84874b6f0168dfc24aea05f20d8a1ff3b196efe832528053f39")


def test_a_hash_saved_earlier_still_checks():
    assert check_password("correct horse", SAVED)
    assert not check_password("correct horse!", SAVED)


def test_a_new_hash_has_a_16_byte_salt_and_32_byte_key():
    scheme, n, r, p, salt, key = hash_password("pw").split("$")
    assert scheme == "scrypt" and len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(key)) == 32


def test_malformed_stored_values_never_check():
    for bad in ["", "plain", "bcrypt$1$2$3$aa$bb", SAVED.replace("scrypt", "md5"), SAVED[:-2]]:
        assert not check_password("correct horse", bad)
