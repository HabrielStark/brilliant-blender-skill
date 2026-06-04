"""Release-readiness status document checks."""
from pathlib import Path


def test_status_tracks_current_release_gates():
    status = Path("STATUS.md").read_text(encoding="utf-8")

    required_phrases = [
        'pytest tests -q',
        'ruff check blender_cinematic mcp_server scripts tests',
        'python scripts\\audit_repo_invariants.py',
        'bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon',
        'python -m pip_audit .',
        'python -m build --sdist --wheel',
        'python -m twine check',
        'python scripts\\validate_skill.py',
        'python -m benchmarks.runners.run_benchmarks --baseline --out artifacts\\visual_acceptance_artfix_v28',
        'python benchmarks\\runners\\run_benchmarks.py --baseline --out artifacts\\visual_acceptance_final_after_docs',
        'python scripts\\visual_review_pack.py --out artifacts\\visual_review_pack_artfix_v28 --allow-unreviewed',
        'python scripts\\blind_visual_eval.py --out artifacts\\blind_visual_eval_artfix_v28 --seed 20260604 --allow-unreviewed',
        'python scripts\\visual_review_pack.py --out artifacts\\visual_review_pack_artfix_v28_reviewed --human-review artifacts\\visual_review_pack_artfix_v28\\codex_visual_review.json',
        'python scripts\\blind_visual_eval.py --out artifacts\\blind_visual_eval_artfix_v28_reviewed --seed 20260604 --human-review artifacts\\blind_visual_eval_artfix_v28\\codex_blind_review.json',
        'python scripts\\assert_visual_acceptance.py --visual-review artifacts\\visual_review_pack_artfix_v28_reviewed\\visual_review_pack.json --blind-eval artifacts\\blind_visual_eval_artfix_v28_reviewed\\blind_visual_eval.json',
        'python scripts\\run_prompt_scenarios.py --render --out artifacts\\prompt_scenarios_final_render',
        'python scripts\\run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts\\live_watch_final_after_docs',
        'python scripts\\run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts\\live_reference_match_final_after_docs',
        'python scripts\\run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts\\live_shader_texture_final_after_docs',
        'python scripts\\run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts\\live_turntable_animation_final_after_docs',
        'python scripts\\package_skill.py --out dist',
        'python scripts\\generate_sbom.py --out dist',
        'npm pack --pack-destination dist',
        'python scripts\\assert_release_artifacts.py --dist dist',
        'npm install --prefix C:\\tmp\\bbs-npm-smoke-prefix -g dist\\brilliant-blender-skill-0.1.0.tgz',
        'C:\\tmp\\bbs-npm-smoke-prefix\\brilliant-blender-skill.cmd doctor',
        'python C:\\tmp\\bbs-npm-smoke-install\\scripts\\validate_skill.py',
        'npm test',
        'npm run e2e',
        'npm audit --package-lock-only --audit-level=high',
        'npm pack --dry-run',
        'nvidia-ml-py',
        'THIRD_PARTY_NOTICES',
        'primary Blender-taste acceptance gate',
        'codex_visual_review_agent_gpt5_2026_06_04_v28',
        'min_distinct_named_part_objects',
        'all 14 adversarial slop baselines score 79 and fail',
        '4/4 prompt fixtures pass static anti-slop recipe contracts',
        'Live-agent forward-test gates: met locally',
        'watch_live_agent_forward_v6_20260604',
        'reference_match_live_agent_forward_v12_20260604',
        'shader_texture_live_agent_forward_v6_20260604',
        'turntable_animation_live_agent_forward_v2_20260604',
        'all four prompt-scenario families',
        'NPM/GitHub install path: met locally',
        'brilliant-blender-skill',
        'bcas-validate-glb',
    ]
    for phrase in required_phrases:
        assert phrase in status

    stale_claims = [
        'No real browser run',
        'Playwright render" of a live',
        'was not executed',
        '127 passed',
        '2026-05-31',
        'pynvml==',
        '3/3 prompt fixtures',
        'Current v37 prompt scenarios are prompt fixtures',
    ]
    for phrase in stale_claims:
        assert phrase not in status
