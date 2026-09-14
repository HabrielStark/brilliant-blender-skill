# Agent orchestration playbook

Use sub-agents to create independent evidence, not to multiply uncoordinated
edits. The orchestrator remains responsible for the goal, file ownership,
integration, final claims, and stop decision.

## The builder -> verifier loop (the core protocol)

Metrics prove a render is *not broken*. They cannot prove it looks like the
brief — that takes an agent that can actually look at pixels. So the done-signal
is never the builder's own claim:

1. **Builder** iterates apply -> render -> critique until no fail-severity
   diagnoses remain, then claims done.
2. **Visual verifier** — a *different* agent session — receives ONLY the brief,
   the `required_parts` ledger, and the render path (plus the reference image
   when one exists). Not the builder's reasoning, not its claimed fixes — fresh
   eyes only. It opens the image itself and answers:
   - For every element in the ledger: is it present, identifiable, and does it
     read as *what it is* (a flower reads as a flower, not as a blob)?
   - Does the composition match the brief's intent (mood, framing, hierarchy)?
   - If a reference exists: which regions diverge most, and why?
   - Verdict: `PASS` or a numbered defect list ordered by visual impact.
3. A defect list routes back to the builder as new work. `PASS` from the
   verifier plus zero fail diagnoses is the only valid done-state.

The verifier must never be told the score or the builder's interpretation —
anchoring it to the builder's story defeats the point. If sub-agents are
unavailable, the orchestrator plays verifier on a fresh read of the render and
records that limitation in the report.

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
