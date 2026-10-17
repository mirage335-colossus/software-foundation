"""Private Perl builtin numeric observation; never original native admission.

The raw whole-document decoder belongs to the parent protocol. This module only
checks a fully decoded object. Perl final-versus-release-candidate authority is
not established by the documented version builtin, so final validation remains
an explicit source gap. No emitter or selected runtime is executed here.
"""
from protocol_contract import KIND, MissingMethod, closed_fields, integer, numeric_release

METHOD = 'perl-builtin-version-series-only-v1'
_FIELDS = ('schema_version', 'kind', 'role', 'perl_version', 'taint_mode')


def observed_numeric(value):
    """Return the interpreter's declared numeric builtin observation only."""
    closed_fields(value, _FIELDS, 'Perl builtin version')
    integer(value['schema_version'], 'Perl builtin schema', 1, 1)
    if value['kind'] != KIND or value['role'] != 'perl':
        raise ValueError('Perl builtin kind/role differs')
    release = numeric_release(value['perl_version'], 'Perl builtin version')
    if release.split('.')[0] != '5':
        raise ValueError('Reviewed Perl 5 builtin observation required')
    integer(value['taint_mode'], 'Perl enforced taint mode', 1, 1)
    return release


def validate(value):
    """A numeric builtin/series label cannot establish a final Perl release."""
    observed_numeric(value)
    raise MissingMethod('windows-runtime-version-perl-final-release')


def argv(program_path, emitter_path):
    """Build documented fixed flags; physical/path identity remains external."""
    for value in (program_path, emitter_path):
        if (type(value) is not str or not 1 <= len(value) <= 4096 or
                any(character in value for character in ('\x00', '\r', '\n'))):
            raise ValueError('Explicit bounded Perl program/emitter path required')
    return [program_path, '-T', '-f', '--', emitter_path]

