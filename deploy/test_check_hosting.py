"""Run without Docker: python3 deploy/test_check_hosting.py."""

import importlib
import io
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

hosting = importlib.import_module("check-hosting")


class ContainerUserTest(unittest.TestCase):
    def test_main_checks_user_before_group(self):
        root_users = (
            "", "0", "root", "0:0", "0:10001", "root:root", "root:10001",
            ":10001", "00", "00:10001",
        )
        for user in root_users + (
            "10001", "10001:10001", "10001:0", "101", "nginx", "nginx:root",
        ):
            for service in ("server", "web"):
                with self.subTest(user=user, service=service):
                    containers = [
                        {
                            "Name": f"/knightsat-{name}-1",
                            "Config": {"User": user if name == service else "10001"},
                            "HostConfig": {
                                "ReadonlyRootfs": True,
                                "CapDrop": ["ALL"],
                                "SecurityOpt": ["no-new-privileges:true"],
                                "Memory": 1024,
                                "MemorySwap": 1024,
                                "NanoCpus": 1000000000,
                                "PidsLimit": 64,
                                "Privileged": False,
                                "LogConfig": {
                                    "Type": "local",
                                    "Config": {"max-size": "10m", "max-file": "3"},
                                },
                                "RestartPolicy": {"Name": "unless-stopped"},
                                "PortBindings": {} if name == "server" else {
                                    "8080/tcp": [
                                        {"HostIp": "127.0.0.1", "HostPort": "8080"}
                                    ]
                                },
                            },
                            "Mounts": [],
                            "NetworkSettings": {
                                "Networks": dict.fromkeys(
                                    ["knightsat_backend"] if name == "server" else
                                    ["knightsat_backend", "knightsat_frontend"], {}
                                ),
                            },
                        }
                        for name in ("server", "web")
                    ]
                    with (
                        patch.object(hosting, "check_origin"),
                        patch.object(hosting.subprocess, "check_output", side_effect=[
                            json.dumps(containers), json.dumps([{"Internal": True}])
                        ]),
                        redirect_stdout(io.StringIO()) as output,
                    ):
                        if user in root_users:
                            with self.assertRaisesRegex(AssertionError, "non-root"):
                                hosting.main()
                            self.assertNotIn("PASS: non-root", output.getvalue())
                        else:
                            hosting.main()
                            self.assertIn("PASS: non-root", output.getvalue())


if __name__ == "__main__":
    unittest.main()
