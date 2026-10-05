# Input data manifest

## Full research archive

The combined archive is intentionally stored in this private repository through Git LFS because retaining the exact input materially reduces repeated setup and improves reproducibility across devices.

| Field | Value |
| --- | --- |
| Path | `input-data/Vic3_data.zip` |
| Storage | Git LFS |
| LFS object size | 124,462,636 bytes |
| LFS object SHA-256 | `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34` |

The archive includes the exact 1.14.5 analysis input used by this project, including `victoria3.exe` and `victoria3_win_console.exe`. Build identity is still verified independently before any binary-derived conclusion or future hook is accepted.

Do not replace or regenerate this archive silently. If it changes, record the new hash, size, provenance, and affected analysis.

## Reduced inputs

Smaller archives remain useful when the full LFS object is unnecessary:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `input-data/jomini.zip` | 173,384 | `b50301358a63c20365ed614098f9c851d353969e3f9d7c1ede819f2658066395` |
| `input-data/clausewitz.zip` | 132,337 | `3ca3cbd5a14b6c6429cc75e4678738e339a96700ef8ad70c48ee0439f2bc1e9a` |
| `input-data/game.zip` | 17,056,424 | `697e5c147b54eb4f006b5532f9d65fb91449d45d1a2acf12b10d8a2b385abb8a` |

These files are normal Git inputs; Git LFS is not required for them at their current sizes.

## Build identifiers

Stored under `input-data/build-info/`:

- `caligula_branch.txt`: `release/1.14.5`
- `caligula_rev.txt`: `9f8281a37e85639359b3b0c2c5df0196e975ca4b`
- `clausewitz_branch.txt`: `caligula/release/1.14.x`
- `clausewitz_rev.txt`: `fd5e1dbd038c3c4a3f48a36abf60ebb42dd0ceef`

## Additional preserved evidence

`input-data/pc-evidence-2026-10-05/` contains the deliberately selected logs, scripts/configuration, benchmark/sensor material, inventories, and split recoverable benchmark save described in:

- `docs/superpowers/reports/2026-10-05-pc-evidence-preservation-ja.md`

The report and generated indexes define the detailed provenance and coverage. Avoid duplicating that large inventory here.

## Storage policy

- keep the repository private
- retain `input-data/Vic3_data.zip` in Git LFS while it remains useful to active research
- verify hashes before using binary-derived evidence
- keep small, high-value extracted inputs when they reduce repeated work
- keep unrelated or low-value large game assets outside the repository
- keep raw ETL/uProf captures local unless a specific reproducibility need justifies repository storage
- preserve hashes, inventories, derived analysis, and concise provenance even when large raw data is kept elsewhere
- treat technical Git/Git LFS limits separately from copyright/license permissions; do not redistribute third-party game data without confirming the applicable terms
