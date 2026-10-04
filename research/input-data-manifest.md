# Input data manifest

## Current archive

- Local filename: `Vic3_data.zip`
- SHA-256: `79f4f6d2c54528be378ffb09aa2d62d02c1f01279b967dd3189178146d5e8c34`
- Compressed size: 122,267,140 bytes
- Uncompressed size: 323,589,511 bytes
- Files: 8,104 including macOS metadata entries

## Storage rule

The archive contains proprietary Victoria 3 files and must not be committed to this optimization repository.

Use a separate private data repository/local storage. Because the archive is larger than GitHub's normal 100 MiB per-file limit, store it with Git LFS or another private binary-storage mechanism rather than ordinary Git.

Expected data-repository contents:

- `Vic3_data.zip` tracked by LFS
- `SHA256SUMS.txt`
- optional `README.md` stating that the repository is private research input and must not be made public

The optimization repository should reference the archive only by filename/hash/build metadata.
