"""Ruby direct-constant observations; final-release admission remains unavailable.

Source-only candidate: this module must not be imported or executed before the
supervising protocol freezes the closure and authorizes the relevant checks.
"""

from protocol_contract import KIND, MissingMethod, closed_fields, integer, numeric_release


METHOD = "ruby-direct-builtins-v1"

_FIELDS = (
    "schema_version",
    "kind",
    "role",
    "ruby_version",
    "ruby_engine",
    "ruby_engine_version",
    "ruby_patchlevel",
)


def observed_numeric(value) -> str:
    """Validate the whole observation and return its numeric Ruby version.

    Requiring engine ``ruby`` and equal language/engine numeric versions is a
    conservative project policy, not a guarantee inferred from vendor examples.
    Numeric observation does not establish that this is a final release.
    """
    closed_fields(value, _FIELDS, "ruby runtime version")
    integer(value["schema_version"], "ruby schema version", min=1, max=1)
    if type(value["kind"]) is not str or value["kind"] != KIND:
        raise ValueError("unexpected ruby runtime version kind")
    if type(value["role"]) is not str or value["role"] != "ruby":
        raise ValueError("unexpected ruby runtime version role")

    version = numeric_release(value["ruby_version"], "ruby version")
    if type(value["ruby_engine"]) is not str:
        raise ValueError("ruby engine must be a string")
    engine_version = numeric_release(value["ruby_engine_version"], "ruby engine version")
    integer(value["ruby_patchlevel"], "ruby patch level", min=-1, max=2147483647)
    if value["ruby_engine"] != "ruby":
        raise MissingMethod("windows-runtime-version-ruby-engine")
    if engine_version != version:
        raise ValueError("ruby engine version must equal ruby version by project policy")
    return version


def validate(value) -> str:
    """Apply final-release policy after whole-observation validation.

    The reviewed documentation states development implies patch level -1; it
    supplies no converse or complete final/preview/release-candidate predicate.
    """
    observed_numeric(value)
    if value["ruby_patchlevel"] == -1:
        raise ValueError("ruby development build is not a final release")
    raise MissingMethod("windows-runtime-version-ruby-final-release")


def argv(program_path: str, emitter_path: str) -> list:
    """Return fixed documented flags for controller-pinned program/script paths."""
    for label, path in (("ruby program path", program_path), ("ruby emitter path", emitter_path)):
        if type(path) is not str or not path or len(path) > 4096:
            raise ValueError(f"{label} must be a nonempty string of at most 4096 characters")
        if any(character in path for character in ("\x00", "\r", "\n")):
            raise ValueError(f"{label} must not contain NUL, CR, or LF")
    return [
        program_path,
        "--disable=gems,did_you_mean,rubyopt,jit",
        "--",
        emitter_path,
    ]
