# Goal, checkpoint, and evidence contract

Every run starts with a short goal contract and ends with a requirement-to-
evidence matrix. This prevents a polished description from being mistaken for
a rendered, inspected, or exportable result.

## Goal contract

Write these fields before creating Blender data:

```json
{
  "goal_id": "stable-task-id",
  "outcome": "one sentence describing the requested artifact",
  "request_class": "still|animation|web_asset|interactive_web|reference_match|scene_repair|benchmark",
  "inputs": ["brief", "reference image path", "existing blend path"],
  "deliverables": ["blend", "preview", "report"],
  "non_goals": ["unrequested redesign", "paid cloud rendering"],
  "acceptance_gates": ["active camera", "visual score >= 80"],
  "evidence_root": "artifacts/<goal_id>"
}
```

Do not invent missing inputs. Record assumptions and mark them as uncertainty.
For a supplied reference image, inspect the pixels before writing a recipe and
record the observed layout in the manifest metadata.

## Checkpoint ledger

Append one JSON object per checkpoint to `checkpoint_ledger.jsonl` (or an
equivalent durable report) with:

```json
{
  "checkpoint": "CP-03",
  "objective": "prove the hero reads in the active camera",
  "hypothesis": "the crop hides the crown and lower strap",
  "files_changed": ["..."],
  "commands": ["python scripts/scene_lint.py ..."],
  "artifacts": ["iterations/iter_02_preview.png", "iterations/iter_02_inspect.json"],
  "result": "fail|pass|blocked",
  "next_hypothesis": "pull the camera back and recenter look_at",
  "stop_status": "continue|done|blocked|churn"
}
```

Each checkpoint must have an observable output and a verification method. Do
not rerun a heavy benchmark, render, or browser suite unless code, config,
dependencies, scene state, viewport, or external state changed.

## Claim levels

Use the strongest claim supported by artifacts:

| Level | What it proves | Allowed wording |
|---|---|---|
| `static` | schema/recipe/docs inspection only | “static contract passes” |
| `local_runtime` | Blender/add-on or Node validator ran locally | “local runtime check passes” |
| `visual_inspected` | actual pixels were inspected with a rubric | “preview inspected; defects recorded” |
| `human_reviewed` | blind or human review JSON covers the artifact | “reviewed visual signoff” |
| `live_external` | a named external deployment/service was checked | “live check passes” |

Never upgrade a claim level because a score is high, a file is named `final`,
or a command was written in a report. Missing Blender, GPU, browser, reference
pixels, or human review must remain explicit limitations.

## Final evidence matrix

Before release, map every required gate to an artifact, command, or screenshot.
Unexplained `partial` or `unknown` entries are failures, not implicit passes.
The final report must list artifact paths, measured scores, failures repaired,
unresolved limitations, and the highest claim level actually earned.

The latest checkpoint controls current status. Historical best scores remain
diagnostic only: a later failed iteration, missing preview, failed final render,
or unrun web validation must force a non-passing report.
