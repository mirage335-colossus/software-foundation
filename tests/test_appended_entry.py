"""The supported payload entry point never discovers a native build toolchain."""
import argparse
import contextlib
import importlib.util
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import subprocess
from unittest.mock import Mock, patch
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import appended
import build


def rich_options(root, profile="web"):
    """Arguments only: this fixture never creates an eligible retained engine."""
    return ["build", "--core-provider", "cpp", "--kernel-maintenance", "--appended-profile", profile,
            "--gui-source", str(root / "gui-input"), "--gui-backends", "wasm", "--sdk", str(root / "sdk"),
            "--engine-group", str(root / "engine"),
            *[value for name, pin in (("recipe", "a"), ("manifest", "b"), ("proof", "c"), ("runtime", "d"))
              for value in ("--engine-" + name + "-sha256", pin * 64)]]


def inert_sdk(root):
    sdk = root / "sdk"
    sdk.mkdir()
    (root / "gui-input").mkdir()
    (root / "engine").mkdir()
    (sdk / "sdk.json").write_text(json.dumps({"recipe_id": "e" * 64, "target": {
        "system": "Emscripten", "processor": "wasm32", "triple": "wasm32-emscripten"}}))
    return hashlib.sha256((sdk / "sdk.json").read_bytes()).hexdigest()


def physical_metadata():
    """In-memory static template fixture; never eligible retained/runtime evidence."""
    import appended_engine_consumer as consumer
    profile = {"schema_version": 1, "kind": "foundation-copied-engine-physical-v1",
               "target": "browser-wasm32", "binding": consumer.PHYSICAL_BINDING,
               "pointer_bits": 32, "pthread": False, "shared_memory": False,
               "bridge_abi": consumer.BRIDGE_ABI, "capabilities": "467",
               "contract_sha256": hashlib.sha256((ROOT / "include/foundation/appended/engine_provider.h").read_bytes()).hexdigest(),
               "build_sha256": "a" * 64, "source_recipe_sha256": "b" * 64,
               **consumer.PHYSICAL_PROFILE_FACTS}
    return {"scope": consumer.SCOPE, "whole_group_verified": True, "production_eligible": True,
            "recipe_id": profile["source_recipe_sha256"], "provider_build_sha256": profile["build_sha256"],
            "engine_profile": profile, "command_catalog": {"sha256": profile["command_catalog_sha256"]}}


@contextlib.contextmanager
def forbid_native_payload_work():
    """A public payload route must not discover SDKs or launch build processes."""
    with contextlib.ExitStack() as stack:
        for name in ("execute", "run", "native_rust_identity", "host_programs", "job_limits", "sdk_identity"):
            stack.enter_context(patch.object(build, name,
                side_effect=AssertionError("payload route entered native tool selection: " + name)))
        for name in ("run", "check_call", "check_output", "Popen"):
            stack.enter_context(patch.object(subprocess, name,
                side_effect=AssertionError("payload route launched a subprocess: " + name)))
        yield


