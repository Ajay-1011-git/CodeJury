# Canonical Stage 2 service

The Stage 2 API and existing browser UI run together on loopback:

```sh
CODEJURY_STAGE2_RUNNER_IMAGE=sha256:3a0eda85cef3c470ee50838c2d4c0d5208ad0debc2c9578e90ae91677227d61f \
python -m codejury.stage2_core.serve --port 8002
```

Open `http://127.0.0.1:8002/`. Stage 1's service and evidence remain separate. Known archived Stage 1 IDs return 409; unknown IDs return 404. The legacy lookup opens only the old database read-only and reads IDs, never old sources.

The service validates the frozen stage2.v1 contract, bounds request bodies, allows only local development origins and serves schema-checked errors, health, examples, snapshots, monotonic events, candidates, cancellation and read-only reports. A run is durably queued before dispatch. Native compute must actually be acquired before admission; busy or unavailable compute creates no accepted run. One runtime slot and a separate server-instance lock prevent duplicate work. Restart marks abandoned queued/running work as infrastructure failure and never silently resumes it.

Learned policy requires all four completed role cards. Health and training reports expose only actual registered roles; incomplete roles cannot become a ready learned service. Final benchmark remains not_run until a genuine frozen evaluation report exists. Public demo examples overlap training families and are unscored. Detailed private labels, hidden tests, weights and arbitrary artifact paths have no HTTP route.

CPU API/controller/continuation tests pass. Native learned-policy browser acceptance awaits the Critic/Judge releases; these unit checks do not certify that acceptance.
