# syntax=docker/dockerfile:1.7
# The board page. Python standard library only. The repository mounts read only at
# /src/repo and the harness package inside it runs the server. The SQLite cache lives
# in /data, because the repository is read only and the cache is not the truth.
#
# Base pinned by digest (python:3.11-slim, 2026-09-04):
FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534
RUN apt-get update && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/* \
 && git config --global --add safe.directory /src/repo
ENV PYTHONPATH=/src/repo PYTHONUNBUFFERED=1
WORKDIR /src/repo
EXPOSE 8412
CMD ["python3", "-m", "harness", "--root", "/src/repo", "dashboard", "serve", "--host", "0.0.0.0", "--port", "8412", "--db", "/data/board.sqlite", "--rebuild-every", "300"]
