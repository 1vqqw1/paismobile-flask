import hashlib
import hmac
import secrets

ITERATIONS = 120000


class Password:
    @staticmethod
    def make(password):
        salt = secrets.token_hex(16)
        code = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            ITERATIONS
        ).hex()
        return "pbkdf2_sha256$" + salt + "$" + code

    @staticmethod
    def check(password, stored):
        try:
            algorithm, salt, old_code = stored.split("$", 2)
        except ValueError:
            return False
        if algorithm != "pbkdf2_sha256":
            return False
        new_code = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            ITERATIONS
        ).hex()
        return hmac.compare_digest(new_code, old_code)


def hash_password(password):
    return Password.make(password)


def check_password(password, stored_hash):
    return Password.check(password, stored_hash)
