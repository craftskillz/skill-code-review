import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/review-code/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


renderer, guard, verifier, preparer = (load(n) for n in ('render_report', 'guard_fix_command', 'verify_fixes', 'prepare_fix_branch'))


def agent(role, status='completed'):
    return {'id': role, 'label': role, 'requested_model': 'modele-test', 'observed_model': None,
            'status': status, 'summary': 'Résumé.'}


def finding(fid, outcome, **extra):
    base = {'id': fid, 'severity': 'P2', 'title': 'Titre', 'file': 'src/a.js', 'line': 3, 'trigger': 'Situation',
            'impact': 'Impact', 'evidence': 'Preuve', 'recommendation': 'Reco', 'reviewers': ['review-behavior'],
            'sensitive': False, 'outcome': outcome, 'challenge': {'verdict': 'confirmed', 'reason': 'Lu en a.js:3'}}
    return {**base, **extra}


FIX = {'commit': 'abc1234', 'test': 'test/a.test.js', 'summary': 'Résumé', 'red': 'not ok', 'green': 'ok', 'diff': '+x\n-y',
       'review': {'verdict': 'approved', 'reason': 'Conforme'}}
DECISION = {'reason': 'business_ambiguity', 'question': 'Quel arrondi ?', 'recommendation': 'Par ligne.',
            'options': [{'label': 'A', 'consequence': 'a'}, {'label': 'B', 'consequence': 'b'}]}


