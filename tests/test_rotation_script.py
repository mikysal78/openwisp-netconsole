"""Root rotation script (examples/ansible/templates/router-logs-rotation.py.j2).

The script is rendered with test paths and run with --config-only: it must
apply valid values and reject anything else, falling back to the playbook
values without ever echoing the untrusted content.
"""

import json
import os
import subprocess
import sys

import pytest

from openwisp_netconsole import rotation

jinja2 = pytest.importorskip("jinja2")

TEMPLATE = os.path.join(
    os.path.dirname(__file__),
    "..",
    "examples",
    "ansible",
    "roles",
    "router_logs",
    "templates",
    "router-logs-rotation.py.j2",
)
DEFAULTS = {"frequency": "daily", "max_size_mb": 50, "retention_days": 30, "max_files": 30}


@pytest.fixture
def script(tmp_path):
    for d in ("ow", "st", "logs"):
        (tmp_path / d).mkdir()
    with open(TEMPLATE) as f:
        text = jinja2.Template(f.read(), keep_trailing_newline=True).render(
            ansible_managed="test",
            router_logs_rotation_settings_file=str(tmp_path / "ow" / "rotation.json"),
            router_logs_rotation_status_file=str(tmp_path / "st" / "status.json"),
            router_logs_dir=str(tmp_path / "logs"),
            router_logs_frequency="daily",
            router_logs_max_size_mb=50,
            router_logs_retention_days=30,
            router_logs_max_files=30,
        )
    text = text.replace("/etc/logrotate-router-logs.conf", str(tmp_path / "logrotate.conf"))
    path = tmp_path / "rotation.py"
    path.write_text(text)

    def run(settings=None):
        if settings is not None:
            (tmp_path / "ow" / "rotation.json").write_text(settings)
        subprocess.run([sys.executable, "-I", str(path), "--config-only"], timeout=10, capture_output=True)
        status = json.loads((tmp_path / "st" / "status.json").read_text())
        conf = (tmp_path / "logrotate.conf").read_text()
        return status, conf

    run.tmp = tmp_path
    return run


def test_same_limits_as_the_module():
    with open(TEMPLATE) as f:
        text = f.read()
    for name, (low, high) in rotation.LIMITS.items():
        assert '"%s": (%d, %d),' % (name, low, high) in text


def test_playbook_values_without_settings(script):
    status, conf = script()
    assert (status["source"], status["settings"], status["error"]) == ("playbook", DEFAULTS, "")
    assert "    daily\n    maxsize 50M\n    rotate 30\n    maxage 30\n" in conf


def test_admin_values(script):
    values = {"frequency": "weekly", "max_size_mb": 100, "retention_days": 7, "max_files": 10}
    status, conf = script(json.dumps(values))
    assert (status["source"], status["settings"], status["error"]) == ("admin", values, "")
    assert "    weekly\n    maxsize 100M\n    rotate 10\n    maxage 7\n" in conf


@pytest.mark.parametrize(
    "settings",
    [
        '{"frequency": "daily\\n    postrotate\\n        rm -rf /", "max_size_mb": 50,'
        ' "retention_days": 30, "max_files": 30}',
        '{"frequency": "daily", "max_size_mb": "50M\\n}", "retention_days": 30, "max_files": 30}',
        '{"frequency": "daily", "max_size_mb": 1, "retention_days": 30, "max_files": 30}',
        '{"frequency": "daily", "max_size_mb": 50, "retention_days": 1, "max_files": 30}',
        '{"frequency": "daily", "max_size_mb": 50, "retention_days": 30, "max_files": true}',
        "[1, 2, 3]",
        "{not json",
        '{"a": "' + "x" * 5000 + '"}',
    ],
)
def test_rejects_invalid_settings(script, settings):
    status, conf = script(settings)
    assert status["source"] == "playbook" and status["settings"] == DEFAULTS
    assert status["error"]
    assert "rm -rf" not in conf and "rm -rf" not in status["error"]
    assert "postrotate\n        /usr/lib/rsyslog/rsyslog-rotate\n    endscript" in conf


def test_rejects_symlink(script):
    target = script.tmp / "secret.json"
    target.write_text(json.dumps(dict(DEFAULTS, retention_days=7)))
    os.symlink(target, script.tmp / "ow" / "rotation.json")
    status, _ = script()
    assert status["source"] == "playbook" and status["error"]


def test_fifo_does_not_block(script):
    os.mkfifo(script.tmp / "ow" / "rotation.json")
    status, _ = script()
    assert status["source"] == "playbook" and "regular file" in status["error"]
