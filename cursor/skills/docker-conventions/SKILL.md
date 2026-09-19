---
name: docker-conventions
description: Implements and reviews Dockerfiles and Compose stacks. Use for image builds and local Compose — not for Kubernetes, Helm, or CI pipelines.
---

# Docker conventions

Default: Dockerfile + Compose for local/dev and image build.

- Start Dockerfiles with `# syntax=docker/dockerfile:1`. Prefer multi-stage builds.
- Final stage runs as a non-root `USER`. Do not run the app as root.
- Do not ship `:latest` for production tags. Pin a version or digest.
- Add `.dockerignore`. Copy lockfiles before source so dependency layers cache.
- Compose is for local/dev dependency stacks, not a Kubernetes stand-in.
- Do not run `docker system prune -af`.

## Lint

If the repo already has hadolint configured, run it. If bootstrapping Dockerfiles, add hadolint with tool defaults (no extra `.hadolint.yaml` unless the repo already has one).
