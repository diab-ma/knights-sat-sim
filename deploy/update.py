#!/usr/bin/python3
"""Root-owned forced SSH command. Input: one JSON line with revision and token."""

import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.request import urlopen

from release import REPO, require, select

ROOT = Path('/opt/knightsat')
STATE = ROOT / 'deploy/state'


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, timeout=300, **kwargs).strip()


def inspect(*args):
    return json.loads(run('docker', 'inspect', *args))


def deploy(request):
    # Lock covers validation, pulls, replacement and reopening; never cancel a peer.
    with (ROOT / 'update.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another update holds the host lock') from None
        require(not (STATE / 'active').exists(),
                'Maintenance is already active; use the attended recovery runbook')
        bootstrap = (ROOT / 'bootstrap.sha256').read_text().strip()
        release = select(request['revision'], request['token'], bootstrap)
        sha = release['revision']
        current = inspect('knightsat-server-1', 'knightsat-web-1')
        require(len(current) == 2, 'Expected the existing placeholder stack')
        # Installation records the current images; detect out-of-band replacement.
        allowed = json.loads((ROOT / 'current.json').read_text())
        require({c['Name']: c['Image'] for c in current} == allowed['images'],
                'Running images differ from the last qualified deployment')
        volume = next(m['Name'] for c in current if c['Name'] == '/knightsat-server-1'
                      for m in c['Mounts'] if m['Destination'] == '/data')
        require(volume == 'knightsat_progress', 'Unexpected progress volume')
        images = {s: f'ghcr.io/{REPO}-{s}@{release[s]}' for s in ('server', 'web')}
        # Short-lived workflow token lives only in a private temporary Docker config.
        with tempfile.TemporaryDirectory(prefix='knightsat-registry-') as config:
            env = {**os.environ, 'DOCKER_CONFIG': config, 'REVISION': sha,
                   'SERVER_IMAGE': images['server'], 'WEB_IMAGE': images['web'],
                   'STATE_DIR': str(STATE)}
            run('docker', 'login', 'ghcr.io', '-u', 'github-actions', '--password-stdin',
                input=request['token'], env=env)
            for service, image in images.items():
                run('docker', 'pull', image, env=env)
                info = inspect(image)[0]
                require(info['Config']['Labels'].get('org.opencontainers.image.revision') == sha,
                        f'{service} image revision mismatch')
            compose = ['docker', 'compose', '--project-directory', str(ROOT),
                       '-f', str(ROOT / 'compose.hosting.yml')]
            run(*compose, 'config', '--quiet', env=env)
            pending = {**release, 'images': images, 'previous': allowed}
            (STATE / 'pending.json').write_text(json.dumps(pending, indent=2) + '\n')
            (STATE / 'active').touch()
            print(f'MAINTENANCE: replacing with {sha}', flush=True)
            # No automatic rollback: future schemas may be incompatible.
            run(*compose, 'up', '-d', '--no-build', '--pull', 'never', '--wait',
                '--wait-timeout', '120', env=env)
            deployed = inspect('knightsat-server-1', 'knightsat-web-1')
            for c in deployed:
                service = c['Config']['Labels']['com.docker.compose.service']
                require(c['Image'] == inspect(images[service])[0]['Id'], 'Running image mismatch')
                require(c['State']['Health']['Status'] == 'healthy', 'Container is not healthy')
            require(any(m.get('Name') == volume and m['Destination'] == '/data'
                        for c in deployed for m in c['Mounts']), 'Progress volume changed')
            with urlopen('http://127.0.0.1:8080/revision', timeout=10) as response:
                require(response.read().decode().strip() == sha, 'Origin revision mismatch')
            with urlopen('http://127.0.0.1:8080/health', timeout=10) as response:
                require(json.load(response) == {'status': 'ok'}, 'Origin is unhealthy')
            try:
                run(sys.executable, str(ROOT / 'deploy/check-hosting.py'), '--maintenance')
                run(sys.executable, str(ROOT / 'deploy/check-hosting.py'), '--public')
                # Persist digest references for restarts and attended repair.
                (ROOT / '.env.next').write_text(
                    f'REVISION={sha}\nSERVER_IMAGE={images["server"]}\n'
                    f'WEB_IMAGE={images["web"]}\nSTATE_DIR={STATE}\n')
                (ROOT / '.env.next').replace(ROOT / '.env')
                record = {**release, 'images': {c['Name']: c['Image'] for c in deployed}}
                (ROOT / 'current.next').write_text(json.dumps(record, indent=2) + '\n')
                (ROOT / 'current.next').replace(ROOT / 'current.json')
                (STATE / 'active').unlink()
            except BaseException:
                (STATE / 'active').touch()
                raise
            print(f'DEPLOYED: {sha}; healthy; retained {volume}; CI {release["run"]}', flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        request = json.loads(sys.stdin.buffer.readline(16385))
        require(set(request) == {'revision', 'token'}, 'Unexpected deployment input')
        require(isinstance(request['token'], str) and len(request['token']) < 4096,
                'Invalid workflow token')
        deploy(request)
    except Exception as error:
        # Never echo input or subprocess output: it may contain registry credentials.
        print(f'UPDATE FAILED: {type(error).__name__}: {error}', file=sys.stderr)
        print('Inspect maintenance and pending.json; follow the recovery runbook.', file=sys.stderr)
        sys.exit(1)
