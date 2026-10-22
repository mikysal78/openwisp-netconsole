import json
import os

import pytest

from openwisp_netconsole import rotation

OK = {"frequency": "daily", "max_size_mb": 50, "retention_days": 30, "max_files": 30}


def test_validate_ok():
    assert rotation.validate(dict(OK, extra="ignorato")) == OK


@pytest.mark.parametrize(
    "change",
    [
        {"frequency": "hourly"},
        {"frequency": "daily\nmissingok"},
        {"frequency": None},
        {"max_size_mb": 4},
        {"max_size_mb": 101},
        {"max_size_mb": "50"},
        {"max_size_mb": 50.5},
        {"max_size_mb": True},
        {"retention_days": -1},
        {"retention_days": 1},
        {"retention_days": 91},
        {"max_files": 6},
        {"max_files": 61},
        {"max_files": "30\npostrotate"},
        {"max_files": None},
    ],
)
def test_validate_rifiuta(change):
    with pytest.raises(ValueError):
        rotation.validate(dict(OK, **change))


@pytest.mark.parametrize("values", [None, [], "daily", 3])
def test_validate_non_oggetto(values):
    with pytest.raises(ValueError):
        rotation.validate(values)


def test_write_settings_atomico(tmp_path):
    path = tmp_path / "rotation.json"
    rotation.write_settings(str(path), OK)
    assert json.loads(path.read_text()) == OK
    assert oct(path.stat().st_mode & 0o777) == "0o644"
    assert [p.name for p in tmp_path.iterdir()] == ["rotation.json"]
    with pytest.raises(ValueError):
        rotation.write_settings(str(path), dict(OK, max_files=0))
    assert json.loads(path.read_text()) == OK


def test_read_json_symlink_e_limiti(tmp_path):
    secret = tmp_path / "segreto.json"
    secret.write_text('{"a": 1}')
    os.symlink(secret, tmp_path / "link.json")
    assert rotation.read_json(str(tmp_path / "link.json")) is None
    assert rotation.read_json(str(tmp_path / "manca.json")) is None
    big = tmp_path / "grande.json"
    big.write_text('{"a": "' + "x" * 5000 + '"}')
    assert rotation.read_json(str(big)) is None
    bad = tmp_path / "rotto.json"
    bad.write_text("{non json")
    assert rotation.read_json(str(bad)) is None
    assert rotation.read_json(str(secret)) == {"a": 1}


def test_read_status(tmp_path):
    p = tmp_path / "status.json"
    p.write_text("[1, 2]")
    assert rotation.read_status(str(p)) is None
    p.write_text('{"applied": "2026-10-23T00:17:00+02:00", "error": ""}')
    assert rotation.read_status(str(p))["applied"].startswith("2026")


@pytest.mark.parametrize(
    "name,low,high", [("max_size_mb", 5, 100), ("retention_days", 7, 90), ("max_files", 7, 60)]
)
def test_limiti_estremi(name, low, high):
    assert rotation.validate(dict(OK, **{name: low}))[name] == low
    assert rotation.validate(dict(OK, **{name: high}))[name] == high


def test_limiti_uguali_allo_script_di_root():
    # lo script di root (repo openwisp2) ricontrolla gli stessi limiti
    here = os.path.dirname(__file__)
    script = os.path.join(here, "..", "..", "openwisp2", "templates", "router-logs-rotation.py.j2")
    if not os.path.exists(script):
        pytest.skip("repo openwisp2 non presente accanto")
    text = open(script).read()
    for name, (low, high) in rotation.LIMITS.items():
        assert '"%s": (%d, %d),' % (name, low, high) in text
