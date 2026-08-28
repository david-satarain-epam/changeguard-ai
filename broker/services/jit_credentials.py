from secrets import token_urlsafe


def generate_jit_credentials() -> str:
    return token_urlsafe(24)
