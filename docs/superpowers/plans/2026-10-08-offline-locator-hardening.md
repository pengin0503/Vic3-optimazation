# Offline locator hardening implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline with TDD.
> The user waived approval waits; do not dispatch implementation subagents.

**Goal:** Verify caller metadata offline and protect the selected input.
**Architecture:** Extend the existing locator, reusing RuntimeFunctionIndex.
**Tech Stack:** Python standard library; existing C++ regression builds.
**Spec:** ../specs/2026-10-08-offline-locator-hardening-design.md

## Global Constraints

- Fixed executable/source hashes and generated include remain unchanged.
- No live process access, DLL/hook changes or native optimization activation.
- Static association is not proof of ABI, unwind correctness or lifetime.

## Review Focus

- Chained fragments must resolve to the declared root, not the nearest start.
- Gaps and overlapping ranges cannot be treated as caller code.
- Exception directory must be used, not arbitrary .pdata padding.
- Truncated/overflowing/zero-fill metadata fails closed.
- Directory input with an external hard-link output preserves the exe.

### Task 1: Caller metadata verification

Files: tools/check_lookup_contract_locator.py,
tests/test_lookup_contract_locator.py, .github/workflows/lookup-reuse-contract.yml.
Consumes: verify_owned_image(image: bytes, manifest: dict) -> dict.
Produces: same API with verified caller metadata and true verification flag.

- [ ] Extend the mini fixture with literal exception records; add direct,
  chained-root, wrong-root, gap, overlap, malformed chain, and bad directory tests.
- [ ] Run locator tests; confirm missing checks fail with assertions.
- [ ] Implement bounded exception-directory parsing and RuntimeFunctionIndex
  association checks; require every byte of the call to be covered.
- [ ] Run all Python tests; add runtime_function_groups.py to workflow paths.
- [ ] Record RED/GREEN and exact ZIP evidence; save code with tests.

### Task 2: Selected executable output protection

Files: tools/check_lookup_contract_locator.py, tests/test_lookup_contract_locator.py.
Consumes: check_output_path(input_path: Path, output_path: Path) -> None.
Produces: same API refusing external hard links to selected directory exe.

- [ ] Add a real temporary-filesystem external hard-link test.
- [ ] Run it; confirm current guard incorrectly accepts the alias.
- [ ] Resolve the same executable selected by read_input; reject same-file output.
- [ ] Run all Python tests, exact ZIP locator, B0 Release CTest and runner.
- [ ] Review changed files, record limits and results, commit to main by
  force-free fast-forward with an expected-SHA lease, then verify CI.
