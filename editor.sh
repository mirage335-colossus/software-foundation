#!/bin/sh
set -eu

# Usage: ./editor.sh [editor arguments, e.g. --project editor/self/project.json]
# Prefer the retained native SDK documented in COMPILE-editor. Without it,
# use the system toolchain in the build wrapper's default development tree.
root=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
cd "$root"
sdk="$root/build/agents/rust-package-qualification/sdk"
build_dir="$root/build/editor-fltk-dev"
if [ -f "$sdk/sdk.json" ]; then
    build_dir="$root/build/editor-fltk-sdk"
fi
editor="$build_dir/foundation-editor-fltk"

# Reuse an existing executable; rebuilding after source edits is explicit.
if [ ! -x "$editor" ]; then
    if [ -f "$sdk/sdk.json" ]; then
        ./build.sh editor build dev --backend fltk --sdk "$sdk" --build-dir "$build_dir"
    else
        ./build.sh editor build dev --backend fltk --build-dir "$build_dir"
    fi
fi

exec "$editor" "$@"
