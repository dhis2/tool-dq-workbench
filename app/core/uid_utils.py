import secrets
import string

class UidUtils:
    @staticmethod
    def generate_uid() -> str:
        """Generates a unique identifier."""
        alphabet = string.ascii_letters + string.digits
        first_letter = secrets.choice(string.ascii_lowercase)
        last_part = ''.join(secrets.choice(alphabet) for _ in range(10))
        return first_letter + last_part

    @staticmethod
    def is_valid_uid(uid: str) -> bool:
        """Checks if the provided UID is valid."""
        if len(uid) != 11:
            return False
        if not uid[0].islower():
            return False
        if not all(c.isalnum() for c in uid):
            return False
        return True