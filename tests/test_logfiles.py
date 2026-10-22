import gzip
import os

import pytest

from openwisp_netconsole import logfiles as lf


@pytest.fixture
def logdir(tmp_path):
    root = tmp_path / "router-logs"
    root.mkdir()
    d = root / "netconsole-C2600"
    d.mkdir()
    (d / "netconsole.log").write_bytes(b"riga 1\nriga 2\n")
    (d / "netconsole.log.1").write_bytes(b"vecchia\n")
    with gzip.open(d / "netconsole.log.2.gz", "wb") as f:
        f.write(b"vecchissima\n")
    (d / "altro.txt").write_bytes(b"non elencato\n")
    (root / "netconsole-10.27.22.244").mkdir()
    (root / "netconsole-10.27.22.244" / "netconsole.log").write_bytes(b"da ip\n")
    # segreto fuori dalla radice dei log
    (tmp_path / "segreto").mkdir()
    (tmp_path / "segreto" / "netconsole.log").write_bytes(b"SEGRETO\n")
    return root


def test_source_keys():
    keys = lf.source_keys("C2600", ["10.27.22.244", "10.27.22.244", None, "x", "::1"])
    assert keys == [("name", "C2600"), ("ip", "10.27.22.244"), ("ip", "::1")]


@pytest.mark.parametrize(
    "name", ["", "../etc", ".hidden", "a/b", "a b", "a" * 65, "10.27.22.244", "aa:bb:cc:dd:ee:ff"]
)
def test_source_keys_rifiuta_nomi(name):
    assert lf.source_keys(name, []) == []


def test_device_sources(logdir):
    keys = lf.source_keys("C2600", ["10.27.22.244", "10.27.22.1"])
    assert lf.device_sources(str(logdir), keys) == [("name", "C2600"), ("ip", "10.27.22.244")]


def test_symlink_fuori_dalla_radice(logdir, tmp_path):
    os.symlink(tmp_path / "segreto", logdir / "netconsole-evil")
    assert lf.device_sources(str(logdir), [("name", "evil")]) == []
    assert lf.list_files(str(logdir), "evil") == []
    assert lf.open_file(str(logdir), "evil", "netconsole.log") is None
    assert lf.read_log(str(logdir), "evil") == ([], "", True)


def test_file_symlink(logdir, tmp_path):
    d = logdir / "netconsole-C2600"
    os.symlink(tmp_path / "segreto" / "netconsole.log", d / "netconsole.log.3")
    assert "netconsole.log.3" not in [n for n, _ in lf.list_files(str(logdir), "C2600")]
    assert lf.open_file(str(logdir), "C2600", "netconsole.log.3") is None


@pytest.mark.parametrize(
    "key,filename",
    [
        ("..", "netconsole.log"),
        ("../segreto", "netconsole.log"),
        ("C2600", "../netconsole-10.27.22.244/netconsole.log"),
        ("C2600", "altro.txt"),
        ("C2600", "/etc/passwd"),
        ("C2600/../..", "netconsole.log"),
    ],
)
def test_open_file_rifiuta(logdir, key, filename):
    assert lf.open_file(str(logdir), key, filename) is None


def test_list_files(logdir):
    assert lf.list_files(str(logdir), "C2600") == [
        ("netconsole.log", 14),
        ("netconsole.log.1", 8),
        ("netconsole.log.2.gz", os.path.getsize(logdir / "netconsole-C2600" / "netconsole.log.2.gz")),
    ]


def test_read_log_coda_e_incrementale(logdir):
    path = logdir / "netconsole-C2600" / "netconsole.log"
    lines, pos, reset = lf.read_log(str(logdir), "C2600")
    assert (lines, reset) == (["riga 1", "riga 2"], True)
    # riga ancora in scrittura: non va restituita finche' non e' completa
    with open(path, "ab") as f:
        f.write(b"riga 3\nriga 4 a meta")
    lines, pos, reset = lf.read_log(str(logdir), "C2600", pos)
    assert (lines, reset) == (["riga 3"], False)
    with open(path, "ab") as f:
        f.write(b"\n")
    lines, pos, reset = lf.read_log(str(logdir), "C2600", pos)
    assert (lines, reset) == (["riga 4 a meta"], False)
    lines, pos2, reset = lf.read_log(str(logdir), "C2600", pos)
    assert (lines, pos2, reset) == ([], pos, False)


def test_read_log_rotazione(logdir):
    path = logdir / "netconsole-C2600" / "netconsole.log"
    _, pos, _ = lf.read_log(str(logdir), "C2600")
    os.rename(path, str(path) + ".1")
    path.write_bytes(b"nuovo file\n")
    lines, _, reset = lf.read_log(str(logdir), "C2600", pos)
    assert (lines, reset) == (["nuovo file"], True)


@pytest.mark.parametrize("pos", ["", "x", "1:2:3", "abc:def", "-1:-1", "99999999999:0"])
def test_read_log_pos_non_valida(logdir, pos):
    lines, _, reset = lf.read_log(str(logdir), "C2600", pos)
    assert (lines, reset) == (["riga 1", "riga 2"], True)


def test_read_log_limiti(logdir):
    path = logdir / "netconsole-C2600" / "netconsole.log"
    path.write_bytes(b"".join(b"riga %d\n" % i for i in range(5000)))
    lines, _, _ = lf.read_log(str(logdir), "C2600", max_lines=100, max_bytes=4096)
    assert len(lines) == 100 and lines[-1] == "riga 4999"
    lines, _, _ = lf.read_log(str(logdir), "C2600", max_lines=10000, max_bytes=4096)
    # la prima riga, tagliata dal limite di byte, viene scartata
    assert all(line.startswith("riga ") for line in lines) and len("\n".join(lines)) < 4096


def test_read_log_utf8_non_valido(logdir):
    path = logdir / "netconsole-C2600" / "netconsole.log"
    path.write_bytes(b"ok \xff\xfe <script>\n")
    lines, _, _ = lf.read_log(str(logdir), "C2600")
    assert lines == ["ok �� <script>"]
