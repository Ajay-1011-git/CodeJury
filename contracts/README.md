# Stage 1 seed provenance

Initialized on 2026-10-11 with Ajay's explicit approval because the upstream repository contained only four Markdown guides.

`stage1-api.schema.json` is the exact UTF-8 JSON code block extracted from `01-Stage1-Ajay-Build.md`, including its final newline. Its SHA-256 matches the guide's frozen checksum. No reformatting was performed. `reference/CodeJury-Final-Architecture.md` is a byte-for-byte copy of the root architecture document.

The eight fixtures and filename-to-definition manifest are **new synthetic seed examples**, not recovered originals, inference outputs, training results, or measured evidence. Response fixtures use `runtime_mode: fixture`; the request fixture is a public input suitable for later live execution. The original seed pack was not present. This initialization is the user-approved exception to backend-only ownership; subsequent task changes stay under `backend/`.