def report():
    return {'schema_version': 2, 'demo': True, 'title': 'T', 'repository': 'R', 'headline': 'H', 'status': 'completed',
            'scope': {'base': 'main', 'head': 'feat', 'base_sha': 'a' * 40, 'head_sha': 'b' * 40},
            'fix_branch': {'name': 'review-fixes/x', 'head_sha': 'c' * 40},
            'awareness': {'summary': 'S', 'changes': [{'area': 'A', 'before': 'B', 'after': 'C'}], 'watch': ['W']},
            'agents': [agent(r) for r in sorted(renderer.ROLES)],
            'findings': [finding('R-001', 'fixed', fix=copy.deepcopy(FIX)),
                         finding('R-002', 'human_decision', decision=copy.deepcopy(DECISION)),
                         finding('R-003', 'dismissed', challenge={'verdict': 'refuted', 'reason': 'Contrôle en amont'})],
            'checks': [{'label': 'Suite', 'kind': 'test', 'status': 'passed', 'detail': 'npm test'}], 'limitations': []}


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.data = report()

    def refused(self):
        with self.assertRaises(ValueError):
            renderer.validate(self.data)

    def test_untrusted_text_stays_text(self):
        self.data['findings'][1]['title'] = '<script>alert(1)</script> {{SCOPE}}'
        result = renderer.render(self.data)
        self.assertNotIn('<script>alert(1)</script>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('{{SCOPE}}', result)

    def test_report_shows_decisions_fixes_and_dismissals(self):
        result = renderer.render(self.data)
        for expected in ('Quel arrondi ?', 'not ok', 'Contrôle en amont', 'git merge --ff-only review-fixes/x'):
            self.assertIn(expected, result)

    def test_sensitive_area_cannot_be_fixed_automatically(self):
        self.data['findings'][0]['sensitive'] = True
        self.refused()

    def test_only_confirmed_finding_can_be_fixed(self):
        self.data['findings'][0]['challenge']['verdict'] = 'uncertain'
        self.refused()

    def test_fix_needs_an_approved_review_by_someone_else(self):
        self.data['findings'][0]['fix']['review']['verdict'] = 'rejected'
        self.refused()

    def test_fix_needs_observed_red_output(self):
        del self.data['findings'][0]['fix']['red']
        self.refused()

    def test_fix_needs_a_fixer_that_ran(self):
        next(a for a in self.data['agents'] if a['id'] == 'fix-finding').update(status='not_run', requested_model=None)
        self.data['limitations'] = ['Rôle absent.']
        self.refused()

    def test_only_refuted_finding_can_be_dismissed(self):
        self.data['findings'][2]['challenge']['verdict'] = 'confirmed'
        self.refused()

    def test_decision_offers_real_choice(self):
        self.data['findings'][1]['decision']['options'].pop()
        self.refused()

    def test_incomplete_reader_requires_partial(self):
        next(a for a in self.data['agents'] if a['id'] == 'review-tests')['status'] = 'failed'
        self.data['findings'] = []
        self.data['fix_branch'] = None
        self.refused()
        self.data['status'] = 'partial'
        self.refused()
        self.data['limitations'] = ['Analyse absente.']
        self.assertIn('Couverture partielle', renderer.render(self.data))

    def test_failed_role_cannot_own_a_finding(self):
        behavior = next(a for a in self.data['agents'] if a['id'] == 'review-behavior')
        behavior['status'] = 'failed'
        self.data.update(status='partial', limitations=['x'])
        self.refused()

    def test_model_change_must_be_explained(self):
        self.data['agents'][0]['observed_model'] = 'autre'
        self.refused()
        self.data['limitations'] = ['Modèle remplacé.']
        self.assertIn('Modèle différent de celui demandé', renderer.render(self.data))

    def test_inspection_is_not_a_passed_test(self):
        self.data['checks'][0].update(kind='inspection', status='passed')
        self.refused()

    def test_cli_refuses_overwrite_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as temp:
            source, output = Path(temp) / 'r.json', Path(temp) / 'r.html'
            source.write_text(json.dumps(self.data))
            command = [sys.executable, str(SCRIPTS / 'render_report.py'), str(source), '--output', str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
            source.write_text('{}')
            check = [sys.executable, str(SCRIPTS / 'render_report.py'), str(source), '--check']
            self.assertEqual(subprocess.run(check, capture_output=True).returncode, 1)

    def test_demo_report_is_valid(self):
        renderer.validate(json.loads((ROOT / 'demo/report.json').read_text(encoding='utf-8')))


class GuardTests(unittest.TestCase):
    PROJECT = '/projet'

    def decide(self, tool, **tool_input):
        return guard.decide({'tool_name': tool, 'tool_input': tool_input, 'cwd': self.PROJECT}, self.PROJECT)

    def test_allows_work_inside_worktree(self):
        self.assertIsNone(self.decide('Edit', file_path='/projet/.review-worktrees/a/src/x.js'))
        self.assertIsNone(self.decide('Bash', command='cd /projet/.review-worktrees/a && npm test'))
        self.assertIsNone(self.decide('Bash', command='cd /projet/.review-worktrees/a && git add -A && git commit -m x'))

    def test_refuses_writes_outside_worktree(self):
        self.assertTrue(self.decide('Write', file_path='/projet/src/x.js'))
        self.assertTrue(self.decide('Edit', file_path='/projet/.review-worktrees/../src/x.js'))

    def test_refuses_commands_that_move_or_publish(self):
        for command in ('git push origin main', 'git -C /projet merge feat', 'cd x && git reset --hard',
                        'git commit --no-verify -m x', 'gh pr merge 1', 'git switch main'):
            self.assertTrue(self.decide('Bash', command=command), command)

    def test_refuses_commit_outside_worktree(self):
        self.assertTrue(self.decide('Bash', command='git commit -m x'))

    def test_allows_commit_when_already_in_worktree(self):
        event = {'tool_name': 'Bash', 'tool_input': {'command': 'git add a && git commit -m x'},
                 'cwd': '/projet/.review-worktrees/a'}
        self.assertIsNone(guard.decide(event, self.PROJECT))


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.git('init', '-q', '-b', 'main')
        self.commit('a.txt', 'base')
        self.git('switch', '-qc', 'feat')
        self.commit('b.txt', 'change')
        self.info = preparer.prepare(self.repo, 'main', 'feat', 'revue-1')

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-C', str(cwd or self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid', *args],
                              check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, name, message, cwd=None):
        folder = Path(cwd or self.repo)
        (folder / name).write_text(message)
        self.git('add', '.', cwd=folder)
        self.git('commit', '-qm', message, cwd=folder)

    def data(self, commit):
        fixed = finding('R-001', 'fixed', file='b.txt', line=1, fix={**FIX, 'commit': commit})
        return {'scope': {'head': 'feat', 'head_sha': self.info['head_sha']},
                'fix_branch': {'name': self.info['fix_branch'], 'head_sha': self.git('rev-parse', self.info['fix_branch'])},
                'findings': [fixed]}

    def test_prepare_creates_branch_from_reviewed_commit_and_diff(self):
        self.assertEqual(self.git('rev-parse', 'HEAD', cwd=self.info['worktree']), self.info['head_sha'])
        self.assertIn('b.txt', Path(self.info['diff']).read_text())
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_prepare_refuses_dirty_tree_and_existing_id(self):
        with self.assertRaises(ValueError):
            preparer.prepare(self.repo, 'main', 'feat', 'revue-1')
        (self.repo / 'a.txt').write_text('modifié')
        with self.assertRaises(ValueError):
            preparer.prepare(self.repo, 'main', 'feat', 'revue-2')

    def trace_guard(self):
        (self.repo / '.review-worktrees/.guard.log').write_text('Bash\tallow\n')

    def test_verify_detects_fix_made_without_running_guard(self):
        self.commit('c.txt', 'fix\n\nReview-Finding: R-001', cwd=self.info['worktree'])
        sha = self.git('rev-parse', 'HEAD', cwd=self.info['worktree'])
        self.assertTrue(any('garde-fou' in e for e in verifier.verify(self.data(sha[:10]), self.repo)))

    def test_verify_accepts_matching_history(self):
        self.trace_guard()
        self.commit('c.txt', 'fix\n\nReview-Finding: R-001', cwd=self.info['worktree'])
        sha = self.git('rev-parse', 'HEAD', cwd=self.info['worktree'])
        self.assertEqual(verifier.verify(self.data(sha[:10]), self.repo), [])

    def test_verify_detects_invented_location(self):
        self.commit('c.txt', 'fix\n\nReview-Finding: R-001', cwd=self.info['worktree'])
        sha = self.git('rev-parse', 'HEAD', cwd=self.info['worktree'])
        data = self.data(sha[:10])
        data['findings'][0].update(file='b.txt', line=99)
        self.assertTrue(any('99' in e for e in verifier.verify(data, self.repo)))
        data['findings'][0].update(file='absent.txt', line=1)
        self.assertTrue(any('introuvable' in e for e in verifier.verify(data, self.repo)))

    def test_verify_detects_declared_fix_without_commit(self):
        self.assertTrue(verifier.verify(self.data('abc1234'), self.repo))

    def test_verify_detects_commit_without_trailer(self):
        self.commit('c.txt', 'fix', cwd=self.info['worktree'])
        sha = self.git('rev-parse', 'HEAD', cwd=self.info['worktree'])
        self.assertTrue(verifier.verify(self.data(sha[:10]), self.repo))

    def test_verify_detects_moved_reviewed_branch(self):
        self.commit('c.txt', 'fix\n\nReview-Finding: R-001', cwd=self.info['worktree'])
        sha = self.git('rev-parse', 'HEAD', cwd=self.info['worktree'])
        data = self.data(sha[:10])
        self.commit('d.txt', 'ajout direct')
        self.assertTrue(any('a bougé' in e for e in verifier.verify(data, self.repo)))


if __name__ == '__main__':
    unittest.main()
