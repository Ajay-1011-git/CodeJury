# Ajay backend handoff

Git identity: Ajay M <ajaym556677@gmail.com>. No co-author attribution. User explicitly authorized commits and pushes to `main` after each audited task.

Shared seed base: `c0ef9625f8a7781433d4692222a18cc86a43ae02`. Initial upstream commit: `8db26b3`. The approved seed initialization precedes the backend-only work. Frozen schema hash: `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`.

| Task | Status | Evidence |
| --- | --- | --- |
| A.01 | Complete, model/runner checks pending as permitted | Six CPU tests, eight contract fixtures, environment and lint checks; versions/source audit in dependency-audit.md |
| A.02 | Complete | 36 intake/oracle/storage tests; frozen checker passes |
| A.03 | Complete | Five real self-checks and eight runner tests; image/mount evidence below |
| A.04–A.09 | Not started | No completion or measured-learning claim |

## A.01 actual verification

Commands run from backend using `.venv/bin/python`:

```text
python tools/check_environment.py
python=3.11.16 system=Darwin machine=arm64 foundation_ready=true
docker_cli=true colima_cli=false
model_inference=pending A.06 native smoke and training pilot
sandbox_execution=pending A.03 isolated execution checks
memory_bytes=null within sandbox; native sysctl independently returned 17179869184

python -m pytest tests/test_environment.py -q
6 passed in 0.56s

python -m codejury.contracts.check ../contracts
PASS error.json: Error
PASS event-page.json: EventPage
PASS examples.json: Examples
PASS health.json: Health
PASS run-accepted.json: RunAccepted
PASS run-create.json: RunCreate
PASS run-queued.json: RunSnapshot
PASS training-report.json: TrainingReport
PASS schema SHA-256 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df; 8 fixtures
```

Audit found and corrected import ordering and made subprocess failure handling explicit. The checker refuses missing/changed schemas, unknown definitions, extra/missing wire fields, fixture symlinks, path traversal and unlisted JSON fixtures. Initial tests use synthetic fixtures only. Native MLX CLI help succeeds; actual inference/training remains pending. Docker daemon is unavailable and Colima is absent.

The A.01 commit can be found with `git log --grep='A.01' --format='%H %s'`; storing its own hash in the same commit would require rewriting that hash.

## A.02 actual verification

```text
python -m pytest tests/test_intake.py tests/test_oracles.py tests/test_storage.py -q
36 passed in 1.23s
python -m codejury.contracts.check ../contracts
PASS schema SHA-256 5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df; 8 fixtures
ruff check src tests tools
All checks passed!
```

Audit: submitted source is parsed only; default/annotation/decorator execution, imports, nested helpers, generators and global state are rejected. JSON bounds are depth 8, 4096 nodes, 8000-character strings and JS-exact integers. Domains reject bool/float values. Property templates use trusted deterministic implementations and type-sensitive recursive equality. Runtime paths must be disjoint from offline data. SQLite triggers enforce append-only events and immutable candidate rows; parallel append/reopen tests prove stable ordered IDs. No model or sandbox evidence is claimed.

## A.03 actual verification

```text
python -m codejury.runner.cli self-test --profile stage1-demo
architecture=arm64 host_mounts=[]
success actual_output=3 exception_type=null
input_mutation actual_output=10 input_mutated=true
timeout exception_type=TimeoutError duration_ms=2004
oversized_output exception_type=ValueError actual_output=null
PASS independent assertion mismatch detection; 5 real checks
CODEJURY_SANDBOX_TESTS=1 python -m pytest tests/test_runner_policy.py tests/test_runner_sandbox.py -q
8 passed in 5.19s
```

Runner image: `sha256:29ae090c8377a4e3d482dd6efa6fdee6a0d46a5d8eaabf916556ee341ae118b9`. Base Python 3.11.16 image: `python@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e`. Colima 0.10.3/Lima 2.2.1; VM Docker 29.5.2. Dedicated `codejury-stage1` VZ VM: aarch64, 2 CPUs, 2 GiB RAM, 10 GiB data disk; `--mount none`, no SSH agent/config forwarding, no global Docker-context activation. Initial DNS failure was resolved with explicit DNS 1.1.1.1 and 8.8.8.8. Effective `/proc/mounts` contains root/data/cidata and kernel filesystems, no `/Users`, home share, virtiofs or sshfs.

Each job is created then inspected before start: network none, no mounts/binds, UID 65532, read-only root, dropped ALL capabilities, no-new-privileges, 128 MiB memory/swap, PID limit 16, CPU 1 and 16 MiB tmpfs. Source/input are stdin data. Output/trace are bounded. A 2-second function timer and 4-second host watchdog are separate; cancellation removes the entire container. Real trusted probes verified blocked external TCP access and cleanup of both processes after `os.fork`. Candidate builtins and introspection are restricted inside the VM; this is additional defense, not a host-execution fallback.
