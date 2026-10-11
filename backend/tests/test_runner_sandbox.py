import json
import os
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
import yaml

from codejury.properties import equal
from codejury.runner import Cancelled, DockerRunner, InfrastructureError

pytestmark = [
    pytest.mark.sandbox,
    pytest.mark.skipif(
        os.getenv("CODEJURY_SANDBOX_TESTS") != "1",
        reason="Enable CODEJURY_SANDBOX_TESTS=1 for real isolated execution",
    ),
]


@pytest.fixture
def runner():
    runner = DockerRunner()
    runner.ready()
    return runner


def test_success_and_assertion_mismatch(runner):
    result = runner.execute("def total(values):\n    return sum(values)\n", "total", [[1, 2]])
    assert equal(result.actual_output, 3)
    assert not equal(result.actual_output, True)
    assert result.exception_type is None
    assert not equal(result.actual_output, 99)


def test_loop_timeout_and_mutation(runner):
    result = runner.execute("def total(values):\n    while True:\n        pass\n", "total", [[]])
    assert result.exception_type == "TimeoutError"
    mutation = runner.execute(
        "def total(values):\n    values.append(9)\n    return 9\n", "total", [[]]
    )
    assert mutation.input_mutated


def test_output_bound_and_trace_truncation(runner):
    result = runner.execute("def total(values):\n    return [0]*10000\n", "total", [[]])
    assert result.exception_type == "ValueError" and result.actual_output is None
    printed = runner.execute(
        "def total(values):\n    print('x'*10000)\n    return 1\n", "total", [[]]
    )
    assert printed.actual_output == 1
    assert printed.trace_truncated and sum(map(len, printed.trace)) <= 4096


def test_cancel_kills_whole_job_and_leaves_no_container(runner):
    cancel = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            runner.execute,
            "def total(values):\n    while True:\n        pass\n",
            "total",
            [[]],
            cancel,
        )
        timer = threading.Timer(0.5, cancel.set)
        timer.start()
        with pytest.raises(Cancelled):
            future.result(timeout=10)
        timer.join()
    jobs = subprocess.run(
        runner.docker("ps", "-aq", "--filter", "name=codejury-job-"),
        check=True,
        capture_output=True,
        text=True,
    )
    assert jobs.stdout.strip() == ""


def test_missing_image_never_falls_back_to_host(tmp_path):
    config = tmp_path / "runner.yaml"
    config.write_text(yaml.safe_dump({"image_id": "sha256:" + "0" * 64}))
    with pytest.raises(InfrastructureError):
        DockerRunner(config).execute("def f(x):\n    return x\n", "f", [1])


def trusted_probe(runner, script, timeout=5):
    """Trusted isolation probe, never a user-facing arbitrary command interface."""
    name = "codejury-probe-" + uuid.uuid4().hex
    argv = runner.argv(name)
    argv[-1:-1] = ["--entrypoint", "python"]
    argv.extend(["-I", "-c", script])
    try:
        subprocess.run(argv, check=True, capture_output=True, timeout=15)
        inspection = runner.inspect_job(name)
        assert inspection["mounts"] == [] and inspection["network"] == "none"
        return subprocess.run(
            runner.docker("start", "-a", name),
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    finally:
        subprocess.run(runner.docker("rm", "-f", name), check=True, capture_output=True, timeout=10)


def test_network_denied_and_forbidden_mount_inspection(runner):
    script = """import socket,json,os
s=socket.socket(); s.settimeout(1)
try:
 s.connect(('1.1.1.1',443)); denied=False
except OSError:
 denied=True
print(json.dumps({'denied':denied,'uid':os.getuid(),'home_mount':os.path.exists('/Users')}))
"""
    result = json.loads(trusted_probe(runner, script).stdout)
    assert result == {"denied": True, "uid": 65532, "home_mount": False}


def test_forked_process_watchdog_kills_container(runner):
    script = "import os,time; os.fork(); time.sleep(60)"
    with pytest.raises(subprocess.TimeoutExpired):
        trusted_probe(runner, script, timeout=1)
    jobs = subprocess.run(
        runner.docker("ps", "-aq", "--filter", "name=codejury-probe-"),
        check=True,
        capture_output=True,
        text=True,
    )
    assert jobs.stdout.strip() == ""
