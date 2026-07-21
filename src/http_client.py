from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

import requests

_TLS_CONFIGURED = False


def configure_system_trust_store() -> None:
    """Use the operating-system trust store when possible.

    On Windows this allows Requests/urllib3 to trust enterprise or antivirus
    inspection roots already installed in the Windows certificate store.
    """
    global _TLS_CONFIGURED
    if _TLS_CONFIGURED:
        return

    use_system_store = os.getenv("MEMORIA_USE_SYSTEM_TRUST_STORE", "true").strip().lower()
    if use_system_store not in {"0", "false", "no", "off"}:
        try:
            import truststore

            truststore.inject_into_ssl()
        except ImportError:
            # Requests will continue with its normal certificate bundle.
            pass

    _TLS_CONFIGURED = True


def ssl_verify_setting() -> bool | str:
    """Return the Requests `verify` value.

    Secure priority:
    1. Explicit MEMORIA_CA_BUNDLE / REQUESTS_CA_BUNDLE path.
    2. System trust store, configured by truststore.
    3. Standard Requests verification.

    MEMORIA_SSL_VERIFY=false exists only for isolated troubleshooting and
    should never be used for normal ingestion or automation.
    """
    ca_bundle = (
        os.getenv("MEMORIA_CA_BUNDLE")
        or os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("CURL_CA_BUNDLE")
    )
    if ca_bundle:
        path = Path(ca_bundle).expanduser()
        if not path.exists():
            raise FileNotFoundError(
                f"O certificado CA configurado não existe: {path}. "
                "Corrija MEMORIA_CA_BUNDLE/REQUESTS_CA_BUNDLE."
            )
        return str(path)

    verify_value = os.getenv("MEMORIA_SSL_VERIFY", "true").strip().lower()
    if verify_value in {"0", "false", "no", "off"}:
        warnings.warn(
            "A validação TLS foi desativada por MEMORIA_SSL_VERIFY=false. "
            "Use apenas para diagnóstico temporário numa rede controlada.",
            RuntimeWarning,
            stacklevel=2,
        )
        return False

    return True


def create_session() -> requests.Session:
    configure_system_trust_store()
    session = requests.Session()
    session.verify = ssl_verify_setting()
    return session


def request_diagnostics() -> dict[str, Any]:
    configure_system_trust_store()
    verify = ssl_verify_setting()
    return {
        "system_trust_store_enabled": os.getenv(
            "MEMORIA_USE_SYSTEM_TRUST_STORE", "true"
        ).strip().lower()
        not in {"0", "false", "no", "off"},
        "verify": verify,
        "custom_ca_bundle": verify if isinstance(verify, str) else None,
        "https_proxy": os.getenv("HTTPS_PROXY") or os.getenv("https_proxy"),
        "requests_ca_bundle": os.getenv("REQUESTS_CA_BUNDLE"),
    }
