#!/usr/bin/env python3
"""Explicit payload tools. No operation falls back to a native kernel build."""
import argparse
import importlib
import sys


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    routes = {
        "compile": ("appended_compile", "compile"),
        "pack": ("appended_container", "pack"),
        "inspect": ("appended_container", "inspect"),
        "verify": ("appended_container", "verify"),
        "strip": ("appended_container", "strip"),
        "compose": ("appended_container", "compose"),
        "kernel-seal": ("appended_kernel", "seal"),
        "policy": ("appended_policy", None),
        "prepare-release": ("appended_release", "prepare-release"),
        "prepare-checkout": ("appended_checkout", None),
        "verify-candidate": ("appended_release", "verify-candidate"),
        "verify-composition": ("appended_release", "verify-composition"),
        "qualification": ("appended_qualification", None),
        "release-check": ("appended_release_check", None),
        "delivery": ("appended_delivery", None),
        "recover": ("appended_release", "recover"),
        "browser-kernel": ("package_appended_wasm", None),
        "rich-browser-kernel": ("package_appended_engine_wasm", None),
        "document-browser-kernel": ("package_appended_engine_document_wasm", None),
    }
    parser = argparse.ArgumentParser(description=__doc__, usage="build.sh appended ACTION [OPTIONS]",
        epilog="Actions: " + ", ".join(routes) + ". Use ACTION --help for exact inputs. "
               "kernel-seal finalizes a newly built kernel once; compose only preserves already finalized bytes.")
    if not arguments or arguments[0] in ("-h", "--help"):
        parser.print_help()
        return 0
    action = arguments[0]
    if action not in routes:
        parser.error("unknown appended action: " + action)
    module_name, operation = routes[action]
    module = importlib.import_module(module_name)
    options = arguments[1:]
    if operation is not None:
        options = [operation, *options]
    return module.main(options)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as error:
        print("appended: " + str(error), file=sys.stderr)
        sys.exit(1)
