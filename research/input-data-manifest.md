# Input data manifest

## Original combined archive

The earlier local combined archive is retained only as provenance:

- filename: `Vic3_data.zip`
- SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- compressed size: 122,267,140 bytes
- uncompressed size: 323,589,511 bytes
- files: 8,104 including macOS metadata entries

The combined archive is not required in the repository.

## Selected same-repository input files

Store the reduced inputs under `input-data/` as separate files:

| File | Bytes | Approx. MiB | SHA-256 |
| --- | ---: | ---: | --- |
| `jomini.zip` | 173,384 | 0.165 | `b50301358a63c20365ed614098f9c851d353969e3f9d7c1ede819f2658066395` |
| `clausewitz.zip` | 132,337 | 0.126 | `3ca3cbd5a14b6c6429cc75e4678738e339a96700ef8ad70c48ee0439f2bc1e9a` |
| `game.zip` | 17,056,424 | 16.266 | `697e5c147b54eb4f006b5532f9d65fb91449d45d1a2acf12b10d8a2b385abb8a` |

All three are below GitHub's normal 100 MiB single-file hard limit; Git LFS is therefore not technically required for these three files. GitHub may still warn on large files above lower advisory thresholds.

## Build identifiers

Committed separately under `input-data/build-info/`:

- `caligula_branch.txt`: `release/1.14.5`
- `caligula_rev.txt`: `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- `clausewitz_branch.txt`: `caligula/release/1.14.x`
- `clausewitz_rev.txt`: `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`

## Storage rule

Keep the repository private. The technical GitHub size limit is separate from copyright/license permissions; do not make third-party game data public without confirming the applicable terms.

After each archive is uploaded, verify its SHA-256 against the table above before using it as research input.
