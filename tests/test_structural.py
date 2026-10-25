"""Check advisory structural review through the canonical comparator CLI."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_compare import metric_file


COMPARATOR = Path(__file__).resolve().parents[1] / 'scripts' / 'compare.py'


def graph(kind: str, projection: str, connected: bool = False,
          cyclic: bool = False) -> dict[str, object]:
    """Build exact indexed reachability for two eligible internal units."""
    numerator = 2 + int(connected) + int(cyclic)
    return {
        'granularity': kind, 'projection': projection, 'units': [f'{kind}:a', f'{kind}:b'],
        'cycles': [{'members': [f'{kind}:a', f'{kind}:b']}] if cyclic else [],
        'pc': {'value': numerator / 4, 'numerator': numerator, 'denominator': 4},
        'impacts': [
            {'unit': 0, 'dependencies': [1] if connected else [],
             'dependents': [1] if cyclic else [],
             'predecessors': [[0, 0], [1, 0]] if connected else [[0, 0]]},
            {'unit': 1, 'dependencies': [0] if cyclic else [],
             'dependents': [0] if connected else [],
             'predecessors': [[0, 1], [1, 1]] if cyclic else [[1, 1]]},
        ],
    }


def state(connected: bool = False, cyclic: bool = False) -> dict[str, object]:
    """Build all four structural projections with explicit coverage containers."""
    return {'scope': 'repo', 'coverage': [], 'effective': [], 'relationships': [],
            'graphs': [graph(kind, projection, connected, cyclic)
                       for kind in ('module', 'type') for projection in ('contract', 'full')]}


class StructuralCliTests(unittest.TestCase):
    """Keep all structural outcomes separate from required ordinary metrics."""

    def setUp(self) -> None:
        """Create independent before and after report roots."""
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        self.before_root = self.workspace / 'before'
        self.after_root = self.workspace / 'after'

    def report(self, name: str, score: float = 50.0) -> Path:
        """Write a complete ordinary report; use its name as source identity."""
        root = self.before_root if name == 'before' else self.after_root
        path = self.workspace / f'{name}.json'
        path.write_text(json.dumps({'files': [metric_file(root / 'sample.rs', name, score)]}))
        return path

    def attach(self, path: Path, structure: object) -> None:
        """Write a structural payload without changing required ordinary metrics."""
        report = json.loads(path.read_text())
        report['structure'] = structure
        path.write_text(json.dumps(report))

    def compare(self, before: Path, after: Path, *options: str) -> subprocess.CompletedProcess[str]:
        """Run the canonical comparator with explicit roots and optional review flags."""
        return subprocess.run([sys.executable, str(COMPARATOR), str(before), str(after),
                               '--before-root', str(self.before_root),
                               '--after-root', str(self.after_root), *options],
                              capture_output=True, check=False, text=True)

    def test_structural_failures_never_change_green_or_red_mi_exit(self) -> None:
        """Keep MI exit 0 or 1 for missing, invalid, local, or lost structural data."""
        for score, expected_exit in ((50.0, 0), (9.999, 1)):
            for failure in ('missing', 'invalid', 'index', 'fraction', 'local', 'coverage'):
                with self.subTest(score=score, failure=failure):
                    before, after = self.report('before'), self.report('after', score)
                    old, new = state(True, True), state()
                    self.attach(before, old)
                    match failure:
                        case 'missing':
                            pass
                        case 'invalid':
                            self.attach(after, ['invalid'])
                        case 'index':
                            new['graphs'][0]['impacts'][0]['dependencies'] = [-1]
                            self.attach(after, new)
                        case 'fraction':
                            new['graphs'][0]['pc']['denominator'] = 9
                            self.attach(after, new)
                        case 'local':
                            new['scope'] = 'local'
                            self.attach(after, new)
                        case 'coverage':
                            old['coverage'] = [{'path': 'sample.rs', 'language': 'rust',
                                                'status': 'partial', 'limitations': []}]
                            new['coverage'] = [{'path': 'sample.rs', 'language': 'rust',
                                                'status': 'unavailable', 'limitations': ['parse_error']}]
                            self.attach(before, old)
                            self.attach(after, new)
                    result = self.compare(before, after, '--structure')
                    self.assertEqual(result.returncode, expected_exit, result.stderr)
                    summary = json.loads(result.stdout)
                    self.assertEqual(summary['gate_passed'], expected_exit == 0)
                    self.assertTrue(summary['structure']['review'])
                    self.assertIn(summary['structure']['status'], ('unavailable', 'partial'))
                    self.assertNotEqual(summary['structure']['reason'], '')
                    if failure == 'coverage':
                        self.assertEqual(summary['structure']['coverage_lost'], ['sample.rs'])
                        self.assertIsNone(summary['structure']['graphs'][0]['cycles_removed'])
                        self.assertIsNone(summary['structure']['graphs'][0]['reach_removed'])

    def test_missing_structure_flags_are_advisory_and_legacy_reports_still_pass(self) -> None:
        """Support both flag spellings without requiring a structural payload."""
        before, after = self.report('before'), self.report('after')
        legacy = self.compare(before, after)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertNotIn('structure', json.loads(legacy.stdout))
        for flag in ('--structure', '--require-structure'):
            with self.subTest(flag=flag):
                result = self.compare(before, after, flag)
                self.assertEqual(result.returncode, 0, result.stderr)
                review = json.loads(result.stdout)['structure']
                self.assertEqual((review['status'], review['reason']), ('unavailable', 'missing'))
                self.assertTrue(review['review'])

    def test_missing_required_metrics_still_returns_incomplete_exit(self) -> None:
        """Reject missing ordinary metrics even when structural review is requested."""
        before, after = self.report('before'), self.report('after')
        self.attach(before, state())
        document = json.loads(after.read_text())
        del document['files'][0]['maintainability_index']
        document['structure'] = ['invalid']
        after.write_text(json.dumps(document))
        result = self.compare(before, after, '--structure')
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('Incomplete metric comparison:', result.stderr)

    def test_valid_structural_change_is_review_only(self) -> None:
        """Report a new matched dependency while the ordinary MI result passes."""
        before, after = self.report('before'), self.report('after')
        self.attach(before, state())
        self.attach(after, state(True))
        result = self.compare(before, after, '--structure')
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(summary['structure']['status'], 'ok')
        self.assertTrue(summary['structure']['review'])
        self.assertEqual(summary['structure']['graphs'][0]['reach_added'], [['module:a', 'module:b']])

    def test_invalid_index_forms_are_advisory_without_a_review_flag(self) -> None:
        """Reject bad structural endpoints while preserving both MI outcomes."""
        for score, expected in ((50.0, 0), (9.999, 1)):
            for indices in ([-1], [2], [True], ['1'], [1, 1]):
                with self.subTest(score=score, indices=indices):
                    before, after = self.report('before'), self.report('after', score)
                    self.attach(before, state())
                    payload = state(True)
                    payload['graphs'][0]['impacts'][0]['dependencies'] = indices
                    self.attach(after, payload)
                    result = self.compare(before, after)
                    self.assertEqual(result.returncode, expected, result.stderr)
                    self.assertEqual(json.loads(result.stdout)['structure']['reason'], 'invalid')

    def test_lost_resolution_suppresses_removed_findings(self) -> None:
        """Keep unresolved and newly external support separate from improvement."""
        for status in ('unresolved', 'external'):
            with self.subTest(status=status):
                before, after = self.report('before'), self.report('after')
                old, new = state(True, True), state()
                edge = {'source': 'a', 'target': 'b', 'kind': 'type', 'resolution': 'resolved',
                        'evidence': [{'owner': 'a', 'detail': 'B'}]}
                old['relationships'] = [edge]
                new['relationships'] = [dict(edge, target='B', resolution=status)]
                self.attach(before, old)
                self.attach(after, new)
                result = self.compare(before, after, '--structure')
                self.assertEqual(result.returncode, 0, result.stderr)
                summary = json.loads(result.stdout)['structure']
                self.assertEqual(summary['coverage_lost'], ['a'])
                self.assertIsNone(summary['graphs'][0]['cycles_removed'])
                self.assertIsNone(summary['graphs'][0]['reach_removed'])


if __name__ == '__main__':
    unittest.main()
