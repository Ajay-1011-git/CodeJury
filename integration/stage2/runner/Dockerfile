# Same pinned Python base as both owner runners. No candidate source enters the image.
FROM python@sha256:e41613d42d4891e4930f79523f93f81bbc7632584ec65e36ab055f41a800b41e
RUN useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin runner
COPY entry.py /opt/codejury/entry.py
RUN chmod 0444 /opt/codejury/entry.py
USER 65532:65532
WORKDIR /tmp
# The runner supplies its fixed command after the image. CMD permits trusted isolation
# probes to substitute python -c without retaining a conflicting image ENTRYPOINT.
CMD ["python", "/opt/codejury/entry.py"]
