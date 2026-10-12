Stage2 integration custodian: inspect real dependencies, seed compatible common constraints, record the common commit, then wire owner factories at E checkpoints. No automatic service starts.

The shared seed includes `constraints.txt`, observed from the existing Python
3.11/macOS ARM64 environment. Install the existing backend with `uv sync --frozen
--python 3.11 --extra model`; the unchanged `backend/uv.lock` governs dependencies.
Owner dependency proposals must agree with the common constraints; only the
integrator changes the package manifest/lock at a checkpoint.

From `backend/`, ` .venv/bin/python ../integration/stage2/bootstrap.py` checks
the frozen schema, fixtures and discoverable Python ports. It starts no service.
See `backend/docs/stage2_core/audit.md` for actual baseline evidence and limits.
Both owners branch from the A2.01 seed in separate clones/worktrees.

The Sarvesh tools/workbench branch is integrated. See [HANDOFF.md](HANDOFF.md)
for actual Mac MLX inspection, native sandbox/tool checks and remaining learning
dependencies. Stage 2's live service, real A/B episode collection, Critic/Judge/general
training and final benchmark remain pending; module integration is not E2/E4 completion.
