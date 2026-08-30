import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'todo_app.py'))


def run_cmd(args, cwd):
    """Run the todo_app script with given args list in cwd, return CompletedProcess."""
    result = subprocess.run([sys.executable, SCRIPT] + args,
                            cwd=cwd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True)
    return result


class TestTodoApp(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for each test to isolate todos.json
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def test_add_task(self):
        res = run_cmd(['add', 'Buy', 'milk'], cwd=self.tmpdir.name)
        self.assertEqual(res.returncode, 0, msg=res.stderr)
        self.assertIn('Added todo #1.', res.stdout.strip())
        # Verify file content
        json_path = os.path.join(self.tmpdir.name, 'todos.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], 1)
        self.assertEqual(data[0]['task'], 'Buy milk')
        self.assertFalse(data[0]['done'])

    def test_list_tasks(self):
        # Add two tasks
        run_cmd(['add', 'Task', 'one'], cwd=self.tmpdir.name)
        run_cmd(['add', 'Task', 'two'], cwd=self.tmpdir.name)
        res = run_cmd(['list'], cwd=self.tmpdir.name)
        self.assertEqual(res.returncode, 0)
        lines = [ln for ln in res.stdout.splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)
        self.assertTrue(any('1. [ ] Task one' in line for line in lines))
        self.assertTrue(any('2. [ ] Task two' in line for line in lines))

    def test_done_task(self):
        run_cmd(['add', 'Finish', 'report'], cwd=self.tmpdir.name)
        res_done = run_cmd(['done', '1'], cwd=self.tmpdir.name)
        self.assertEqual(res_done.returncode, 0)
        self.assertIn('Marked todo #1 as done.', res_done.stdout)
        # Verify status in list output
        res_list = run_cmd(['list'], cwd=self.tmpdir.name)
        self.assertIn('1. [x] Finish report', res_list.stdout)

    def test_done_invalid_id(self):
        # No todos yet, attempt to mark non-existing ID
        res = run_cmd(['done', '42'], cwd=self.tmpdir.name)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn('Todo with ID 42 not found.', res.stderr)

    def test_done_non_integer_id(self):
        run_cmd(['add', 'Sample'], cwd=self.tmpdir.name)
        res = run_cmd(['done', 'abc'], cwd=self.tmpdir.name)
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("Invalid ID 'abc'", res.stderr)

if __name__ == '__main__':
    unittest.main()
