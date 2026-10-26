import logging
from scaffold.browser.manager import BrowserlessLogFilter


def test_management_request_logging_redacts_token():
    record = logging.LogRecord(
        "httpx",
        logging.INFO,
        "test",
        1,
        "HTTP %s",
        ("http://browserless/config?token=synthetic-secret&timeout=60",),
        None,
    )
    assert BrowserlessLogFilter().filter(record)
    assert "synthetic-secret" not in record.getMessage()
    assert "token=<redacted>&timeout=60" in record.getMessage()
