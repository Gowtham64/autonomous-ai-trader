"""Latest public marks. The quote poll writes them. The trading cycle reads them."""

_quotes: list[dict] = []


def publish(items: list[dict]) -> None:
    global _quotes
    _quotes = [dict(item) for item in items]


def snapshot() -> list[dict]:
    return [dict(item) for item in _quotes]
