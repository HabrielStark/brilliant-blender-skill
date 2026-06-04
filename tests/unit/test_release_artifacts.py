"""Release artifact assertion tests."""
import hashlib
import io
import tarfile
import zipfile

import pytest

from scripts import assert_release_artifacts


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _add_tar_file(tar, name, text="x"):
    data = text.encode("utf-8")
    info = tarfile.TarInfo(name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _write_checksums(path, names):
    lines = []
    for name in names:
        artifact = path.parent / name
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}\n")
    path.write_text("".join(lines), encoding="utf-8")


def _write_minimal_artifacts(tmp_path, monkeypatch):
    monkeypatch.setattr(assert_release_artifacts, "ROOT", tmp_path)
    _write(tmp_path / "web" / "dist" / "web_validate_asset.js", "#!/usr/bin/env node\n")

    dist = tmp_path / "dist"
    dist.mkdir()
    with tarfile.open(dist / assert_release_artifacts.SDIST, "w:gz") as tar:
        for name in assert_release_artifacts.REQUIRED_SDIST:
            _add_tar_file(tar, f"pkg/{name}")

    with zipfile.ZipFile(dist / assert_release_artifacts.SKILL_ZIP, "w") as zf:
        for name in assert_release_artifacts.REQUIRED_SKILL:
            zf.writestr(name, "x")

    with zipfile.ZipFile(dist / assert_release_artifacts.ADDON_ZIP, "w") as zf:
        for name in assert_release_artifacts.REQUIRED_ADDON:
            zf.writestr(name, "x")

    with tarfile.open(dist / assert_release_artifacts.NPM_TARBALL, "w:gz") as tar:
        for name in assert_release_artifacts.REQUIRED_NPM_TARBALL:
            _add_tar_file(tar, f"package/{name}")

    with zipfile.ZipFile(dist / assert_release_artifacts.WHEEL, "w") as zf:
        zf.writestr(
            "blender_cinematic_agent_skill-0.1.0.dist-info/METADATA",
            'Requires-Dist: nvidia-ml-py==13.610.43; extra == "nvidia"\n',
        )

    _write(dist / "python-sbom.cdx.json", "{}")
    _write(dist / "npm-sbom.cdx.json", "{}")
    _write_checksums(dist / assert_release_artifacts.CHECKSUMS, [
        assert_release_artifacts.SKILL_ZIP,
        assert_release_artifacts.ADDON_ZIP,
    ])
    _write_checksums(dist / assert_release_artifacts.SBOM_CHECKSUMS, [
        "python-sbom.cdx.json",
        "npm-sbom.cdx.json",
    ])
    return dist


def test_assert_release_artifacts_passes_for_complete_artifacts(tmp_path, monkeypatch):
    dist = _write_minimal_artifacts(tmp_path, monkeypatch)
    assert_release_artifacts.assert_release_artifacts(dist)


def test_assert_release_artifacts_fails_for_missing_notice(tmp_path, monkeypatch):
    dist = _write_minimal_artifacts(tmp_path, monkeypatch)
    sdist = dist / assert_release_artifacts.SDIST
    with tarfile.open(sdist, "w:gz") as tar:
        for name in assert_release_artifacts.REQUIRED_SDIST - {"THIRD_PARTY_NOTICES.md"}:
            _add_tar_file(tar, f"pkg/{name}")

    with pytest.raises(AssertionError, match="THIRD_PARTY_NOTICES"):
        assert_release_artifacts.assert_release_artifacts(dist)


def test_assert_release_artifacts_fails_for_missing_checksums(tmp_path, monkeypatch):
    dist = _write_minimal_artifacts(tmp_path, monkeypatch)
    (dist / assert_release_artifacts.CHECKSUMS).unlink()
    with pytest.raises(AssertionError, match="missing artifact"):
        assert_release_artifacts.assert_release_artifacts(dist)


def test_assert_release_artifacts_fails_for_corrupt_checksums(tmp_path, monkeypatch):
    dist = _write_minimal_artifacts(tmp_path, monkeypatch)
    (dist / assert_release_artifacts.SBOM_CHECKSUMS).write_text(
        f"{'0' * 64}  python-sbom.cdx.json\n{'0' * 64}  npm-sbom.cdx.json\n",
        encoding="utf-8",
    )
    with pytest.raises(AssertionError, match="checksum mismatch"):
        assert_release_artifacts.assert_release_artifacts(dist)
