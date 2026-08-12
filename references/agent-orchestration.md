# Agent orchestration playbook

Use sub-agents to create independent evidence, not to multiply uncoordinated
edits. The orchestrator remains responsible for the goal, file ownership,
integration, final claims, and stop decision.

## When to delegate

Delegate only a bounded branch with a different hypothesis or evidence surface:

| Role | Mission | Allowed write scope | Required evidence |
|---|---|---|---|
| Scene planner | Translate the brief into subject anatomy, composition, and a recipe plan | None (read-only) | plan plus cited manifest/recipe constraints |
| Blender technical reviewer | Check schema, collections, transforms, modifiers, animation, and render limits | None unless explicitly assigned a disjoint addon file | exact paths, failed rules, and reproduction command |
| Visual reviewer | Inspect actual preview pixels and identify composition, lighting, material, detail, and continuity defects | None; review artifacts only | image paths, five visual defects, up to three technical defects |
| Web/export reviewer | Validate GLB, textures, camera paths, generated web code, and desktop/mobile behavior | Disjoint web test or fixture files only | validator output, console/network status, screenshots |
| Security reviewer | Trace workspace, subprocess, bridge, input, and package boundaries | None | threat, path, severity, and negative-test recommendation |

Do not spawn agents for a one-file edit, a repeated identical review, or a
check whose result cannot change the next action. If sub-agents are unavailable,
run the same roles sequentially yourself and record that limitation.

## Dispatch protocol

1. Give each agent the user-facing request, the relevant raw artifacts, and one
   bounded question. Do not provide the suspected bug, intended fix, expected
   score, or another agent's conclusion.
2. Assign non-overlapping ownership. Read-only reviewers must not edit the
   repository. Implementers must name their files and must not revert other
   agents' edits.
3. Require an evidence-first response:

   ```text
   Mission:
   Hypothesis tested:
   Files inspected/changed:
   Commands or visual checks:
   Result:
   Remaining uncertainty:
   Recommended next action:
   ```

4. The orchestrator reconciles reports against the current worktree and reruns
   the cheapest decisive check. A sub-agent report is evidence, not approval.
5. Keep only changes that satisfy the goal contract and pass the same tests as
   local work. Never merge a convenient claim without the underlying artifact.

## Conflict and safety rules

- Never let two agents edit the same file at the same time.
- Never allow an agent to add arbitrary Blender Python to the normal recipe path.
- Preserve `WorkspaceResolver`, argument-array subprocesses, pinned dependencies,
  and the core/add-on `bpy` boundary.
- Treat an unavailable Blender executable, GPU, browser, or human reviewer as a
  limitation to report, not as a passing result.
- Stop delegation when reports converge, no new hypothesis exists, or the
  remaining work is a single deterministic fix owned by the orchestrator.
