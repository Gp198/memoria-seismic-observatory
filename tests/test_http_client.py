from pathlib import Path

import pytest

from src.http_client import ssl_verify_setting


def test_ssl_verify_defaults_to_true(monkeypatch):
    monkeypatch.delenv("MEMORIA_CA_BUNDLE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)
    monkeypatch.delenv("MEMORIA_SSL_VERIFY", raising=False)
    assert ssl_verify_setting() is True


def test_custom_ca_bundle(monkeypatch, tmp_path: Path):
    bundle = tmp_path / "company.pem"
    bundle.write_text("placeholder", encoding="utf-8")
    monkeypatch.setenv("MEMORIA_CA_BUNDLE", str(bundle))
    assert ssl_verify_setting() == str(bundle)


def test_missing_custom_ca_bundle_fails(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("MEMORIA_CA_BUNDLE", str(tmp_path / "missing.pem"))
    with pytest.raises(FileNotFoundError):
        ssl_verify_setting()
