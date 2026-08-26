# fixtures/pki — DEMO-ONLY key material

These certificates exist so the prebaked demo media carries **real, verifiable
C2PA signatures** without touching any production CA.

| File | Role |
|---|---|
| `demo_root.pem` / `demo_root.key` | self-signed demo trust anchor (the Doctus trust list, v1) |
| `demo_signer.pem` / `demo_signer.key` | studio signing identity (leaf, EKU emailProtection — required by c2pa-rs) |

**The private keys are public on purpose** (same practice as c2patool's own
test fixtures): they sign throwaway demo media only and confer zero authority.
Regenerate anytime with `python scripts/prebake_fixtures.py` after deleting
this directory — the media fixtures are then re-signed against the fresh root,
keeping the set self-consistent.

Never point the demo anchor at anything real, and never accept
`fixtures/pki` as a trust source outside this repository's tests.
