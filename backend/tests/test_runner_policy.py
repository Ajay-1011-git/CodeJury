import yaml

from codejury.runner import DockerRunner


def test_job_uses_fixed_isolation_flags_and_no_mounts(tmp_path):
    config = tmp_path / "runner.yaml"
    config.write_text(yaml.safe_dump({"image_id": "sha256:" + "a" * 64}))
    runner = DockerRunner(config)
    argv = runner.argv("codejury-job-test")
    assert argv[:4] == ["docker", "--context", "colima-codejury-stage1", "create"]
    assert "--mount" not in argv and "-v" not in argv and "--volume" not in argv
    for flag, value in [
        ("--network", "none"),
        ("--user", "65532:65532"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges"),
        ("--memory", "128m"),
        ("--pids-limit", "16"),
    ]:
        assert argv[argv.index(flag) + 1] == value
    assert "--read-only" in argv
