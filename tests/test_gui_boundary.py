"""Source-level boundary tripwires supplement executable GUI conformance."""

from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def shared_violations(source):
    """Shared application includes public vocabulary, never a concrete host."""
    result = []
    includes = re.findall(r'#\s*include\s*[<"]([^>"]+)', source)
    allowed_gui = {"gui/contract.hpp", "gui/layout.hpp", "gui/runtime.hpp"}
    for include in includes:
        if include.startswith("gui/") and include not in allowed_gui:
            result.append(include)
        if include.startswith(("FL/", "SDL", "windows.h", "backends/", "hosts/")):
            result.append(include)
    if re.search(r'\b(?:import\s+Rev|TerminalAdapter|FramebufferAdapter|WebAdapter)\b', source):
        result.append("concrete backend dependency")
    return result


class GuiBoundaryTests(unittest.TestCase):
    def test_shared_application_is_backend_independent(self):
        for path in (ROOT / "gui/shared").glob("*pp"):
            self.assertEqual([], shared_violations(path.read_text()), str(path))

    def test_tripwire_rejects_concrete_backends(self):
        for source in ('#include <FL/Fl.H>', '#include <gui/framebuffer.hpp>',
                       'import Rev.Widget;', 'gui::WebAdapter adapter;'):
            self.assertTrue(shared_violations(source), source)
        self.assertFalse(shared_violations('#include <gui/contract.hpp>\ngui::Adapter& adapter;'))

    def test_composition_hosts_do_not_name_feature_ids(self):
        for path in (ROOT / "gui/hosts").glob("*.cpp"):
            self.assertNotIn('"entries.', path.read_text(), str(path))

    def test_dependency_lock_is_complete_for_consumed_inputs(self):
        lock = json.loads((ROOT / "third_party/gui-boundary.lock.json").read_text())
        self.assertRegex(lock["revision"], r"^[0-9a-f]{40}$")
        for path in ("include/gui/contract.hpp", "include/gui/layout.hpp",
                     "include/gui/terminal.hpp", "include/gui/framebuffer.hpp",
                     "backends/terminal/main.cpp", "backends/fltk/adapter.hpp"):
            self.assertIn(path, lock["files"])
        for path, digest in lock["files"].items():
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("..", Path(path).parts)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual("NOASSERTION", lock["license"])


if __name__ == "__main__":
    unittest.main()
