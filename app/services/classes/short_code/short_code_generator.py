import secrets
import string


class ShortCodeGenerator:
    """Generates a random short code of a given length and character set."""

    def __init__(self, length: int = 7, charset: str = None):
        self.length = length
        self.charset = charset or (string.ascii_letters + string.digits)

    def generate(self) -> str:
        """Creates a single short code."""
        return "".join(secrets.choice(self.charset) for _ in range(self.length))
