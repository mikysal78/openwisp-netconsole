"""API dei log netconsole con token, utenti e device finti (niente database)."""

import json
import uuid

import django
import pytest
from django.conf import settings

if not settings.configured:
    settings.configure(SECRET_KEY="test-only", ALLOWED_HOSTS=["openwisp.example.com"], USE_TZ=True)
    django.setup()

from django.test import RequestFactory  # noqa: E402

from openwisp_netconsole import api, sources  # noqa: E402

PK = uuid.UUID("05cb6ac3-10a3-4cf3-8968-e1868fe95e34")
GOOD = "a" * 40


class FakeUser:
    def __init__(self):
        self.username, self.is_active, self.is_staff, self.is_superuser = "op", True, True, False
        self.perms, self.orgs = {"config.view_device"}, {"org1"}

    def has_perm(self, perm):
        return perm in self.perms

    def is_manager(self, org):
        return org in self.orgs


class FakeDevice:
    class DoesNotExist(Exception):
        pass

    def __init__(self):
        self.pk, self.name, self.organization_id = PK, "C2600", "org1"
        self.management_ip, self.last_ip = "10.27.22.244", None


class Manager:
    def __init__(self, items, exc):
        self.items, self.exc = items, exc

    def select_related(self, *args):
        return self

    def get(self, **kwargs):
        (value,) = kwargs.values()
        if str(value) not in self.items:
            raise self.exc
        return self.items[str(value)]


@pytest.fixture
def world(monkeypatch, tmp_path):
    user, device = FakeUser(), FakeDevice()

    class Token:
        DoesNotExist = type("DoesNotExist", (Exception,), {})
        objects = Manager({GOOD: type("T", (), {"user": user})()}, None)

    Token.objects.exc = Token.DoesNotExist

    class DeviceModel:
        DoesNotExist = FakeDevice.DoesNotExist
        objects = Manager({str(PK): device}, FakeDevice.DoesNotExist)

        class _meta:
            app_label, model_name = "config", "device"

    log = tmp_path / "netconsole-C2600"
    log.mkdir()
    (log / "netconsole.log").write_text("".join("riga %d\n" % i for i in range(500)))
    monkeypatch.setattr(api, "_token_model", lambda: Token)
    monkeypatch.setattr(api, "_device_model", lambda: DeviceModel)
    monkeypatch.setattr(api.app_settings, "LOG_DIR", str(tmp_path))
    # le chiavi condivise con altri device si provano in test_logfiles
    monkeypatch.setattr(
        sources,
        "device_sources",
        lambda d, model: api.logfiles.device_sources(
            str(tmp_path), [("name", d.name), ("ip", d.management_ip)]
        ),
    )
    return user, device


rf = RequestFactory()


def call(auth="Bearer " + GOOD, method="get", pk=PK, **params):
    kwargs = {"HTTP_AUTHORIZATION": auth} if auth is not None else {}
    path = "/api/v1/netconsole/device/%s/logs/" % pk
    return api.logs(getattr(rf, method)(path, params, HTTP_HOST="openwisp.example.com", **kwargs), pk=pk)


def test_logs(world):
    response = call()
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    (log,) = json.loads(response.content)
    assert log["kind"] == "name" and log["key"] == "C2600"
    assert len(log["lines"]) == api.DEFAULT_LINES and log["lines"][-1] == "riga 499"


@pytest.mark.parametrize("lines,expected", [("5", 5), ("0", 1), ("-3", 1), ("x", 200), ("99999", 500)])
def test_logs_lines(world, lines, expected):
    (log,) = json.loads(call(lines=lines).content)
    assert len(log["lines"]) == expected


@pytest.mark.parametrize(
    "auth", [None, "", "Bearer", "Token " + GOOD, "Bearer " + "b" * 40, "Bearer " + "a" * 200]
)
def test_logs_bad_token(world, auth):
    assert call(auth).status_code == 401


def test_logs_permissions(world):
    user, device = world
    user.perms = set()
    assert call().status_code == 404
    user.perms = {"config.change_device"}
    assert call().status_code == 200
    device.organization_id = "org2"
    assert call().status_code == 404
    user.is_superuser = True
    assert call().status_code == 200
    user.is_staff = False
    assert call().status_code == 404


def test_logs_inactive_or_missing(world):
    user, _ = world
    assert call(pk=uuid.uuid4()).status_code == 404
    user.is_active = False
    assert call().status_code == 401


def test_logs_post_refused(world):
    assert call(method="post").status_code == 405


def test_sources_skip_shared_keys(tmp_path, monkeypatch):
    for key in ("C2600", "10.27.22.244", "10.27.22.9"):
        (tmp_path / ("netconsole-" + key)).mkdir()
    monkeypatch.setattr(sources.app_settings, "LOG_DIR", str(tmp_path))
    monkeypatch.setattr(sources.app_settings, "IP_FALLBACK", True)

    class Query:
        """Altri device: uno si chiama come il nostro, uno ha il suo IP di gestione."""

        def __init__(self, hit=False):
            self.hit = hit

        def exclude(self, **kwargs):
            return self

        def filter(self, *args, **kwargs):
            if kwargs.get("name") == "C2600":
                return Query(True)
            text = str(args[0]) if args else ""
            return Query("10.27.22.244" in text)

        def exists(self):
            return self.hit

    class Model:
        objects = Query()

    device = FakeDevice()
    device.last_ip = "10.27.22.9"
    assert sources.device_sources(device, Model) == [("ip", "10.27.22.9")]


def test_logs_completed_from_previous_file(world, tmp_path):
    log = tmp_path / "netconsole-C2600"
    (log / "netconsole.log").write_text("nuova 1\nnuova 2\n")
    (log / "netconsole.log.1").write_text("vecchia 1\nvecchia 2\nvecchia 3\n")
    (rows,) = json.loads(call(lines="4").content)
    assert rows["lines"] == ["vecchia 2", "vecchia 3", "nuova 1", "nuova 2"]
    (log / "netconsole.log").unlink()
    (rows,) = json.loads(call().content)
    assert rows["lines"] == ["vecchia 1", "vecchia 2", "vecchia 3"]
