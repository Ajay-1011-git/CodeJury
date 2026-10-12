# ARM64 runner image for Stage 2 candidate execution. Build context: this directory.
# Base is the same digest pinned by the original Stage 1 runner (backend/config/runner.yaml).
FROM python@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e
RUN useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin runner
COPY entry.py /opt/codejury/entry.py
RUN chmod 0444 /opt/codejury/entry.py
USER 65532:65532
WORKDIR /tmp
ENTRYPOINT ["python", "/opt/codejury/entry.py"]
