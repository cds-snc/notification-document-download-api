# Image Remediation: eMudhra CA distrust & CVE-2026-111497 (Brotli)

Date: 2026-10-29

## Scope

| Location | Image reference |
|---|---|
| `ci/Dockerfile` (production; built by `docker.yaml`, `dev_branch_build_push_images.yml`) | single-stage `FROM` |
| `.devcontainer/Dockerfile` (built via `.devcontainer/docker-compose.yml`) | single-stage `FROM` |
| `.github/workflows/*` | No `container:`/`services:`/`docker://` references; workflows only build `ci/Dockerfile` |

## Changes

| File | Before | After |
|---|---|---|
| `ci/Dockerfile` | `python:3.12-alpine3.20@sha256:5049c050…83bf98` | `python:3.12-alpine3.24@sha256:5789aa194f757888f41fa3d48e14b6feaa1b57c0af0b56fcb1372d6474d3bff0`; removed the now-no-op `sed` distrust of emSign ECC G3 / Comodo AAA (neither cert is in `ca-certificates-20261020`) |
| `.devcontainer/Dockerfile` | `mcr.microsoft.com/vscode/devcontainers/python:1-3.12` (floating) | `mcr.microsoft.com/vscode/devcontainers/python:1-3.12@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39` + `apt-get install --only-upgrade libbrotli1 libbrotli-dev` + drop expired Yarn apt source; removed `sed` distrust (now handled by `ca-certificates 20250419~deb12u2` from bookworm-security) |

### Deviations from strict flavor-pinning (approved)

- **ci**: `python:3.12-alpine3.20` was last published 2025-05-08 (Alpine 3.20 EOL). Its latest digest still trusted eMudhra (HTTP 200)
  and shipped vulnerable `brotli-libs-1.1.0-r2`. Moved to Alpine 3.24 (same distro, same Python 3.12 line).
- **devcontainer**: upstream image is frozen (last built 2025-07-10; `1-3.12-bookworm` resolves to the same digest). The raw base
  fails the eMudhra test (HTTP 200) and has vulnerable `libbrotli1 1.0.9-2+b6`. The `ca-certificates 20250419~deb12u2` package from bookworm-security (installed at build time) and the explicit
  `libbrotli1` upgrade from bookworm-security fix the built image. The base image's Yarn apt key had expired, which made `apt-get update`
  fail (already broken on `main`), so the Yarn apt source is removed.

## Validation results

Test: `curl -sS -o /dev/null -w "HTTP %{http_code}\n" https://dv-g3b-emudhra.we-have-a-problem.com/`
(chain: `EM DV TLS CA - G3B` → `emSign Root TLS CA - G3` → `emSign ECC Root CA - G3`)

| Image | eMudhra curl | Brotli | Other |
|---|---|---|---|
| Old ci base (`alpine3.20` latest) | ❌ HTTP 200, exit 0 | ❌ `brotli-libs-1.1.0-r2` | Python 3.12.10 |
| **New ci base** (`alpine3.24@sha256:5789aa19…`) raw | ✅ HTTP 000, exit 60 (`unable to get local issuer certificate`) | ✅ `brotli-libs-1.2.1-r0` (Alpine secfixes: CVE-2026-111497) | Alpine 3.24.3, Python 3.12.16, `ca-certificates-20261020-r0` (emSign ECC G3 removed) |
| **Built `ci/Dockerfile`** | ✅ HTTP 000, exit 60 | ✅ `brotli-libs-1.2.1-r0` | 201/201 tests pass in image |
| Devcontainer base (`@sha256:7876580d…`) raw | ❌ HTTP 200, exit 0 | ❌ `libbrotli1 1.0.9-2+b6` | No Node in base |
| **Built `.devcontainer/Dockerfile`** | ✅ HTTP 000, exit 60 | ✅ `libbrotli1 1.0.9-2+deb12u1` (DLA-4855-1) | Python 3.12.11 |

Notes:
- Local tests were run on arm64. The pinned digests are multi-arch OCI indexes and include amd64.
- The devcontainer installs Debian's `nodejs 18.20.4+dfsg-1~deb12u3`. This version is below the 22.23.4 / 24.22.1 / 26.12.1 floors, and Debian still tracks it as
  vulnerable. It dynamically links the patched system `libbrotli` (confirmed with `ldd`). This affects the dev environment only. **Follow-up:** remove `nodejs`/`npm`
  from the devcontainer if unused, or install Node ≥ 22.23.4 from NodeSource.
- **Follow-up:** move the devcontainer to the maintained `mcr.microsoft.com/devcontainers/python` image line once it is rebuilt with these fixes.
