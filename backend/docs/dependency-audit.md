# Dependency audit — A.01

Inspected 2026-10-11 on native macOS ARM64 with 17,179,869,184 bytes (16 GiB) RAM. Python 3.11.16 was installed through uv; all backend dependencies are resolved in `backend/uv.lock`. Reproduce with `uv sync --extra model --locked` from backend. The installed MLX-LM distribution requires Python >=3.11; the project keeps the specified Python 3.11 runtime.

Tested installed versions: FastAPI 0.143.0, Pydantic 2.14.0, jsonschema 4.26.0, Hypothesis 6.169.0, Uvicorn 0.54.0, MLX 0.32.3, MLX-LM 0.32.0, pytest 9.1.1. Docker CLI 29.5.3 (build d1c06ef) exists. Docker context is `desktop-linux`, but its daemon socket does not exist. Colima is absent; VM mount isolation and ARM64 runner verification remain A.03 work. No candidate code was executed on the host.

## Sources accessed and inspected interfaces

- [jsonschema Draft 2020-12 validation](https://python-jsonschema.readthedocs.io/en/stable/validate/): use `Draft202012Validator.check_schema` and `validate`; the wrapper retains root `$defs` and points `$ref` to the named definition. Installed constructor signature was inspected.
- [FastAPI validation errors](https://fastapi.tiangolo.com/tutorial/handling-errors/): `FastAPI.exception_handler` exists; its installed signature accepts an exception class or status code. [StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/) is reserved for integration; installed `StaticFiles(directory=..., html=..., check_dir=..., follow_symlink=False)` was inspected.
- [MLX-LM LoRA](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md): actual installed CLI help was run outside the filesystem sandbox because sandboxed Metal initialization fails. Native CLI import succeeds. Verified options include `--model`, `--train`, `--data`, `--mask-prompt`, `--num-layers`, `--batch-size`, `--iters`, `--grad-accumulation-steps`, `--adapter-path`, `--max-seq-length`, `--grad-checkpoint`, `--seed`, and YAML `--config`. Preferred entry is `python -m mlx_lm lora`; direct `python -m mlx_lm.lora` reports deprecation. These are observed interfaces, not evidence of model inference or training.
- [Microsoft Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct) and [chosen MLX conversion](https://huggingface.co/mlx-community/Phi-4-mini-instruct-mlx-4Bit): public Hub metadata inspected through `https://huggingface.co/api/models/mlx-community/Phi-4-mini-instruct-mlx-4Bit`. Conversion revision `d848c30f6d5419b9892433cf6b1062626d15340e`, MIT license, `model_type=phi3`, `Phi3ForCausalLM`, 4-bit quantization. Installed `mlx_lm/models/phi3.py` contains `qkv_proj` and `o_proj`. This proves a relevant implementation is present, not that this checkpoint loads/trains correctly. Weight/tokenizer hashes and actual module target inspection are deferred to A.06. No remote Python code is enabled.
- [Colima](https://github.com/abiosoft/colima) and [Docker run](https://docs.docker.com/reference/cli/docker/container/run/): installed `docker run --help` verifies `--platform`, `--network`, `--user`, `--read-only`, `--tmpfs`, `--cap-drop`, `--security-opt`, `--memory`, `--pids-limit`, `--cpus`, `--init` and `--pull`. Colima's installed help cannot yet be inspected because it is absent.

## Seed exception and pending checks

Ajay approved initializing the missing seed from the guides. Schema extraction is byte-for-byte with the required SHA-256 `5f760939e1fbf34cb7613a38f9476595d23a829089e8e557adc015cb0168f0df`. The eight fixtures are newly authored synthetic examples, not recovered originals. The architecture reference is copied byte-for-byte. This is recorded in `contracts/README.md`; subsequent task changes are backend-only.

Pending: real checkpoint load/generate, 10–20-step train/save/reload pilot, isolated VM mounts, ARM64 image digest and execution. A.01 permits these to remain pending. Stage 1 milestones are not complete.

## A.03 installed/runtime follow-up

Installed Colima 0.10.3 and Lima 2.2.1. `colima start --help` confirmed `--mount none`, `--activate=false`, `--ssh-agent=false`, `--ssh-config=false`, `--arch aarch64`, `--vm-type vz`, `--dns`, CPU/memory/disk controls. `docker --context colima-codejury-stage1` is used explicitly; the user's existing default context was preserved. Both effective Lima configuration and guest mount table were inspected. ARM64 Python 3.11.16 image digest and eight actual runner tests are recorded in handoff.md. No Linux MLX/CUDA stack is installed.
