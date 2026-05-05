from scaffold.db.mysql_url import ensure_mysql_utf8mb4_charset


def test_mysql_adds_charset_when_missing() -> None:
    url = "mysql+asyncmy://u:p@h:3306/db"
    assert ensure_mysql_utf8mb4_charset(url) == (
        "mysql+asyncmy://u:p@h:3306/db?charset=utf8mb4"
    )


def test_mysql_preserves_existing_utf8mb4() -> None:
    url = "mysql+asyncmy://u:p@h/db?charset=utf8mb4"
    assert ensure_mysql_utf8mb4_charset(url) == url


def test_mysql_replaces_utf8() -> None:
    url = "mysql+asyncmy://u:p@h/db?charset=utf8"
    assert ensure_mysql_utf8mb4_charset(url) == (
        "mysql+asyncmy://u:p@h/db?charset=utf8mb4"
    )


def test_non_mysql_unchanged() -> None:
    url = "postgresql://u:p@h/db"
    assert ensure_mysql_utf8mb4_charset(url) == url
