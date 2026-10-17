# Synthetic dependency producer fixtures

`source-pins.json` freezes the reviewed fifteen supplier archive identities and
component dependencies independently of the executable recipe. Tests compare
the recipe with these expected values; they never open supplier archives.

The test module creates tiny tar/zip byte fixtures and inert program-path
declarations in private temporary directories. Every program launch is forbidden
or replaced with a `unittest.mock` fake. No compiler, CMake, SDK, engine, network
request or child process is executed. Passing these cases establishes parser,
archive, recipe and supervision behavior only, not a built or qualified prefix.
