"""Check the private origin on the VM: python3 deploy/check-hosting.py."""

import json
import subprocess
import sys
from http.client import HTTPSConnection
from urllib.error import HTTPError
from urllib.request import urlopen


def check_public() -> None:
    """Check the deployed Access gate without credentials or redirects."""

    for method, path, websocket in (
        ("GET", "/", False),
        ("GET", "/health", False),
        ("GET", "/api/session", False),
        ("POST", "/api/attempts", False),
        ("GET", "/api/attempts/hosting-check/events", True),
        ("GET", "/api/hosting-check-missing", False),
        ("GET", "/raw", False),
        ("GET", "/receive", False),
        ("GET", "/internal", False),
        ("GET", "/docs", False),
        ("GET", "/openapi.json", False),
    ):
        for forged in (False, True):
            # Avoid testing Cloudflare's generic Python-user-agent bot denial.
            headers = {"User-Agent": "Mozilla/5.0"}
            if websocket:
                headers.update(
                    {
                        "Connection": "Upgrade",
                        "Upgrade": "websocket",
                        "Sec-WebSocket-Version": "13",
                        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                        "Origin": "https://knightsat.radio-ranger.com",
                    }
                )
            if forged:
                headers.update(
                    {
                        "Cf-Access-Jwt-Assertion": "invalid",
                        "Cookie": "CF_Authorization=invalid",
                    }
                )
            connection = HTTPSConnection("knightsat.radio-ranger.com", timeout=15)
            try:
                connection.request(method, path, headers=headers)
                response = connection.getresponse()
                assert response.status == 302, (method, path, response.status)
                assert response.headers.get("Location", "").startswith(
                    "https://noisy-cherry-b0bc.cloudflareaccess.com/cdn-cgi/access/login/"
                ), f"Expected Access login redirect: {path}"
            finally:
                connection.close()
            print(
                f"PASS: {method} {path} WS={websocket} malformed={forged}: Access 302"
            )
    print("This proves edge denial only, not live WebSockets or individual JWT claims.")


def get(path: str) -> tuple[int, str, bytes]:
    try:
        response = urlopen(f"http://127.0.0.1:8080{path}", timeout=5)
    except HTTPError as error:
        response = error
    with response:
        return response.status, response.headers.get_content_type(), response.read()


def check_origin(maintenance: bool = False) -> None:
    status, kind, body = get("/")
    if maintenance:
        assert status == 503 and b"Temporarily unavailable" in body
    else:
        assert status == 200 and kind == "text/html" and b'id="root"' in body
    assert get("/challenges/hello")[2] == body, "SPA navigation failed"
    status, kind, body = get("/health")
    assert status == 200 and kind == "application/json"
    assert json.loads(body) == {"status": "ok"}
    status, kind, _ = get("/api/hosting-check-missing")
    if maintenance:
        assert status == 503, "API is not in maintenance"
    else:
        assert status == 404 and kind == "application/json", "API reached SPA fallback"
    for path in (
        "/assets/missing.js",
        "/raw/test",
        "/receive/test",
        "/internal/test",
        "/docs",
        "/openapi.json",
    ):
        assert get(path)[0] == 404, f"Unexpected route exposed: {path}"
    print("PASS: built UI, SPA routes, backend health, API proxy, restricted paths")


def main(maintenance: bool = False) -> None:
    check_origin(maintenance)
    containers = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "knightsat-server-1", "knightsat-web-1"], text=True
        )
    )
    for container in containers:
        config = container["HostConfig"]
        user = container["Config"]["User"].partition(":")[0]
        assert user not in ("", "root") and not (
            user.isdecimal() and int(user) == 0
        ), "Container must specify a non-root user"
        assert config["ReadonlyRootfs"] and config["CapDrop"] == ["ALL"]
        assert "no-new-privileges:true" in config["SecurityOpt"]
        assert config["Memory"] > 0 and config["NanoCpus"] > 0
        assert config["MemorySwap"] == config["Memory"], "Extra swap allowed"
        assert config["PidsLimit"] > 0
        assert not config["Privileged"]
        assert config["LogConfig"] == {
            "Type": "local",
            "Config": {"max-size": "10m", "max-file": "3"},
        }
        assert config["RestartPolicy"]["Name"] == "unless-stopped"
        bindings = config.get("PortBindings") or {}
        if container["Name"] == "/knightsat-server-1":
            assert not bindings, "Backend must not publish a host port"
        else:
            assert bindings == {
                "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "8080"}]
            }, "Web port must bind only to loopback"
        assert not any(
            mount["Source"].endswith("docker.sock")
            or mount["Destination"].endswith("docker.sock")
            for mount in container["Mounts"]
        )
        networks = set(container["NetworkSettings"]["Networks"])
        expected = {"knightsat_backend"}
        if container["Name"] == "/knightsat-web-1":
            expected.add("knightsat_frontend")
        assert networks == expected, (container["Name"], networks)
    backend = json.loads(
        subprocess.check_output(
            ["docker", "network", "inspect", "knightsat_backend"], text=True
        )
    )[0]
    assert backend["Internal"], "Backend network permits external routing"
    print("PASS: non-root containers, read-only images, limits, private ports, restart")
    print("Challenges, Access, and live WebSockets need separate acceptance tests.")


if __name__ == "__main__":
    if sys.argv[1:] == ["--public"]:
        check_public()
    elif sys.argv[1:] == ["--origin-only"]:
        check_origin()
    elif sys.argv[1:] == ["--maintenance"]:
        main(maintenance=True)
    elif not sys.argv[1:]:
        main()
    else:
        raise SystemExit(
            "Usage: python3 deploy/check-hosting.py [--public|--origin-only|--maintenance]"
        )
