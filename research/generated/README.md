# Generated research inventories

These files are derived from the locally supplied Victoria 3 1.14.5 research archive using `tools/analyze_vic3.py`.

Verified target executable:

- size: 97,774,200 bytes
- SHA-256: `9b6f133a5dc235de9135d7b57e86ceda8282d1ba6c0e185f3ee19c22f8917f54`
- PE32+ x86-64
- linker: MSVC 14.44
- sections: `.text`, `.rdata`, `.data`, `.pdata`, `.rsrc`, `.reloc`
- embedded PDB path: `C:\mnt\gsg\caligula\caligula\outputdir_windows\binaries\victoria3.pdb`

Current extraction counts:

- 260 unique `CTickTask_*` names
- 24 imported DLLs
- 17 profiler/console command identifiers
- more than 900 source-code path strings
- task/job/parallelism RTTI/template strings including Pdx parallel/task infrastructure

Committed compact inventories:

- `ticktasks-1.14.5.txt`
- `profiler-commands-1.14.5.txt`
- `imports-1.14.5.txt`

The full JSON output, including import symbols, source paths and RTTI/job strings, is intentionally regenerated locally rather than treated as a hand-maintained source file:

```text
python tools/analyze_vic3.py <Vic3_data.zip-or-install> \
  --output research/generated/static-analysis-local.json
```

The integration test validates the known 1.14.5 executable hash and key recovered interfaces when `VIC3_DATA` points to the local archive.
