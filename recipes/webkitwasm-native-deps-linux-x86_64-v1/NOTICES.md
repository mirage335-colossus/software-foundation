# Notice retention boundary

The fifteen source archive identities are fixed in `profile.json`. They are
source inputs, not permission or native binary qualification records. The source
manifest must independently name the original supplier notices, and the asset
manifest must independently name the font/data/certificate notices. The
orchestrator admits their exact bytes and supplies their complete nonempty union
as `NATIVE_NOTICE_FILES`.

The install adapter copies these ordinary files to
`share/licenses/foundation-native-dependencies/` using an index and the original
basename, so equal basenames from different origins cannot overwrite each other.
Original manifest references preserve the relation between each retained notice
and its source/asset. No license text is synthesized or inferred from a library
name. All applicable static-link/source/relinking and redistribution obligations
still require review of the actual resulting binary closure before distribution.
