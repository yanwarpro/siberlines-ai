from urllib.parse import urlsplit


def parse_cors_origins(value: object) -> object:
    if isinstance(value, str):
        return [origin.strip() for origin in value.split(",") if origin.strip()]
    return value


def validate_cors_origins(origins: list[str]) -> list[str]:
    if not origins:
        raise ValueError("CORS_ORIGINS must contain at least one exact origin")

    for origin in origins:
        if origin == "*":
            raise ValueError("Wildcard CORS origins are not allowed")
        parsed = urlsplit(origin)
        hostname = parsed.hostname
        port = parsed.port
        if (
            origin == "null"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not hostname
            or (port is not None and not 1 <= port <= 65535)
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
            or parsed.password
            or "*" in hostname
            or any(character.isspace() for character in origin)
        ):
            raise ValueError(f"Invalid exact CORS origin: {origin}")
    return origins
