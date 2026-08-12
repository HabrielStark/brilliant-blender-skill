"""Tests for the deterministic skill-contract self-audit."""
from pathlib import Path

from scripts.skill_self_audit import audit_skill

ROOT = Path(__file__).resolve().parents[2]


def test_current_skill_contract_passes():
    report = audit_skill(ROOT)
    assert report["status"] == "PASS"
    assert report["errors"] == []
    assert report["required_sections"] >= 5
    assert report["required_references"] >= 12


def test_skill_contract_rejects_missing_section_and_reference(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: test\n---\n"
        "## Goal contract (write before scene work)\n",
        encoding="utf-8",
    )
    (tmp_path / "references").mkdir()

    report = audit_skill(tmp_path)

    assert report["status"] == "FAIL"
    assert any("Sub-agents" in error for error in report["errors"])
    assert any("missing reference" in error for error in report["errors"])


def test_skill_contract_rejects_missing_operational_command(tmp_path):
    source = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    source = source.replace("scripts/report_writer.py <dir>", "report-writer-not-present <dir>")
    (tmp_path / "SKILL.md").write_text(source, encoding="utf-8")
    references = tmp_path / "references"
    references.mkdir()
    for path in (ROOT / "references").glob("*.md"):
        (references / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    report = audit_skill(tmp_path)

    assert report["status"] == "FAIL"
    assert any("report_writer.py" in error for error in report["errors"])
