"""Example OpenWISP template for the devices (examples/openwisp-template)."""

import json
import os

import pytest

HERE = os.path.join(os.path.dirname(__file__), "..", "examples", "openwisp-template")


def load():
    with open(os.path.join(HERE, "netconsole.json")) as f:
        template = json.load(f)
    with open(os.path.join(HERE, "30-netconsole.sh")) as f:
        script = f.read()
    return template, script


def test_json_matches_the_script():
    template, script = load()
    (item,) = template["config"]["files"]
    assert item == {"path": "/etc/hotplug.d/iface/30-netconsole", "mode": "0755", "contents": script}
    assert set(template["default_values"]) == {"netconsole_server", "netconsole_port"}


def test_netjsonconfig_renders_it():
    netjsonconfig = pytest.importorskip("netjsonconfig")
    template, _ = load()
    context = dict(template["default_values"], name="router-1")
    backend = netjsonconfig.OpenWrt({"general": {}}, templates=[template["config"]], context=context)
    backend.validate()
    tar = backend.generate()
    import tarfile

    with tarfile.open(fileobj=tar, mode="r:gz") as t:
        member = t.getmember("etc/hotplug.d/iface/30-netconsole")
        assert member.mode & 0o777 == 0o755
        text = t.extractfile(member).read().decode()
    assert "DST_IP='192.0.2.10'" in text and "DST_PORT='6666'" in text and "NODE='router-1'" in text
    assert "{{" not in text
