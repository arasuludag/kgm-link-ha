"""Test harness for the KGM Link integration.

These tests deliberately run WITHOUT Home Assistant installed. The parts worth testing
— the request bodies and the status parsing — are pure Python, and keeping them free of
the HA test rig means they run anywhere, including a bare CI job.

The package's real `__init__.py` imports Home Assistant, so the modules under test are
loaded as a synthetic `kgm` package that skips it.
"""

from __future__ import annotations

import pathlib
import sys
import types

PKG_DIR = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "kgm_link"


def _install_stubs() -> None:
    if "kgm" in sys.modules:
        return

    package = types.ModuleType("kgm")
    package.__path__ = [str(PKG_DIR)]
    sys.modules["kgm"] = package

    aiohttp = types.ModuleType("aiohttp")
    aiohttp.ClientSession = type("ClientSession", (), {})
    sys.modules.setdefault("aiohttp", aiohttp)

    # crypto.py needs the `cryptography` package and does nothing the command bodies
    # depend on, so it is stubbed rather than imported.
    crypto = types.ModuleType("kgm.crypto")
    crypto.load_public_key = lambda blob: object()
    crypto.envelope_headers = lambda key, token=None: {}
    sys.modules["kgm.crypto"] = crypto


_install_stubs()
