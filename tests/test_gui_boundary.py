"""Source-level boundary tripwires supplement executable GUI conformance."""

from pathlib import Path
import importlib.util
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]


_spec = importlib.util.spec_from_file_location("gui_guard", ROOT / "gui/check_boundary.py")
_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_guard)
shared_violations = _guard.shared_violations


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
                     "backends/terminal/main.cpp", "backends/fltk/adapter.hpp",
                     "backends/rev/adapter.cpp", "backends/framebuffer/main_sdl.cpp",
                     "backends/web/renderer.mjs", "backends/web/host.py",
                     "cmake/PrepareRev.cmake", "third_party/rev/SHA256SUMS"):
            self.assertIn(path, lock["files"])
        for path, digest in lock["files"].items():
            self.assertFalse(Path(path).is_absolute())
            self.assertNotIn("..", Path(path).parts)
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual("NOASSERTION", lock["license"])


    def test_typed_host_contract_has_no_feature_dispatch(self):
        for path in (ROOT / "gui/host").glob("*.hpp"):
            self.assertNotIn('"entries.', path.read_text())
            self.assertNotIn("foundation::Store", path.read_text())
        cmake = (ROOT / "gui/CMakeLists.txt").read_text()
        self.assertNotIn("using Example", cmake)
        self.assertNotIn("string(REPLACE", cmake)
        for name in ("FLTK", "SDL", "REV", "WEB"):
            self.assertIn("FOUNDATION_GUI_" + name, cmake)

    def test_patch_application_is_exact_and_fail_closed(self):
        spec = importlib.util.spec_from_file_location("gui_patch", ROOT / "gui/patches/apply.py")
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        patch = "--- old\n+++ new\n@@ -1,2 +1,2 @@\n first\n-old\n+new\n"
        self.assertEqual("first\nnew\n", module.apply("first\nold\n", patch))
        for source in ("different\nold\n", "first\nchanged\n", "prefix\nfirst\nold\n"):
            with self.assertRaises(ValueError): module.apply(source, patch)
        with self.assertRaises(ValueError): module.apply("first\nold\n", patch.replace("-1,2", "-1,3"))

    def test_browser_transport_has_bounded_worker_and_cleanup(self):
        source = (ROOT / "gui/hosts/web_host.py").read_text()
        self.assertIn("queue.Queue(1)", source)
        self.assertIn("self.worker.join(timeout=2)", source)
        self.assertNotIn("select.select", source)


if __name__ == "__main__":
    unittest.main()