class EntryTests(unittest.TestCase):
    def test_explicit_engine_maintenance_dispatch_precedes_native_tools(self):
        for action in ("plan", "build"):
            with self.subTest(action=action):
                module = Mock()
                module.main.return_value = 0
                with patch.dict(sys.modules, {"appended_engine_maintenance": module}), \
                        patch.object(build, "execute") as execute, \
                        patch.object(build, "run") as run, \
                        patch.object(build, "native_rust_identity") as rust:
                    self.assertEqual(build.main(["engine-maintenance", action, "--input", "fixture"]), 0)
                module.main.assert_called_once_with([action, "--input", "fixture"])
                execute.assert_not_called()
                run.assert_not_called()
                rust.assert_not_called()

    def test_engine_integrity_dispatch_does_not_enter_native_tools(self):
        module = Mock()
        module.main.return_value = 0
        with patch.dict(sys.modules, {"appended_engine_sdk": module}), \
                patch.object(build, "execute") as execute, \
                patch.object(build, "run") as run, \
                patch.object(build, "native_rust_identity") as rust:
            self.assertEqual(build.main(["engine-sdk", "verify", "--root", "fixture"]), 0)
        module.main.assert_called_once_with(["verify", "--root", "fixture"])
        execute.assert_not_called()
        run.assert_not_called()
        rust.assert_not_called()

    def test_payload_routes_dispatch_without_native_execution(self):
        for action, operation in (("pack", "pack"), ("compose", "compose"),
                                  ("strip", "strip"), ("verify", "verify"),
                                  ("compile", "compile"), ("kernel-seal", "seal"),
                                  ("rich-browser-kernel", None),
                                  ("verify-composition", "verify-composition"),
                                  ("qualification", None), ("release-check", None),
                                  ("delivery", None)):
            with self.subTest(action=action):
                module = Mock()
                module.main.return_value = 0
                with patch.object(appended.importlib, "import_module", return_value=module), \
                        patch.object(build, "execute") as execute, \
                        patch.object(build, "run") as run, \
                        patch.object(build, "native_rust_identity") as rust:
                    self.assertEqual(build.main(["appended", action, "--input", "fixture"]), 0)
                module.main.assert_called_once_with(([] if operation is None else [operation]) + ["--input", "fixture"])
                execute.assert_not_called()
                run.assert_not_called()
                rust.assert_not_called()

    def test_document_browser_route_forwards_exact_options_to_its_separate_module(self):
        for options in (
                ["--document-profile", "pixel", "--profile", "web", "--output", "/inert/output with spaces",
                 "--assets", "/inert/assets", "--kernel-module-dir", "/inert/module directory",
                 "--notice", "foundation=/inert/license one", "--notice", "engine=/inert/license two"],
                ["--document-profile", "physical", "--profile", "both", "--output", "/inert/physical"],
                ["--verify", "--output", "/inert/retained carrier", "--descriptor-sha256", "f" * 64]):
            with self.subTest(options=options):
                module = Mock()
                module.main.return_value = 17
                original = list(options)
                with patch.object(appended.importlib, "import_module", return_value=module) as imported, \
                        forbid_native_payload_work():
                    self.assertEqual(build.main(["appended", "document-browser-kernel", *options]), 17)
                imported.assert_called_once_with("package_appended_engine_document_wasm")
                module.main.assert_called_once_with(original)
                self.assertEqual(options, original)

    def test_document_browser_public_route_requires_selection_and_every_pin_before_output(self):
        import package_appended_engine_document_wasm as producer
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "new carrier"
            arguments = ["--output", str(output), "--document-profile", "pixel", "--profile", "web",
                "--assets", str(root / "missing assets"), "--source-root", str(root / "missing source"),
                "--engine-group", str(root / "missing engine"), "--kernel-receipt", str(root / "missing receipt"),
                "--developer-unqualified", *[argument for name in
                    ("engine-recipe", "engine-manifest", "engine-proof", "engine-runtime", "kernel-receipt")
                    for argument in ("--" + name + "-sha256", "a" * 64)]]
            for omitted in ("--document-profile", "--engine-recipe-sha256", "--engine-manifest-sha256",
                            "--engine-proof-sha256", "--engine-runtime-sha256", "--kernel-receipt-sha256"):
                changed = list(arguments)
                index = changed.index(omitted)
                del changed[index:index + 2]
                with self.subTest(omitted=omitted), forbid_native_payload_work(), \
                        patch.object(producer, "package") as package, \
                        patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                    self.assertEqual(build.main(["appended", "document-browser-kernel", *changed]), 1)
                    self.assertIn("Document production requires explicit selection", errors.getvalue())
                    package.assert_not_called()
                    self.assertFalse(output.exists())
            self.assertEqual(list(root.iterdir()), [])

    def test_document_browser_public_verification_cannot_upgrade_retained_policy(self):
        import package_appended_engine_document_wasm as producer
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new carrier"
            for flags in (["--document-profile", "pixel"], ["--developer-unqualified"],
                          ["--engine-runtime-sha256", "a" * 64]):
                with self.subTest(flags=flags), forbid_native_payload_work(), \
                        patch.object(producer, "package") as package, patch.object(producer, "verify") as verify, \
                        patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                    self.assertEqual(build.main(["appended", "document-browser-kernel", "--verify",
                                                "--output", str(output), *flags]), 1)
                    self.assertIn("production flags cannot upgrade", errors.getvalue())
                    package.assert_not_called()
                    verify.assert_not_called()
                    self.assertFalse(output.exists())
            with forbid_native_payload_work(), patch.object(producer, "package") as package, \
                    patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                self.assertEqual(build.main(["appended", "document-browser-kernel", "--output", str(output),
                                            "--descriptor-sha256", "a" * 64]), 1)
                self.assertIn("applies only to verification", errors.getvalue())
                package.assert_not_called()
                self.assertFalse(output.exists())

    def test_document_and_legacy_carrier_routes_reject_each_others_profile_flags(self):
        import package_appended_engine_document_wasm as document
        import package_appended_engine_wasm as legacy
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new carrier"
            for action, flags in (("document-browser-kernel", ["--physical-input"]),
                                  ("rich-browser-kernel", ["--document-profile", "pixel"])):
                with self.subTest(action=action), forbid_native_payload_work(), \
                        patch.object(document, "main", wraps=document.main) as document_main, \
                        patch.object(legacy, "main", wraps=legacy.main) as legacy_main, \
                        patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                    with self.assertRaises(SystemExit) as stopped:
                        build.main(["appended", action, "--output", str(output), *flags])
                    self.assertEqual(stopped.exception.code, 2)
                    self.assertIn("unrecognized arguments", errors.getvalue())
                    self.assertEqual(document_main.call_count, int(action == "document-browser-kernel"))
                    self.assertEqual(legacy_main.call_count, int(action == "rich-browser-kernel"))
                    self.assertFalse(output.exists())

    def test_document_browser_route_help_is_public_and_does_not_select_build_tools(self):
        with forbid_native_payload_work(), patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            self.assertEqual(build.main(["appended", "--help"]), 0)
            self.assertIn("document-browser-kernel", "".join(output.getvalue().split()))
        with forbid_native_payload_work(), patch.object(sys, "stdout", new_callable=io.StringIO) as output:
            with self.assertRaises(SystemExit) as stopped:
                build.main(["appended", "document-browser-kernel", "--help"])
            self.assertEqual(stopped.exception.code, 0)
            self.assertIn("--document-profile {pixel,physical}", output.getvalue())
            self.assertNotIn("--engine-document-profile", output.getvalue())

    def test_project_inspection_does_not_discover_rust_or_configure(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(build, "ROOT", Path(temporary)), \
                patch.object(build, "execute") as execute, \
                patch.object(build, "native_rust_identity") as rust:
            self.assertEqual(build.main(["project", "inspect", "--json"]), 0)
            execute.assert_not_called()
            rust.assert_not_called()

    def test_kernel_profile_requires_explicit_maintenance_before_tools(self):
        with patch.object(build, "run") as run, patch.object(build, "native_rust_identity") as rust:
            with self.assertRaises(SystemExit):
                build.main(["build", "--appended-profile", "binary"])
            run.assert_not_called()
            rust.assert_not_called()

    def test_active_project_never_silently_builds_the_ordinary_application(self):
        import appended_project
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src-bin-appended").mkdir()
            appended_project.set_mode(root, "binary", create=True)
            with patch.object(build, "ROOT", root), patch.object(build, "run") as run:
                for arguments in (["build", "--core-provider", "cpp"],
                                  ["build", "--core-provider", "cpp", "--kernel-maintenance"]):
                    with self.subTest(arguments=arguments), self.assertRaises(SystemExit):
                        build.main(arguments)
                run.assert_not_called()

    def test_missing_project_configuration_keeps_ordinary_build_admission(self):
        class ReachedJobSelection(Exception):
            pass
        with tempfile.TemporaryDirectory() as temporary, \
                patch.object(build, "ROOT", Path(temporary)), \
                patch.object(build, "job_limits", side_effect=ReachedJobSelection) as jobs, \
                patch.object(build, "run") as run:
            with self.assertRaises(ReachedJobSelection):
                build.main(["build", "dev", "--core-provider", "cpp"])
            jobs.assert_called_once()
            run.assert_not_called()

    def test_dangling_project_configuration_stops_before_native_selection(self):
        import appended_project
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            try:
                (root / "foundation-project.json").symlink_to("missing-project.json")
            except (NotImplementedError, OSError) as error:
                self.skipTest("filesystem cannot create a symbolic link: " + str(error))
            with patch.object(build, "ROOT", root), patch.object(build, "job_limits") as jobs, \
                    patch.object(build, "host_programs") as programs, \
                    patch.object(build, "run") as run, patch.object(build, "native_rust_identity") as rust:
                with self.assertRaisesRegex(appended_project.ProjectError, "regular file without symbolic links"):
                    build.main(["build", "dev", "--core-provider", "cpp"])
                for sentinel in (jobs, programs, run, rust):
                    sentinel.assert_not_called()

    def test_rich_web_maintenance_stops_before_toolchain_discovery(self):
        import appended_project
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src-web-appended").mkdir()
            (root / "src-web-appended/index.html").write_text("<!doctype html><title>App</title>")
            appended_project.set_mode(root, "web", create=True)
            with patch.object(build, "ROOT", root), patch.object(build, "run") as run:
                with self.assertRaises(SystemExit):
                    build.main(["build", "--core-provider", "cpp", "--kernel-maintenance"])
                run.assert_not_called()

    def test_retained_superset_profiles_cannot_enter_smaller_kernel_builds(self):
        import appended_project
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src-bin-appended").mkdir()
            for mode, profile in (("binary", "both"), ("neither", "both"),
                                  ("neither", "web"), ("neither", "binary")):
                appended_project.set_mode(root, mode, create=True, profile=profile)
                for flags in ([], ["--kernel-maintenance"]):
                    with self.subTest(mode=mode, profile=profile, flags=flags), \
                            patch.object(build, "ROOT", root), \
                            patch.object(build, "job_limits") as jobs, \
                            patch.object(build, "run") as run, \
                            patch.object(build, "native_rust_identity") as rust, \
                            patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                        with self.assertRaises(SystemExit):
                            build.main(["build", "--core-provider", "cpp", *flags])
                        self.assertIn("kernel", errors.getvalue())
                        jobs.assert_not_called()
                        run.assert_not_called()
                        rust.assert_not_called()
                if profile in ("web", "both"):
                    with self.subTest(mode=mode, profile=profile, requested="binary"), \
                            patch.object(build, "ROOT", root), patch.object(build, "run") as run, \
                            patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                        with self.assertRaises(SystemExit):
                            build.main(["build", "--core-provider", "cpp", "--kernel-maintenance",
                                        "--appended-profile", "binary"])
                        self.assertIn("requires --appended-profile " + profile, errors.getvalue())
                        run.assert_not_called()

    def test_explicit_minimal_profile_rejects_binary_maintenance(self):
        import appended_project
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            appended_project.set_mode(root, "neither", create=True, profile="minimal")
            with patch.object(build, "ROOT", root), patch.object(build, "job_limits") as jobs, \
                    patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                with self.assertRaises(SystemExit):
                    build.main(["build", "--core-provider", "cpp", "--kernel-maintenance",
                                "--appended-profile", "binary"])
                self.assertIn("does not match the explicitly selected kernel.profile", errors.getvalue())
                jobs.assert_not_called()

    def test_explicit_binary_and_auto_minimal_keep_authorized_maintenance(self):
        import appended_project
        class ReachedJobSelection(Exception):
            pass
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for profile in ("binary", "auto"):
                appended_project.set_mode(root, "neither", create=True, profile=profile)
                with self.subTest(profile=profile), patch.object(build, "ROOT", root), \
                        patch.object(build, "job_limits", side_effect=ReachedJobSelection) as jobs, \
                        patch.object(build, "run") as run:
                    with self.assertRaises(ReachedJobSelection):
                        build.main(["build", "--core-provider", "cpp", "--kernel-maintenance",
                                    "--appended-profile", "binary"])
                    jobs.assert_called_once()
                    run.assert_not_called()

    def test_direct_cmake_admission_respects_selected_profile_without_compilers(self):
        import appended_project
        cmake = (ROOT / "CMakeLists.txt").read_text()
        admission = cmake.split('# Appended retained-input admission.\n', 1)[1].split(
            '# Never trust a caller-supplied -D admission boolean.', 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools").mkdir()
            (root / "tools/appended_project.py").write_bytes((ROOT / "tools/appended_project.py").read_bytes())
            (root / "src-bin-appended").mkdir()
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Admission LANGUAGES NONE)\n'
                'set(Python3_EXECUTABLE "' + sys.executable.replace('\\', '/') + '")\n' + admission)
            for ordinal, (mode, profile, requested, accepted) in enumerate((
                    ("binary", "both", "binary", False), ("neither", "both", "binary", False),
                    ("neither", "binary", "none", False), ("neither", "minimal", "binary", False),
                    ("neither", "binary", "binary", True), ("neither", "auto", "binary", True),
                    ("neither", "auto", "none", True))):
                appended_project.set_mode(root, mode, create=True, profile=profile)
                result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / ("build" + str(ordinal))),
                    "-DFOUNDATION_APPENDED_PROFILE=" + requested], capture_output=True, text=True, timeout=15)
                with self.subTest(mode=mode, profile=profile, requested=requested):
                    self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)
            (root / "foundation-project.json").unlink()
            result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "missing-config"),
                "-DFOUNDATION_APPENDED_PROFILE=none"], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            try:
                (root / "foundation-project.json").symlink_to("missing-project.json")
            except (NotImplementedError, OSError) as error:
                self.skipTest("filesystem cannot create a symbolic link: " + str(error))
            result = subprocess.run(["cmake", "-S", str(root), "-B", str(root / "dangling-config"),
                "-DFOUNDATION_APPENDED_PROFILE=none"], capture_output=True, text=True, timeout=15)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("regular file without symbolic links", result.stdout + result.stderr)

    def test_rich_profiles_require_every_independent_pin_before_tools(self):
        for profile in ("web", "both"):
            for omitted in ("--engine-group", "--engine-recipe-sha256", "--engine-manifest-sha256",
                            "--engine-proof-sha256", "--engine-runtime-sha256"):
                options = rich_options(Path("/nonexistent"), profile)
                index = options.index(omitted)
                del options[index:index + 2]
                with self.subTest(profile=profile, omitted=omitted), \
                        patch.object(build, "host_programs") as programs, \
                        patch.object(build, "job_limits") as jobs, patch.object(build, "run") as run, \
                        patch.object(build, "sdk_identity") as sdk, \
                        patch.object(build.subprocess, "check_output") as subprocess_output, \
                        patch.object(build, "native_rust_identity") as rust, \
                        patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                    with self.assertRaises(SystemExit):
                        build.main(options)
                    self.assertIn("all four independent", errors.getvalue())
                    for sentinel in (programs, jobs, run, sdk, subprocess_output, rust):
                        sentinel.assert_not_called()

    def test_engine_flags_and_bad_pins_cannot_enter_other_profiles(self):
        for arguments in (["build", "--engine-group", "/nonexistent"],
                          ["build", "--kernel-maintenance", "--appended-profile", "binary",
                           "--engine-proof-sha256", "c" * 64],
                          [*rich_options(Path("/nonexistent"))[:-1], "D" * 64]):
            with self.subTest(arguments=arguments), patch.object(build, "host_programs") as programs, \
                    patch.object(build, "run") as run, patch.object(build, "sdk_identity") as sdk, \
                    patch.object(build, "job_limits") as jobs, \
                    patch.object(sys, "stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main(arguments)
                for sentinel in (programs, run, sdk, jobs):
                    sentinel.assert_not_called()

    def test_physical_flag_requires_explicit_rich_maintenance_before_tools(self):
        for arguments in (["build"], ["build", "--kernel-maintenance"],
                          ["build", "--kernel-maintenance", "--appended-profile", "binary"],
                          ["build", "--appended-profile", "web"]):
            with self.subTest(arguments=arguments), patch.object(build, "host_programs") as programs, \
                    patch.object(build, "job_limits") as jobs, patch.object(build, "sdk_identity") as sdk, \
                    patch.object(build, "run") as run, \
                    patch.object(build, "native_rust_identity") as rust, \
                    patch.object(sys, "stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit):
                    build.main([*arguments, "--engine-physical-input"])
                for sentinel in (programs, jobs, sdk, run, rust):
                    sentinel.assert_not_called()

    def test_rich_native_target_is_rejected_before_consumer_or_programs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inert_sdk(root)
            (root / "sdk/sdk.json").write_text(json.dumps({"target": {
                "system": "Linux", "processor": "x86_64", "triple": "x86_64-linux-gnu"}}))
            sdk_sha256 = hashlib.sha256((root / "sdk/sdk.json").read_bytes()).hexdigest()
            with patch.object(build, "ROOT", root), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(build, "require_clean"), \
                    patch.object(build, "engine_consumer_identity") as consumer, \
                    patch.object(build, "host_programs") as programs, patch.object(build, "run") as run, \
                    patch.object(build, "job_limits") as jobs, \
                    patch.object(sys, "stderr", new_callable=io.StringIO) as errors:
                with self.assertRaises(SystemExit):
                    build.main(rich_options(root))
                self.assertIn("Emscripten wasm32", errors.getvalue())
                for sentinel in (consumer, programs, run, jobs):
                    sentinel.assert_not_called()

    def test_ineligible_retained_engine_stops_before_all_build_tools(self):
        # The actual consumer sees an empty group; no eligible artifact or runtime
        # evidence is manufactured by this entry-point fixture.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            with patch.object(build, "ROOT", root), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(build, "require_clean"), patch.object(build, "host_programs") as programs, \
                    patch.object(build, "job_limits") as jobs, patch.object(build, "run") as run, \
                    patch.object(build.subprocess, "check_output") as subprocess_output, \
                    patch.object(build.subprocess, "run") as subprocess_run, \
                    patch.object(build, "native_rust_identity") as rust:
                with self.assertRaisesRegex(ValueError, "engine group"):
                    build.main(rich_options(root))
                for sentinel in (programs, jobs, run, subprocess_output, subprocess_run, rust):
                    sentinel.assert_not_called()
                self.assertFalse((root / "build").exists())

    def test_consumer_admission_receives_exact_pins_target_and_sdk(self):
        import appended_engine_consumer
        inspection = Mock()
        inspection.as_dict.return_value = {"group_files": {"three-file-inventory": "e" * 64}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            class ReachedJobSelection(Exception):
                pass
            with patch.object(build, "ROOT", root), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(build, "require_clean"), \
                    patch.object(appended_engine_consumer, "verify_kernel_consumer", return_value=inspection) as verify, \
                    patch.object(build, "job_limits", side_effect=ReachedJobSelection), \
                    patch.object(build, "host_programs") as programs, patch.object(build, "run") as run:
                with self.assertRaises(ReachedJobSelection):
                    build.main(rich_options(root))
            verify.assert_called_once_with(root / "engine", expected_recipe="a" * 64,
                expected_manifest="b" * 64, expected_proof="c" * 64, expected_runtime="d" * 64,
                kernel_target={"system": "Emscripten", "processor": "wasm32",
                               "triple": "wasm32-emscripten", "pointer_bits": 32}, paired_sdk=sdk_sha256)
            programs.assert_not_called()
            run.assert_not_called()

    def test_physical_consumer_binding_and_identity_are_explicit_before_tools(self):
        import appended_engine_consumer
        inspection = Mock()
        inspection.as_dict.return_value = physical_metadata()
        class ReachedJobSelection(Exception):
            pass
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            identities = []
            original = build.engine_consumer_identity
            def capture(*arguments):
                identity = original(*arguments)
                identities.append(identity)
                return identity
            with patch.object(build, "ROOT", root), patch.object(build, "require_clean"), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(appended_engine_consumer, "verify_kernel_consumer", return_value=inspection) as verify, \
                    patch.object(build, "engine_consumer_identity", side_effect=capture), \
                    patch.object(build, "job_limits", side_effect=ReachedJobSelection), \
                    patch.object(build, "host_programs") as programs, patch.object(build, "run") as run:
                with self.assertRaises(ReachedJobSelection):
                    build.main([*rich_options(root), "--engine-physical-input"])
            self.assertEqual(verify.call_args.kwargs["required_binding"], appended_engine_consumer.PHYSICAL_BINDING)
            self.assertIs(identities[0]["physical_input"], True)
            self.assertEqual(identities[0]["consumer"], physical_metadata())
            programs.assert_not_called()
            run.assert_not_called()

    def test_old_copied_binding_cannot_be_opted_into_physical_before_tools(self):
        import appended_engine_consumer
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            with patch.object(build, "ROOT", root), patch.object(build, "require_clean"), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(appended_engine_consumer, "verify_kernel_consumer",
                                 side_effect=ValueError("wrong selected physical binding")) as verify, \
                    patch.object(build, "job_limits") as jobs, patch.object(build, "host_programs") as programs, \
                    patch.object(build, "run") as run:
                with self.assertRaisesRegex(ValueError, "physical binding"):
                    build.main([*rich_options(root), "--engine-physical-input"])
            self.assertEqual(verify.call_args.kwargs["required_binding"], appended_engine_consumer.PHYSICAL_BINDING)
            for sentinel in (jobs, programs, run):
                sentinel.assert_not_called()

    def test_changed_engine_identity_requires_fresh_tree_before_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            tree = root / "owned-build"
            tree.mkdir()
            (tree / "wrapper-identity.json").write_text(json.dumps({"appended_profile": "web",
                                                                  "appended_engine": {"old": "identity"}}))
            with patch.object(build, "ROOT", root), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(build, "require_clean"), \
                    patch.object(build, "engine_consumer_identity", return_value={"mock": "new-identity"}), \
                    patch.object(build, "job_limits") as jobs, patch.object(build, "host_programs") as programs, \
                    patch.object(build, "run") as run:
                with self.assertRaisesRegex(ValueError, "retained engine identity/profile changed"):
                    build.main([*rich_options(root), "--build-dir", str(tree)])
                for sentinel in (jobs, programs, run):
                    sentinel.assert_not_called()

    def test_changing_physical_choice_requires_fresh_wrapper_tree_before_tools(self):
        import appended_engine_consumer as consumer
        inspection = Mock()
        inspection.as_dict.return_value = {"group_files": {"mock-inventory": "e" * 64}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            tree = root / "owned-build"
            tree.mkdir()
            target = {"system": "Emscripten", "processor": "wasm32",
                      "triple": "wasm32-emscripten", "pointer_bits": 32}
            with patch.object(consumer, "verify_kernel_consumer", return_value=inspection):
                identities = {}
                for physical in (False, True):
                    arguments = argparse.Namespace(engine_group=root / "engine", engine_physical_input=physical,
                        **{"engine_" + name + "_sha256": pin * 64 for name, pin in
                           (("recipe", "a"), ("manifest", "b"), ("proof", "c"), ("runtime", "d"))})
                    identities[physical] = build.engine_consumer_identity(arguments, sdk_sha256, target)
            self.assertNotIn("physical_input", identities[False])
            self.assertIs(identities[True]["physical_input"], True)
            for old_choice, new_choice in ((False, True), (True, False)):
                (tree / "wrapper-identity.json").write_text(json.dumps({"appended_profile": "web",
                                                                      "appended_engine": identities[old_choice]}))
                options = [*rich_options(root), "--build-dir", str(tree)]
                if new_choice:
                    options.append("--engine-physical-input")
                with self.subTest(old=old_choice, new=new_choice), patch.object(build, "ROOT", root), \
                        patch.object(build, "require_clean"), patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                        patch.object(build, "engine_consumer_identity", return_value=identities[new_choice]), \
                        patch.object(build, "job_limits") as jobs, patch.object(build, "host_programs") as programs, \
                        patch.object(build, "run") as run:
                    with self.assertRaisesRegex(ValueError, "retained engine identity/profile changed"):
                        build.main(options)
                    for sentinel in (jobs, programs, run):
                        sentinel.assert_not_called()

    def test_complete_group_snapshot_is_rechecked_without_asset_execution(self):
        import appended_engine_sdk
        identity = {"root": "/retained/engine", "pins": {"recipe": "a" * 64},
                    "consumer": {"group_files": {"binary": "b" * 64, "sources": "c" * 64,
                                                   "checksums": "d" * 64}}}
        with patch.object(appended_engine_sdk, "group_snapshot",
                          return_value=dict(identity["consumer"]["group_files"])) as snapshot:
            build.recheck_engine_input(identity)
            snapshot.assert_called_once_with(Path("/retained/engine"), "a" * 64)
            snapshot.return_value["sources"] = "e" * 64
            with self.assertRaisesRegex(ValueError, "retained engine group changed"):
                build.recheck_engine_input(identity)

    def test_direct_rich_cmake_revalidates_pins_without_compiler_execution(self):
        # A LANGUAGES NONE fixture runs only the actual admission scripts. Its
        # tiny ordinary SDK is parser input, and its empty engine is ineligible.
        # No toolchain is configured and no retained tool may be executed.
        import sdk_environment
        cmake = (ROOT / "CMakeLists.txt").read_text()
        options = cmake.split("# Appended profile options.\n", 1)[1].split(
            "# End appended profile options.", 1)[0]
        admission = cmake.split("# Appended retained-input admission.\n", 1)[1].split(
            "# End appended retained-input admission.", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inert_sdk(root)
            tools = root / "tools"
            tools.mkdir()
            for helper in ("sdk_verify.py", "sdk_manifest.py", "sdk_environment.py", "dependency_archive.py",
                           "appended_engine_consumer.py", "appended_engine_manifest.py", "appended_engine_sdk.py",
                           "appended_engine_input_profile.py"):
                (tools / helper).write_bytes((ROOT / "tools" / helper).read_bytes())
            compiler = root / "sdk/compiler-sentinel"
            sentinel = root / "forbidden-tool-was-run"
            compiler.write_text("#!/bin/sh\n: > '" + str(sentinel) + "'\nexit 91\n")
            compiler.chmod(0o755)
            (root / "sdk/sysroot").mkdir()
            (root / "sdk/sdk.json").write_text(json.dumps({
                "schema_version": 1, "recipe_id": "e" * 64,
                "target": {"system": "Emscripten", "processor": "wasm32", "triple": "wasm32-emscripten",
                           "sysroot": "sysroot", "cxx_compiler": "compiler-sentinel"},
                "files": {"compiler-sentinel": hashlib.sha256(compiler.read_bytes()).hexdigest()}}))
            fixture_toolchain = root / "cmake/toolchains/sdk.cmake"
            fixture_toolchain.parent.mkdir(parents=True)
            fixture_toolchain.write_bytes((ROOT / "cmake/toolchains/sdk.cmake").read_bytes())
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Admission LANGUAGES NONE)\n'
                'set(Python3_EXECUTABLE "' + sys.executable.replace('\\', '/') + '")\n'
                'set(CMAKE_SYSTEM_NAME Emscripten)\nset(CMAKE_SIZEOF_VOID_P 4)\n'
                'set(CMAKE_TOOLCHAIN_FILE "' + fixture_toolchain.as_posix() + '")\n'
                'set(FOUNDATION_BUILD_GUI ON)\nset(FOUNDATION_GUI_SOURCE "' + (root / "gui-input").as_posix() + '")\n'
                'set(FOUNDATION_SDK_ROOT "' + (root / "sdk").as_posix() + '")\n' + options + admission +
                '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/graph-entered" "unexpected")\n')
            environment = dict(os.environ)
            for name in sdk_environment.HOST_OVERRIDES:
                environment.pop(name, None)
            complete = ["-DFOUNDATION_APPENDED_PROFILE=web", "-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=ON",
                        "-DFOUNDATION_APPENDED_ENGINE_GROUP=" + str(root / "engine"),
                        "-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON",
                        "-DCMAKE_CXX_COMPILER=" + str(compiler),
                        *["-DFOUNDATION_APPENDED_ENGINE_" + name.upper() + "_SHA256=" + pin * 64
                          for name, pin in (("recipe", "a"), ("manifest", "b"), ("proof", "c"), ("runtime", "d"))]]
            for ordinal, (physical, omitted) in enumerate((physical, omitted)
                    for physical in (False, True)
                    for omitted in (None, "RUNTIME_SHA256", "PROOF_SHA256", "MANIFEST_SHA256", "RECIPE_SHA256")):
                selected = [flag for flag in complete if omitted is None or omitted not in flag]
                if physical:
                    selected.append("-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=ON")
                tree = root / ("cmake-" + str(ordinal))
                result = subprocess.run(["cmake", "-S", str(root), "-B", str(tree), *selected],
                                        capture_output=True, text=True, timeout=15, env=environment)
                with self.subTest(physical=physical, omitted=omitted):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    if omitted is None:
                        self.assertIn("engine group", result.stdout + result.stderr)
                        self.assertEqual(json.loads((tree / "appended-engine-kernel-target.json").read_text()),
                            {"system": "Emscripten", "processor": "wasm32",
                             "triple": "wasm32-emscripten", "pointer_bits": 32})
                    else:
                        self.assertIn("independent lowercase SHA256", result.stdout + result.stderr)
                    self.assertFalse((tree / "graph-entered").exists())
                    self.assertFalse((tree / "appended-engine-physical-input").exists())
                    self.assertFalse(sentinel.exists())
            for language in ("CXX", "C"):
                tree = root / ("mismatched-" + language)
                result = subprocess.run(["cmake", "-S", str(root), "-B", str(tree), *complete,
                                        "-DCMAKE_" + language + "_COMPILER=" + str(root / "different-compiler")],
                                        capture_output=True, text=True, timeout=15, env=environment)
                with self.subTest(mismatched_compiler=language):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("configured " + language + " compiler differ", result.stdout + result.stderr)
                    self.assertFalse((tree / "appended-engine-kernel-target.json").exists())
                    self.assertFalse((tree / "graph-entered").exists())
                    self.assertFalse(sentinel.exists())

    def test_direct_cmake_physical_flag_cannot_select_or_bypass_maintenance(self):
        cmake = (ROOT / "CMakeLists.txt").read_text()
        options = cmake.split("# Appended profile options.\n", 1)[1].split(
            "# End appended profile options.", 1)[0]
        admission = cmake.split("# Appended retained-input admission.\n", 1)[1].split(
            "# End appended retained-input admission.", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Admission LANGUAGES NONE)\n' + options + admission +
                '\nfile(WRITE "${CMAKE_CURRENT_BINARY_DIR}/graph-entered" "unexpected")\n')
            for profile, maintenance in (("none", "OFF"), ("none", "ON"), ("binary", "ON"), ("web", "OFF")):
                tree = root / (profile + maintenance)
                result = subprocess.run(["cmake", "-S", str(root), "-B", str(tree),
                    "-DFOUNDATION_APPENDED_PROFILE=" + profile,
                    "-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=" + maintenance,
                    "-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=ON",
                    "-DFOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED=ON"],
                    capture_output=True, text=True, timeout=15)
                with self.subTest(profile=profile, maintenance=maintenance):
                    self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("Physical engine input requires explicit", result.stdout + result.stderr)
                    self.assertFalse((tree / "graph-entered").exists())
                    self.assertFalse((tree / "appended-engine-kernel-target.json").exists())

    def test_physical_graph_has_private_header_definition_and_readonly_export(self):
        # Mock only CMake's target primitives. No compiler/language or real
        # retained graph is configured; the actual optional graph is evaluated.
        graph = (ROOT / "cmake/AppendedGui.cmake").read_text()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "host").mkdir()
            for module in ("appended_browser_bootstrap", "appended_engine_browser_bootstrap",
                           "appended_engine_wasm_worker", "engine_kernel_bridge"):
                (root / "host" / (module + ".mjs")).write_text("// mocked graph asset\n")
            prelude = '''cmake_minimum_required(VERSION 3.24)
project(Graph LANGUAGES NONE)
set(FOUNDATION_APPENDED_PROFILE web)
set(EMSCRIPTEN TRUE)
set(BUILD_TESTING OFF)
set(FOUNDATION_APPENDED_ENGINE_CONSUMER_VERIFIED TRUE)
foreach(command add_library add_executable target_link_libraries add_dependencies
        set_target_properties foundation_options)
    function(${command})
    endfunction()
endforeach()
foreach(command target_include_directories target_compile_definitions target_link_options)
    function(${command} target)
        if(target STREQUAL "foundation-gui-appended-engine-wasm")
            file(APPEND "${CMAKE_CURRENT_BINARY_DIR}/observed" "${ARGV}\\n")
        endif()
    endfunction()
endforeach()
if(FOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT)
    file(MAKE_DIRECTORY "${CMAKE_CURRENT_BINARY_DIR}/appended-engine-physical-input")
    file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/appended-engine-physical-input/appended_engine_compiled_input_profile.hpp" "// graph fixture only")
endif()
'''
            (root / "CMakeLists.txt").write_text(prelude + graph)
            for physical in (False, True):
                tree = root / ("physical" if physical else "default")
                result = subprocess.run(["cmake", "-S", str(root), "-B", str(tree),
                    "-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=" + ("ON" if physical else "OFF")],
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                observed = (tree / "observed").read_text()
                self.assertIn("_gui_web_engine_input_describe_v1", observed)
                self.assertEqual("FOUNDATION_APPENDED_ENGINE_INPUT_PROFILE_ENABLED=1" in observed, physical)
                if physical:
                    self.assertIn("PRIVATE;" + tree.as_posix() + "/appended-engine-physical-input", observed)

    def test_cmake_physical_selection_is_explicit_and_binds_fresh_tree_identity(self):
        # Admission-script mocks test dispatch and cache identity only. They
        # supply no engine, compiler output, real profile or runtime receipt.
        cmake = (ROOT / "CMakeLists.txt").read_text()
        options = cmake.split("# Appended profile options.\n", 1)[1].split("# End appended profile options.", 1)[0]
        admission = cmake.split("# Appended retained-input admission.\n", 1)[1].split(
            "# End appended retained-input admission.", 1)[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inert_sdk(root)
            compiler = root / "sdk/unexecuted-compiler"
            compiler.write_text("not an executable compiler")
            metadata = json.loads((root / "sdk/sdk.json").read_bytes())
            metadata["target"]["cxx_compiler"] = compiler.name
            (root / "sdk/sdk.json").write_text(json.dumps(metadata))
            digest = hashlib.sha256((root / "sdk/sdk.json").read_bytes()).hexdigest()
            tools = root / "tools"
            tools.mkdir()
            (tools / "sdk_verify.py").write_text('print("' + digest + '")\n')
            ordinary = 'import json\nprint(json.dumps({"fixture":"identical-mock-consumer-facts"},sort_keys=True))\n'
            (tools / "appended_engine_consumer.py").write_text(ordinary)
            (tools / "appended_engine_input_profile.py").write_text(
                'import pathlib,sys\np=pathlib.Path(sys.argv[sys.argv.index("--build-root")+1])\n'
                '(p/"physical-adapter-selected").write_text("mock only")\n' + ordinary)
            toolchain = root / "cmake/toolchains/sdk.cmake"
            toolchain.parent.mkdir(parents=True)
            toolchain.write_text("# no language/toolchain execution\n")
            (root / "CMakeLists.txt").write_text(
                'cmake_minimum_required(VERSION 3.24)\nproject(Admission LANGUAGES NONE)\n'
                'set(Python3_EXECUTABLE "' + Path(sys.executable).as_posix() + '")\n'
                'set(CMAKE_SYSTEM_NAME Emscripten)\nset(CMAKE_SIZEOF_VOID_P 4)\n'
                'set(CMAKE_TOOLCHAIN_FILE "' + toolchain.as_posix() + '")\n'
                'set(CMAKE_CXX_COMPILER "' + compiler.as_posix() + '")\n'
                'set(FOUNDATION_BUILD_GUI ON)\nset(FOUNDATION_GUI_SOURCE "' + (root / "gui-input").as_posix() + '")\n'
                'set(FOUNDATION_SDK_ROOT "' + (root / "sdk").as_posix() + '")\n' + options + admission)
            base = ["-DFOUNDATION_APPENDED_PROFILE=web", "-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=ON",
                    "-DFOUNDATION_APPENDED_ENGINE_GROUP=" + str(root / "engine"),
                    *["-DFOUNDATION_APPENDED_ENGINE_" + pin + "_SHA256=" + "a" * 64
                      for pin in ("RECIPE", "MANIFEST", "PROOF", "RUNTIME")]]
            for initial in (False, True):
                tree = root / ("initial-physical" if initial else "initial-default")
                for choice, accepted in ((initial, True), (initial, True), (not initial, False)):
                    result = subprocess.run(["cmake", "-S", str(root), "-B", str(tree), *base,
                        "-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=" + ("ON" if choice else "OFF")],
                        capture_output=True, text=True, timeout=15)
                    with self.subTest(initial=initial, choice=choice, accepted=accepted):
                        self.assertEqual(result.returncode == 0, accepted, result.stdout + result.stderr)
                        if not accepted:
                            self.assertIn("Retained engine identity changed", result.stdout + result.stderr)
                        elif not initial:
                            self.assertFalse((tree / "physical-adapter-selected").exists())
                        else:
                            self.assertTrue((tree / "physical-adapter-selected").is_file())
    def test_mocked_operation_stops_after_engine_group_changes_during_configure(self):
        self.check_mocked_configure_operation(physical=False)

    def test_mocked_physical_operation_forwards_explicit_choice_and_stops_on_changed_inputs(self):
        self.check_mocked_configure_operation(physical=True)

    def check_mocked_configure_operation(self, *, physical):
        # Only operation ordering is mocked here; no eligible artifact, compiler
        # invocation, Foundation output or runtime evidence is produced.
        import source_identity
        import sdk_wasm
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            node = root / "sdk/node/bin/node"
            node.parent.mkdir(parents=True)
            node.write_bytes(b"unexecuted node sentinel")
            engine = {"root": str(root / "engine"),
                      "pins": {name: pin * 64 for name, pin in
                               (("recipe", "a"), ("manifest", "b"), ("proof", "c"), ("runtime", "d"))},
                      "consumer": {"group_files": {"mock-inventory": "e" * 64}}}
            if physical:
                engine["physical_input"] = True
            with patch.object(build, "ROOT", root), patch.object(build, "require_clean"), \
                    patch.object(build, "sdk_identity", return_value=sdk_sha256), \
                    patch.object(build, "engine_consumer_identity", return_value=engine), \
                    patch.object(build, "host_programs", return_value={name: name for name in ("cmake", "ctest", "cpack", "ninja")}), \
                    patch.object(sdk_wasm, "environment", return_value={}), \
                    patch.object(source_identity, "source_tree", return_value={}), \
                    patch.object(build, "recheck_engine_input", side_effect=[None, None, ValueError("group changed")]), \
                    patch.object(build, "run") as run:
                with self.assertRaisesRegex(ValueError, "group changed"):
                    build.main([*rich_options(root), *(["--engine-physical-input"] if physical else [])])
                run.assert_called_once()
                configure = run.call_args.args[0]
                self.assertIn("--preset", configure)
                self.assertIn("-DFOUNDATION_APPENDED_KERNEL_MAINTENANCE=ON", configure)
                self.assertIn("-DFOUNDATION_APPENDED_ENGINE_PHYSICAL_INPUT=" + ("ON" if physical else "OFF"), configure)
                self.assertIn("-DFOUNDATION_APPENDED_ENGINE_GROUP=" + str(root / "engine"), configure)
                for name, value in engine["pins"].items():
                    self.assertIn("-DFOUNDATION_APPENDED_ENGINE_" + name.upper() + "_SHA256=" + value, configure)
                saved = json.loads((root / "build/dev-sdk-gui-appended-web/wrapper-identity.json").read_text())
                self.assertEqual(saved["appended_engine"], engine)

    def test_sdk_change_after_engine_admission_stops_before_retained_tools(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sdk_sha256 = inert_sdk(root)
            engine = {"root": str(root / "engine"), "pins": {name: "a" * 64
                      for name in ("recipe", "manifest", "proof", "runtime")}}
            with patch.object(build, "ROOT", root), patch.object(build, "require_clean"), \
                    patch.object(build, "sdk_identity", side_effect=[sdk_sha256, "f" * 64]), \
                    patch.object(build, "engine_consumer_identity", return_value=engine), \
                    patch.object(build, "recheck_engine_input"), \
                    patch.object(build, "host_programs", return_value={}) as programs, \
                    patch.object(build, "run") as run:
                with self.assertRaisesRegex(ValueError, "SDK changed after retained-engine admission"):
                    build.main(rich_options(root))
                programs.assert_called_once_with()
                run.assert_not_called()
                self.assertFalse((root / "build").exists())


class CompiledInputProfileTests(unittest.TestCase):
    @staticmethod
    def fixture(root):
        import appended_engine_input_profile as profile
        group = root / "group"
        group.mkdir()
        build_root = root / "build"
        build_root.mkdir()
        target = root / "target.json"
        target.write_text(json.dumps({"system": "Emscripten", "processor": "wasm32",
                                      "triple": "wasm32-emscripten", "pointer_bits": 32}))
        arguments = ["--group", str(group), "--build-root", str(build_root),
                     "--kernel-target-json", str(target), "--paired-sdk-sha256", "e" * 64,
                     *[value for name, pin in (("recipe", "b"), ("manifest", "c"), ("proof", "d"), ("runtime", "f"))
                       for value in ("--" + name + "-sha256", pin * 64)]]
        return arguments, build_root / profile.HEADER_DIRECTORY / profile.HEADER_NAME

    def test_generated_profile_uses_fixed_commands_and_verified_pins(self):
        import appended_engine_input_profile as profile
        inspection = Mock()
        inspection.as_dict.return_value = physical_metadata()
        header = profile.compiled_header(inspection)
        self.assertIn('detail::digest("' + "a" * 64 + '")', header)
        self.assertIn('detail::digest("' + "b" * 64 + '")', header)
        self.assertIn("inline const EngineSurfaceProfileFacts compiled_engine_surface_profile", header)
        self.assertIn("800, 600, 1.0, kCommands, 0", header)
        self.assertIn("static_assert(kCommands ==", header)
        for name, value in (("production_eligible", False), ("whole_group_verified", False),
                            ("scope", "embedded-retained-consumer-byte-and-static-contract-only")):
            metadata = physical_metadata()
            metadata[name] = value
            inspection.as_dict.return_value = metadata
            with self.subTest(field=name), self.assertRaisesRegex(ValueError, "fully verified"):
                profile.compiled_header(inspection)

    def test_old_or_changed_static_facts_cannot_generate_enabled_header(self):
        import appended_engine_input_profile as profile
        inspection = Mock()
        for name, value in (("kind", "foundation-copied-engine-v1"), ("binding", "copied-owner-bridge/direct-worker-v1"),
                            ("capabilities", "259"), ("surface_capabilities", "32"),
                            ("command_catalog_sha256", "0" * 64), ("mouse_input_version", 2),
                            ("viewport_width", 801), ("display_scale", True),
                            ("build_sha256", "0" * 64), ("source_recipe_sha256", "0" * 64),
                            ("contract_sha256", '"; bad_cpp(); //')):
            metadata = physical_metadata()
            metadata["engine_profile"][name] = value
            inspection.as_dict.return_value = metadata
            with self.subTest(field=name), self.assertRaises(ValueError):
                profile.compiled_header(inspection)
        for name in ("recipe_id", "provider_build_sha256"):
            metadata = physical_metadata()
            metadata[name] = "c" * 64
            inspection.as_dict.return_value = metadata
            with self.subTest(retained_pin=name), self.assertRaisesRegex(ValueError, "verified retained pins"):
                profile.compiled_header(inspection)

    def test_helper_fully_verifies_once_then_saves_only_private_fixed_header(self):
        import appended_engine_consumer as consumer
        import appended_engine_input_profile as profile
        inspection = Mock()
        inspection.as_dict.return_value = physical_metadata()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = self.fixture(root)
            with patch.object(consumer, "verify_kernel_consumer", return_value=inspection) as verify, \
                    patch.object(sys, "stdout", new_callable=io.StringIO) as printed:
                self.assertEqual(profile.main(arguments), 0)
            verify.assert_called_once_with(root / "group", expected_recipe="b" * 64,
                expected_manifest="c" * 64, expected_proof="d" * 64, expected_runtime="f" * 64,
                paired_sdk="e" * 64, required_binding=consumer.PHYSICAL_BINDING,
                kernel_target={"system": "Emscripten", "processor": "wasm32",
                               "triple": "wasm32-emscripten", "pointer_bits": 32})
            self.assertEqual(json.loads(printed.getvalue()), physical_metadata())
            self.assertEqual(output.read_text(), profile.compiled_header(inspection))
            self.assertEqual(sorted(path.name for path in output.parent.iterdir()), [profile.HEADER_NAME])
            original = output.stat().st_mtime_ns
            with patch.object(consumer, "verify_kernel_consumer", return_value=inspection), \
                    patch.object(sys, "stdout", new_callable=io.StringIO):
                self.assertEqual(profile.main(arguments), 0)
            self.assertEqual(output.stat().st_mtime_ns, original)

    def test_ineligible_actual_group_and_invalid_profiles_leave_no_output(self):
        import appended_engine_consumer as consumer
        import appended_engine_input_profile as profile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = self.fixture(root)
            with self.assertRaisesRegex(ValueError, "engine group"):
                profile.main(arguments)
            self.assertFalse(output.parent.exists())
            inspection = Mock()
            metadata = physical_metadata()
            metadata["engine_profile"]["capabilities"] = "259"
            inspection.as_dict.return_value = metadata
            with patch.object(consumer, "verify_kernel_consumer", return_value=inspection), \
                    self.assertRaises(ValueError):
                profile.main(arguments)
            self.assertFalse(output.parent.exists())

    def test_output_aliases_and_retained_containment_fail_without_mutation(self):
        import appended_engine_consumer as consumer
        import appended_engine_input_profile as profile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = self.fixture(root)
            (root / "spacer").mkdir()
            for location in (root / "group", root / "spacer/../group"):
                selected = list(arguments)
                selected[selected.index("--build-root") + 1] = str(location)
                with self.subTest(location=str(location)), patch.object(consumer, "verify_kernel_consumer") as verify:
                    with self.assertRaises(ValueError):
                        profile.main(selected)
                    verify.assert_not_called()
                    self.assertFalse((root / "group" / profile.HEADER_DIRECTORY).exists())
            output.parent.mkdir()
            foreign = root / "foreign-header"
            foreign.write_bytes(b"preserve foreign input")
            os.link(foreign, output)
            with patch.object(consumer, "verify_kernel_consumer") as verify:
                with self.assertRaisesRegex(ValueError, "without aliases"):
                    profile.main(arguments)
                verify.assert_not_called()
            self.assertEqual(foreign.read_bytes(), b"preserve foreign input")
            self.assertEqual(output.read_bytes(), foreign.read_bytes())

    def test_duplicate_target_fields_are_rejected_before_verification_or_output(self):
        import appended_engine_consumer as consumer
        import appended_engine_input_profile as profile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = self.fixture(root)
            (root / "target.json").write_text('{"system":"Linux","system":"Emscripten"}')
            with patch.object(consumer, "verify_kernel_consumer") as verify:
                with self.assertRaises(ValueError):
                    profile.main(arguments)
                verify.assert_not_called()
            self.assertFalse(output.parent.exists())

    def test_private_header_cannot_overwrite_target_input(self):
        import appended_engine_consumer as consumer
        import appended_engine_input_profile as profile
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            arguments, output = self.fixture(root)
            output.parent.mkdir()
            original = (root / "target.json").read_bytes()
            output.write_bytes(original)
            arguments[arguments.index("--kernel-target-json") + 1] = str(output)
            with patch.object(consumer, "verify_kernel_consumer") as verify:
                with self.assertRaisesRegex(ValueError, "overwrite its target input"):
                    profile.main(arguments)
                verify.assert_not_called()
            self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
