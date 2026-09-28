"""Safe failure checks: python3 deploy/test_release.py (no live server)."""
import copy
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import release

update = importlib.import_module('update')
SHA = 'a' * 40
TREE = [{'path': 'server/api/main.py', 'mode': '100644', 'sha': 'b' * 40, 'type': 'blob'}]
FINGERPRINT = release.fingerprint(TREE)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.responses = [
            {'status': 'ahead'}, {'tree': TREE, 'truncated': False},
            {'workflow_runs': [{'id': 1, 'run_attempt': 1, 'head_sha': SHA, 'head_branch': 'main',
                                'event': 'push', 'status': 'completed',
                                'conclusion': 'success', 'html_url': 'https://github.com/run/1'}]},
            {'total_count': len(release.REQUIRED), 'jobs': [
                {'name': name, 'conclusion': 'success'} for name in release.REQUIRED]},
            {'artifacts': [{'name': 'release-1', 'expired': False, 'id': 2}]},
            {'revision': SHA, 'server': 'sha256:'+'c'*64, 'web': 'sha256:'+'d'*64},
        ]

    def test_selection_and_refusals(self):
        with patch.object(release, 'github', side_effect=self.responses):
            self.assertEqual(release.select(SHA, 'fixture', FINGERPRINT)['revision'], SHA)
        changes = [(0, 'status', 'diverged'), (1, 'truncated', True),
                   (2, 'workflow_runs', []), (3, 'jobs', []),
                   (4, 'artifacts', []), (5, 'revision', 'e'*40),
                   (5, 'server', 'latest')]
        for index, key, value in changes:
            responses = copy.deepcopy(self.responses)
            responses[index][key] = value
            with self.subTest(key=key), patch.object(release, 'github', side_effect=responses):
                with self.assertRaises(RuntimeError):
                    release.select(SHA, 'fixture', FINGERPRINT)
        for state in ('failure', 'cancelled', 'skipped', None):
            responses = copy.deepcopy(self.responses)
            responses[2]['workflow_runs'][0]['conclusion'] = state
            with patch.object(release, 'github', side_effect=responses):
                with self.assertRaises(RuntimeError):
                    release.select(SHA, 'fixture', FINGERPRINT)
        with patch.object(release, 'github', side_effect=self.responses):
            with self.assertRaisesRegex(RuntimeError, 'Bootstrap refuses'):
                release.select(SHA, 'fixture', 'unknown')
        for value in ('main', 'a'*7, '../main', SHA+'\n', 'A'*40):
            with self.assertRaises(RuntimeError):
                release.revision(value)

    def test_fingerprint_tracks_added_changed_and_deleted_application_inputs(self):
        self.assertEqual(FINGERPRINT, release.fingerprint(TREE + [
            {'path': 'README.md', 'mode': '100644', 'sha': 'f'*40, 'type': 'blob'}]))
        for tree in ([{**TREE[0], 'sha': 'f'*40}],
                     TREE + [{**TREE[0], 'path': 'server/api/sessions.py'}]):
            self.assertNotEqual(FINGERPRINT, release.fingerprint(tree))
        with self.assertRaises(RuntimeError):
            release.fingerprint([])

    def test_host_lock_maintenance_and_failed_preflight_never_replace(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bootstrap.sha256').write_text(FINGERPRINT)
            with patch.object(update, 'ROOT', root), patch.object(update, 'STATE', root):
                with (root / 'update.lock').open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with self.assertRaisesRegex(RuntimeError, 'host lock'):
                        update.deploy({})
                (root / 'active').touch()
                with self.assertRaisesRegex(RuntimeError, 'Maintenance'):
                    update.deploy({})
                (root / 'active').unlink()
                with patch.object(update, 'select', side_effect=RuntimeError('CI failed')), \
                        patch.object(update, 'run') as command:
                    with self.assertRaisesRegex(RuntimeError, 'CI failed'):
                        update.deploy({'revision': SHA, 'token': 'fixture'})
                    command.assert_not_called()
                    self.assertFalse((root / 'active').exists())

    def test_failed_replacement_stays_closed_and_preserves_record(self):
        containers = [
            {'Name': '/knightsat-server-1', 'Image': 'old-server',
             'Mounts': [{'Name': 'knightsat_progress', 'Destination': '/data'}]},
            {'Name': '/knightsat-web-1', 'Image': 'old-web', 'Mounts': []},
        ]
        record = {'images': {c['Name']: c['Image'] for c in containers}}
        def command(*args, **kwargs):
            if 'up' in args:
                raise RuntimeError('fixture replacement failed')
            return ''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'bootstrap.sha256').write_text(FINGERPRINT)
            (root / 'current.json').write_text(json.dumps(record))
            (root / '.env').write_text('old configuration\n')
            image = {'Config': {'Labels': {'org.opencontainers.image.revision': SHA}}}
            with patch.object(update, 'ROOT', root), patch.object(update, 'STATE', root), \
                    patch.object(update, 'select', return_value=self.responses[-1]), \
                    patch.object(update, 'inspect', side_effect=[containers, [image], [image]]), \
                    patch.object(update, 'run', side_effect=command):
                with self.assertRaisesRegex(RuntimeError, 'replacement failed'):
                    update.deploy({'revision': SHA, 'token': 'fixture'})
            self.assertTrue((root / 'active').exists())
            self.assertEqual(json.loads((root / 'current.json').read_text()), record)
            self.assertEqual((root / '.env').read_text(), 'old configuration\n')
            self.assertNotIn('fixture', (root / 'pending.json').read_text())


if __name__ == '__main__':
    unittest.main()
