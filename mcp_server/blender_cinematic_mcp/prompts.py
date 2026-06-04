"""MCP prompts (SRS 12.6): reusable workflow templates.

Each prompt expands into a strict instruction block reminding the agent of the
mandatory loop for a given scenario. Arguments: brief, output mode, target
runtime, quality profile, max iterations.
"""
from __future__ import annotations

from .security import ServerContext

_COMMON = (
    "Follow SKILL.md strictly. Classify -> manifest -> preflight -> budget -> plan -> "
    "blockout -> preview -> critique -> refine -> final (only after hard checks pass) -> "
    "validate -> report. Never claim done without artifact paths and an inspected preview."
)


def _block(title: str, body: str, brief: str, profile: str, max_iter: int, runtime: str = "") -> str:
    rt = f"\nTarget runtime: {runtime}." if runtime else ""
    return (f"# {title}\n\nBrief: {brief}\nQuality profile: {profile}\nMax iterations: {max_iter}.{rt}\n\n"
            f"{body}\n\n{_COMMON}")


def register_prompts(mcp, ctx: ServerContext) -> None:
    @mcp.prompt(name="cinematic_scene_workflow")
    def cinematic_scene_workflow(brief: str, quality_profile: str = "auto", max_iterations: int = 5) -> str:
        return _block("Cinematic Scene", "Build a still or short cinematic shot with intentional camera, "
                      "lighting rig, PBR materials and depth. Score >= 80 before final.",
                      brief, quality_profile, max_iterations)

    @mcp.prompt(name="reference_match_workflow")
    def reference_match_workflow(brief: str, quality_profile: str = "auto", max_iterations: int = 8) -> str:
        return _block("Reference Match", "Extract subject/palette/camera/lighting/materials from the reference, "
                      "build to match, and compare with SSIM + palette + checklist each iteration.",
                      brief, quality_profile, max_iterations)

    @mcp.prompt(name="web_3d_hero_workflow")
    def web_3d_hero_workflow(brief: str, quality_profile: str = "auto", max_iterations: int = 10,
                             target_runtime: str = "react-three-fiber") -> str:
        return _block("Web 3D Hero", "Build, export a budgeted GLB, validate it locally, generate the "
                      "viewer/component + camera_path.json, and capture desktop+mobile screenshots.",
                      brief, quality_profile, max_iterations, target_runtime)

    @mcp.prompt(name="safe_laptop_workflow")
    def safe_laptop_workflow(brief: str, quality_profile: str = "safe_laptop", max_iterations: int = 3) -> str:
        return _block("Safe Laptop", "Force safe_laptop: EEVEE, no volumetrics, low particle counts, "
                      "<=1920px final. Explain every fallback in the report.",
                      brief, quality_profile, max_iterations)

    @mcp.prompt(name="scene_repair_workflow")
    def scene_repair_workflow(brief: str, quality_profile: str = "auto", max_iterations: int = 5) -> str:
        return _block("Scene Repair", "Inspect + lint the broken scene, fix camera/lights/names/materials, "
                      "and produce a before/after report.",
                      brief, quality_profile, max_iterations)

    @mcp.prompt(name="benchmark_run_workflow")
    def benchmark_run_workflow(brief: str, quality_profile: str = "balanced", max_iterations: int = 10) -> str:
        return _block("Benchmark Run", "Run the benchmark task end-to-end and emit the structured benchmark "
                      "result (pass, visual_score, technical_score, runtime, iterations, artifacts).",
                      brief, quality_profile, max_iterations)
