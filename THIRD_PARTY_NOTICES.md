# Third-Party Notices

This project is released under the MIT license. The project also depends on
third-party open-source packages listed below. This notice is a release
readiness aid and does not replace the license files shipped by each package
manager artifact.

## Python Runtime Dependencies

| Package | Pinned version | License metadata |
|---|---:|---|
| pydantic | 2.12.5 | MIT |
| psutil | 6.1.1 | BSD-3-Clause |
| Pillow | 12.2.0 | MIT-CMU |
| numpy | 1.26.4 | BSD |
| mcp | 1.27.2 | MIT |

## Python Optional/Development Dependencies

| Package | Pinned version | License metadata |
|---|---:|---|
| scikit-image | 0.26.0 | BSD |
| nvidia-ml-py | 13.610.43 | NVIDIA NVML Python bindings; see package metadata |
| pytest | 9.0.3 | MIT |
| pytest-cov | 7.1.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| pip-audit | 2.10.0 | Apache-2.0 |
| build | 1.5.0 | MIT |
| twine | 6.2.0 | Apache-2.0 |
| cyclonedx-bom | 7.3.0 | Apache-2.0 |
| ruff | 0.15.15 | MIT |
| bandit | 1.9.4 | Apache-2.0 |

## Node Dependencies

| Package | Pinned version | License metadata |
|---|---:|---|
| @gltf-transform/core | 4.1.1 | MIT |
| @gltf-transform/extensions | 4.1.1 | MIT |
| @gltf-transform/functions | 4.1.1 | MIT |
| @playwright/test | 1.60.0 | Apache-2.0 |
| @types/node | 22.10.2 | MIT |
| three | 0.160.1 | MIT |
| typescript | 5.7.2 | Apache-2.0 |

## Node Transitive Dependencies Observed In The Lockfile

| Package | Pinned version | License metadata |
|---|---:|---|
| @img/sharp-win32-x64 | 0.33.5 | Apache-2.0 AND LGPL-3.0-or-later |
| @types/ndarray | 1.0.14 | MIT |
| color | 4.2.3 | MIT |
| color-convert | 2.0.1 | MIT |
| color-name | 1.1.4 | MIT |
| color-string | 1.9.1 | MIT |
| cwise-compiler | 1.1.3 | MIT |
| detect-libc | 2.1.2 | Apache-2.0 |
| iota-array | 1.0.0 | MIT |
| is-arrayish | 0.3.4 | MIT |
| is-buffer | 1.1.6 | MIT |
| ktx-parse | 0.7.1 | MIT |
| ndarray | 1.0.19 | MIT |
| ndarray-lanczos | 0.3.0 | MIT |
| ndarray-ops | 1.2.2 | MIT |
| ndarray-pixels | 4.1.0 | MIT |
| playwright | 1.60.0 | Apache-2.0 |
| playwright-core | 1.60.0 | Apache-2.0 |
| property-graph | 3.0.0 | MIT |
| semver | 7.8.1 | ISC |
| sharp | 0.33.5 | Apache-2.0 |
| simple-swizzle | 0.2.4 | MIT |
| undici-types | 6.20.0 | MIT |
| uniq | 1.0.1 | MIT |

## Notes For Redistributors

- Keep dependency versions pinned and regenerate this file when changing
  `pyproject.toml`, `package.json`, or `package-lock.json`.
- The generated SBOMs in `dist/` provide machine-readable dependency inventory.
- The package manager artifacts may include additional platform-specific optional
  packages. Review the generated SBOMs and lockfiles for the target platform.
