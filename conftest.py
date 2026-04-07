#!/usr/bin/env python3
"""
Test-only compatibility shims for optional third-party dependencies.
"""

from __future__ import annotations

import json
import subprocess
import sys
import types


try:
    import requests as _requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")

    class HTTPError(Exception):
        """Minimal requests.HTTPError shim for tests."""

    class RequestException(Exception):
        """Minimal requests.RequestException shim for tests."""

    def _unpatched_request(*args, **kwargs):
        raise RuntimeError(
            "requests stub invoked unexpectedly; tests should patch module-level requests calls"
        )

    requests_stub.get = _unpatched_request
    requests_stub.post = _unpatched_request
    requests_stub.patch = _unpatched_request
    requests_stub.put = _unpatched_request
    requests_stub.delete = _unpatched_request
    requests_stub.HTTPError = HTTPError
    requests_stub.RequestException = RequestException
    requests_stub.exceptions = types.SimpleNamespace(
        HTTPError=HTTPError,
        RequestException=RequestException,
    )

    sys.modules["requests"] = requests_stub


try:
    import yaml as _yaml  # noqa: F401
except ModuleNotFoundError:
    yaml_stub = types.ModuleType("yaml")

    class YAMLError(Exception):
        """Minimal yaml.YAMLError shim for tests."""

    def safe_load(stream):
        if hasattr(stream, "read"):
            content = stream.read()
        else:
            content = stream

        text = "" if content is None else str(content)
        if not text.strip():
            return None

        ruby_script = (
            'require "yaml"; '
            'require "json"; '
            'print JSON.dump(YAML.safe_load(STDIN.read, aliases: true))'
        )
        result = subprocess.run(
            ["ruby", "-e", ruby_script],
            input=text,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise YAMLError(result.stderr.strip() or "YAML parse failed")
        return json.loads(result.stdout) if result.stdout.strip() else None

    yaml_stub.safe_load = safe_load
    yaml_stub.YAMLError = YAMLError

    sys.modules["yaml"] = yaml_stub
