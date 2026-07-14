import gzip
import json
import zlib
from pathlib import Path

import pytest

from fmva.config.models import SecConfig
from fmva.exceptions import SecRequestError
from fmva.sec.client import SecClient, _decode_response_body


def config(tmp_path: Path) -> SecConfig:
    return SecConfig(
        user_agent="Researcher researcher@domain.test",
        max_retries=2,
        requests_per_second=10,
        cache_directory=tmp_path,
    )


def test_client_caches_successful_response(tmp_path: Path) -> None:
    calls = []

    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        calls.append((url, headers, timeout))
        return {"ok": True}

    client = SecClient(config(tmp_path), transport=transport, sleeper=lambda _: None)
    assert client.get_json("https://example.test/a") == {"ok": True}
    assert client.get_json("https://example.test/a") == {"ok": True}
    assert len(calls) == 1
    assert "researcher@domain.test" in calls[0][1]["User-Agent"]


def test_client_retries_and_reports_failure(tmp_path: Path) -> None:
    calls = 0

    def transport(url: str, headers: dict[str, str], timeout: float) -> dict:
        nonlocal calls
        calls += 1
        raise TimeoutError("timeout")

    client = SecClient(config(tmp_path), transport=transport, sleeper=lambda _: None)
    with pytest.raises(SecRequestError, match="3 attempt"):
        client.get_json("https://example.test/fail")
    assert calls == 3


def test_sec_transport_decodes_gzip_and_deflate_content() -> None:
    payload = json.dumps({"ok": True}).encode("utf-8")

    assert json.loads(_decode_response_body(gzip.compress(payload), "gzip")) == {"ok": True}
    assert json.loads(_decode_response_body(zlib.compress(payload), "deflate")) == {"ok": True}
