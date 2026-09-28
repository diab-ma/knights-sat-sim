#!/usr/bin/env python3
"""One-time, attended bootstrap installation: sudo python3 deploy/install.py KEY.pub."""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

from release import require

source = Path(__file__).resolve().parent.parent
root = Path('/opt/knightsat')
require(os.geteuid() == 0, 'Run through an attended private sudo login')
require(not (root / 'current.json').exists(), 'Already installed; do not requalify automatically')
try:
    pwd.getpwnam('knightsat-deploy')
    raise RuntimeError('Unexpected existing deploy identity; inspect before installation')
except KeyError:
    pass
for directory in (root, root / 'deploy'):
    require(not directory.is_symlink() and directory.stat().st_uid == 0
            and directory.stat().st_mode & 0o022 == 0,
            f'Expected root-owned, non-writable directory: {directory}')
key = Path(sys.argv[1]).read_text().strip()
require(re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\r\n]+)?', key), 'Expected one Ed25519 public key')
subprocess.run(['python3', str(root / 'deploy/check-hosting.py')], check=True)
containers = json.loads(subprocess.check_output(
    ['docker', 'inspect', 'knightsat-server-1', 'knightsat-web-1'], text=True))
require({c['Config']['Image'] for c in containers} == {
    'knightsat-server:hosting-20260928', 'knightsat-web:hosting-20260928'},
    'Only the inspected historical placeholder may be bootstrapped; review unexpected images')
# Verify the running API bytes, not a claimed idle/session endpoint.
actual = subprocess.check_output(['docker', 'exec', 'knightsat-server-1',
                                  'cat', '/app/api/main.py'])
require(actual == (source / 'server/api/main.py').read_bytes(), 'Running API differs from placeholder')
(root / 'deploy/state').mkdir(mode=0o755, exist_ok=True)
require(not (root / 'deploy/state').is_symlink(), 'State cannot be a symlink')
os.chown(root / 'deploy/state', 0, 0)
os.chmod(root / 'deploy/state', 0o755)
for name in ('release.py', 'update.py', 'check-hosting.py'):
    require(not (root / 'deploy' / name).is_symlink(), 'Script cannot be a symlink')
    shutil.copyfile(source / 'deploy' / name, root / 'deploy' / name)
    os.chown(root / 'deploy' / name, 0, 0)
    os.chmod(root / 'deploy' / name, 0o755 if name == 'update.py' else 0o644)
for origin, destination in ((source / 'compose.hosting.yml', root / 'compose.hosting.yml'),
                            (source / 'deploy/bootstrap.sha256', root / 'bootstrap.sha256')):
    require(not destination.is_symlink(), 'Configuration cannot be a symlink')
    shutil.copyfile(origin, destination)
    os.chown(destination, 0, 0)
    os.chmod(destination, 0o644)
record = {'revision': 'historical-placeholder',
          'images': {c['Name']: c['Image'] for c in containers}}
subprocess.run(['useradd', '--system', '--create-home', '--shell', '/bin/sh',
                'knightsat-deploy'], check=True)
home = Path(pwd.getpwnam('knightsat-deploy').pw_dir)
os.chown(home, 0, 0)
os.chmod(home, 0o755)
(home / '.ssh').mkdir(mode=0o755)
command = '/usr/bin/sudo -n /opt/knightsat/deploy/update.py'
authorized = home / '.ssh/authorized_keys'
authorized.write_text(f'restrict,command="{command}" {key}\n')
# SSH needs the account to read its root-owned key file.
os.chmod(authorized, 0o644)
sudoers = Path('/etc/sudoers.d/knightsat-deploy')
sudoers.write_text('knightsat-deploy ALL=(root) NOPASSWD: /opt/knightsat/deploy/update.py ""\n')
os.chmod(sudoers, 0o440)
subprocess.run(['visudo', '-cf', str(sudoers)], check=True)
(root / 'current.json').write_text(json.dumps(record, indent=2)+'\n')
print('Installed forced-command deployment identity. No containers replaced.')
