import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/review-code'
ROLES = {'fix-finding', 'review-behavior', 'review-challenger', 'review-tests'}
sys.dont_write_bytecode = True


def load(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


preparer = load(SKILL / 'scripts/prepare_fix_branch.py')


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / 'projet'
        self.script = self.install_skill(self.project / '.claude/skills/review-code')
        self.agents = self.project / '.claude/agents'

    def install_skill(self, target):
        shutil.copytree(SKILL, target, ignore=shutil.ignore_patterns('__pycache__'))
        return target / 'scripts/install_agents.py'

    def run_script(self, script, *args, home=None):
        env = {**os.environ, 'HOME': str(home or self.temp.name), 'PYTHONDONTWRITEBYTECODE': '1'}
        # Lancé depuis un autre dossier : le résultat ne doit pas dépendre du répertoire courant.
        return subprocess.run([sys.executable, str(script), *args], cwd=self.temp.name, env=env,
                              capture_output=True, text=True)

    def installed(self):
        return {path.stem for path in self.agents.glob('*.md')}

    def test_installs_every_role_in_project_agents(self):
        result = self.run_script(self.script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.installed(), ROLES)

    def test_never_overwrites_an_existing_agent(self):
        self.agents.mkdir(parents=True)
        (self.agents / 'review-tests.md').write_text('version de l’équipe')
        result = self.run_script(self.script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.agents / 'review-tests.md').read_text(), 'version de l’équipe')
        self.assertIn('review-tests', result.stdout)
        self.assertEqual(self.installed(), ROLES)

    def test_tells_to_restart_when_it_creates_the_agents_directory(self):
        self.assertIn('Relancer', self.run_script(self.script).stdout)
        self.assertNotIn('Relancer', self.run_script(self.script).stdout)

    def test_check_fails_and_writes_nothing_when_no_agent_is_installed(self):
        result = self.run_script(self.script, '--check')
        self.assertEqual(result.returncode, 1)
        self.assertIn('install_agents.py', result.stderr)
        self.assertFalse(self.agents.exists())

    def test_check_accepts_a_missing_role_for_a_partial_review(self):
        self.run_script(self.script)
        (self.agents / 'review-tests.md').unlink()
        result = self.run_script(self.script, '--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('review-tests', result.stdout)

    def test_refuses_a_global_install(self):
        home = Path(self.temp.name) / 'home'
        script = self.install_skill(home / '.claude/skills/review-code')
        result = self.run_script(script, home=home)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((home / '.claude/agents').exists())

    def test_refuses_to_run_outside_an_installed_skill(self):
        result = self.run_script(SKILL / 'scripts/install_agents.py')
        self.assertEqual(result.returncode, 1)
        self.assertFalse((ROOT.parent / '.claude/agents/review-tests.md').exists())

    def test_accepts_a_symlinked_skill_seen_through_its_real_location(self):
        project = Path(self.temp.name) / 'lien'
        script = self.install_skill(project / '.agents/skills/review-code')
        (project / '.claude/skills').mkdir(parents=True)
        (project / '.claude/skills/review-code').symlink_to(project / '.agents/skills/review-code')
        result = self.run_script(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((project / '.claude/agents/fix-finding.md').exists())


class PrepareAfterInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git('init', '-q', '-b', 'main')
        self.commit('a.txt', 'base')
        self.git('switch', '-qc', 'feat')
        self.commit('b.txt', 'change')

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid', *args],
                       check=True, capture_output=True)

    def commit(self, name, text):
        (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / name).write_text(text)
        self.git('add', '.')
        self.git('commit', '-qm', text)

    def untracked(self, *names):
        for name in names:
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x')

    def test_untracked_install_files_do_not_block_the_review(self):
        self.untracked('.claude/skills/review-code/SKILL.md', '.claude/agents/fix-finding.md',
                       '.agents/skills/review-code/SKILL.md', 'skills-lock.json')
        self.assertEqual(preparer.prepare(self.repo, 'main', 'feat', 'revue-1')['fix_branch'], 'review-fixes/revue-1')

    def test_install_files_are_ignored_when_claude_folder_is_partly_tracked(self):
        self.commit('.claude/settings.json', 'réglages')
        self.untracked('.claude/skills/review-code/SKILL.md')
        self.assertEqual(preparer.prepare(self.repo, 'main', 'feat', 'revue-1')['fix_branch'], 'review-fixes/revue-1')

    def test_other_untracked_file_still_blocks(self):
        self.untracked('.claude/agents/fix-finding.md', 'notes.txt')
        with self.assertRaisesRegex(ValueError, 'notes.txt'):
            preparer.prepare(self.repo, 'main', 'feat', 'revue-1')

    def test_modified_tracked_file_under_claude_still_blocks(self):
        self.commit('.claude/settings.json', 'réglages')
        (self.repo / '.claude/settings.json').write_text('modifié')
        with self.assertRaisesRegex(ValueError, 'settings.json'):
            preparer.prepare(self.repo, 'main', 'feat', 'revue-1')


class FixtureTests(unittest.TestCase):
    def build(self, *args):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        target = Path(temp.name) / 'atelier'
        subprocess.run([sys.executable, str(ROOT / 'evals/build_fixture.py'), str(target), *args],
                       check=True, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        return {path.stem for path in (target / '.claude/agents').glob('*.md')}

    def test_fixture_installs_every_role(self):
        self.assertEqual(self.build(), ROLES)

    def test_fixture_can_remove_a_role(self):
        self.assertEqual(self.build('--without-agent', 'review-tests'), ROLES - {'review-tests'})


if __name__ == '__main__':
    unittest.main()
