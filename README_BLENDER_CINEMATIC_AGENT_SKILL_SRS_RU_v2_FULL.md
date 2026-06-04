# Blender Cinematic Agent Skill — SRS / техническое задание

**Версия:** 0.1 draft
**Дата:** 2026-05-30
**Рабочее имя репозитория:** `blender-cinematic-agent-skill`
**Цель:** создать бесплатный open-source Agent Skill + опциональный MCP-сервер/Blender add-on, который заставляет AI-агента делать не просто случайные `bpy`-скрипты, а полноценный 3D-пайплайн: планирование сцены, проверка железа, blockout, превью-рендер, жесткая самооценка, итерации, финальный рендер, экспорт в GLB/web и отчет с доказательствами.

---

## 0. Инструкция для агента-разработчика

Ты — кодовый агент, который должен реализовать этот репозиторий. Считай этот файл главным SRS/README. Не делай игрушечный wrapper вокруг Blender. Нужно сделать рабочую систему, которая обучает агента вести себя как аккуратный 3D technical artist: сначала понять задачу, проверить компьютер, построить композицию, сделать превью, честно раскритиковать результат, исправить, проверить экспорт и только потом говорить, что работа готова.

Проект должен быть бесплатным и open-source. В дефолтном режиме нельзя требовать платные API, облачные рендеры, закрытые ассеты или сторонние коммерческие сервисы. Опциональные cloud/API-адаптеры можно добавить только как выключенные по умолчанию расширения, но тесты и базовый workflow должны работать локально.

Финальный продукт — не просто MCP. Это **skill-driven Blender production pipeline**:

1. `SKILL.md` — короткие, строгие инструкции для AI-агента.
2. `references/` — отдельные playbook-файлы: камера, свет, материалы, web export, визуальная критика.
3. `scripts/` — локальные helpers: preflight железа, запуск Blender, scene lint, visual QA, GLB validation.
4. `mcp_server/` — безопасные structured MCP tools.
5. `addon/` — Blender add-on, который выполняет валидированные операции внутри Blender.
6. `tests/` и `benchmarks/` — проверка, что skill реально улучшает результат, а не просто красиво описан.

Запрещено заявлять “готово”, “4K”, “cinematic”, “web-ready”, если нет файлов, логов, превью и validation report.

---

## 1. Исследовательская база и позиционирование

### 1.1 Что уже существует

Актуальные Blender MCP-проекты обычно устроены так: AI host/agent подключается к MCP server по stdio; MCP server пересылает команды в Blender add-on через локальный socket; add-on внутри Blender использует `bpy`. Такие решения уже умеют создавать/менять объекты, инспектировать сцену, делать screenshots, рендерить, экспортировать и иногда выполнять Python-код.

Этот проект не должен просто копировать существующие MCP. Его ценность — слой выше: художественный и технический workflow, который заставляет агента использовать Blender осмысленно.

Использованные ориентиры:

- Official MCP specification: https://modelcontextprotocol.io/specification/2025-06-18
- MCP Tools: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- MCP Resources: https://modelcontextprotocol.io/specification/2025-06-18/server/resources
- MCP Prompts: https://modelcontextprotocol.io/specification/2025-06-18/server/prompts
- MCP security guidance: https://modelcontextprotocol.io/docs/tutorials/security/security_best_practices
- Blender Lab MCP page: https://www.blender.org/lab/mcp-server/
- Blender Lab related repo: https://github.com/bpype/blender_mcp
- Community Blender MCP: https://github.com/ahujasid/blender-mcp
- Community Blender MCP server with tests/namespaces: https://github.com/djeada/blender-mcp-server
- Agent Skills spec: https://agentskills.io/specification
- OpenAI Codex Agent Skills docs: https://developers.openai.com/codex/skills
- Blender Python API: https://docs.blender.org/api/current/
- Blender Manual: https://docs.blender.org/manual/en/latest/
- glTF 2.0 spec: https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- three.js GLTFLoader: https://threejs.org/docs/pages/GLTFLoader.html
- three.js AnimationMixer: https://threejs.org/docs/pages/AnimationMixer.html
- Drei ScrollControls: https://drei.docs.pmnd.rs/controls/scroll-controls
- GSAP ScrollTrigger: https://gsap.com/docs/v3/Plugins/ScrollTrigger/
- glTF Transform CLI: https://gltf-transform.dev/cli
- Google Draco: https://github.com/google/draco
- meshoptimizer/gltfpack: https://meshoptimizer.org/gltf/
- scikit-image SSIM: https://scikit-image.org/docs/stable/api/skimage.metrics.html
- LPIPS perceptual metric: https://github.com/richzhang/PerceptualSimilarity
- psutil: https://psutil.readthedocs.io/
- NVIDIA NVML: https://developer.nvidia.com/management-library-nvml

### 1.2 Политика источников

При разработке использовать официальную документацию первой. Если официальных документов недостаточно — GitHub репозитории maintainers, стандарты, package docs, issue/discussion от крупных проектов. Не использовать российские или казахстанские сайты как источники документации, примеров, benchmark-reference или dependency guidance.

### 1.3 Главная проблема

AI-модели могут вызывать Blender tools, но часто проваливают сам production loop:

- делают набор случайных primitives вместо сцены;
- путают “рендер 3840×2160” с реальным 4K-quality;
- не планируют камеру, фокусное расстояние, композицию;
- не проверяют, что рендер не черный, не пустой, не шумный, не вне камеры;
- сразу запускают тяжелый Cycles на слабом ноутбуке;
- экспортируют GLB, который не грузится в web;
- не сохраняют итерации, логи, проверки и доказательства;
- говорят “красиво”, хотя не посмотрели на preview.

Этот проект должен исправить именно поведение агента, а не просто дать ему больше Blender-команд.

---

## 2. Видение продукта

Нужен Blender-аналог сильного frontend/design skill: один open-source skill, который можно поставить в Codex/Claude Code/Cursor/Gemini CLI/другого агента, и агент начнет делать Blender-сцены по дисциплинированному пайплайну.

Система должна заставлять агента:

1. Определить цель: still render, animation, website asset, interactive 3D section, product hero, stylized scene, reference-match scene, technical visualization, scene repair или benchmark.
2. Проверить железо и выбрать безопасный quality profile.
3. Сформировать scene manifest и scene plan до выполнения.
4. Создать чистый `.blend`: коллекции, камеры, свет, материалы, metadata.
5. Строить сцену по стадиям: blockout → preview → critique → refinement → final.
6. Делать screenshot/preview render после ключевых изменений.
7. Жестко оценивать результат: hard checks + rubric.
8. Итеративно улучшать сцену, но максимум 10 раз по умолчанию.
9. Корректно экспортировать в `.blend`, `.png`, видео/sequence, `.glb/.gltf`, web demo.
10. Писать final report: что создано, где файлы, какие настройки, что прошло/не прошло validation.

---

## 3. Non-goals

Проект не должен:

- обещать гарантированный photorealism на любой prompt;
- требовать paid APIs, cloud render farm, платные ассеты или закрытые SDK;
- скачивать ассеты с непроверенных сайтов;
- использовать нелицензированные ассеты;
- открывать опасный remote code execution endpoint;
- делать “execute arbitrary Python” основным публичным API;
- считать один visual metric доказательством красоты;
- бесконечно задавать уточняющие вопросы вместо выбора разумных defaults;
- выдавать только `.blend` без preview, logs и report;
- строить финальную архитектуру вокруг одной модели или одного клиента.

---

## 4. Пользователи

### 4.1 Основные

- Пользователи Codex, Claude Code, Cursor, Gemini CLI и других coding agents.
- Web-разработчики, которым нужны GLB/Three.js/R3F сцены.
- Дизайнеры/indie creators, которым нужны красивые 3D hero sections, product renders, animations.
- AI benchmarkers, которые тестируют модели в Blender.
- Open-source contributors, которые хотят стандартный test harness для agentic Blender workflow.

### 4.2 Вторичные

- 3D artists, которым нужны automation helpers.
- Учителя/студенты, изучающие procedural 3D.
- Разработчики интерактивных demo/portfolio sites.

---

## 5. Архитектура

```text
AI host / coding agent
        │
        │ loads skill metadata + SKILL.md
        ▼
Agent Skill package
  ├─ SKILL.md
  ├─ references/*.md
  ├─ scripts/*.py / *.ts
  └─ benchmarks/*.yaml
        │
        │ optional MCP tool calls
        ▼
MCP server process
  ├─ stdio transport to AI host
  ├─ structured tool schemas
  ├─ resources and prompts
  ├─ validation/sandbox layer
  └─ TCP/IPC client to Blender add-on
        │
        ▼
Blender add-on
  ├─ localhost-only listener by default
  ├─ executes validated operations
  ├─ captures viewport/render images
  ├─ inspects scene state
  └─ returns structured JSON
        │
        ▼
Artifacts
  ├─ .blend
  ├─ previews/*.png
  ├─ renders/*.png or video
  ├─ exports/*.glb / .gltf / .usd / .fbx
  ├─ web-demo/
  └─ reports/*.json / *.md
```

### 5.1 Почему нужны и Skill, и MCP

MCP дает tools. Skill дает порядок действий, художественные правила, defaults, self-critique и ограничения. Blender automation без workflow быстро превращается в “агент вызвал пару функций и решил, что сделал красиво”. Поэтому этот проект обязан поставлять оба слоя.

### 5.2 Структура репозитория

```text
blender-cinematic-agent-skill/
├── README.md
├── LICENSE
├── pyproject.toml
├── package.json
├── SKILL.md
├── AGENTS.md
├── references/
│   ├── camera-language.md
│   ├── composition-rubric.md
│   ├── lighting-materials.md
│   ├── procedural-modeling-recipes.md
│   ├── animation-camera-paths.md
│   ├── web-export-threejs-r3f.md
│   ├── hardware-quality-profiles.md
│   ├── visual-critique-rubric.md
│   └── failure-modes.md
├── scripts/
│   ├── preflight_hardware.py
│   ├── blender_locator.py
│   ├── scene_manifest.py
│   ├── run_blender_job.py
│   ├── render_budget.py
│   ├── visual_eval.py
│   ├── scene_lint.py
│   ├── export_glb.py
│   ├── web_validate_asset.ts
│   └── report_writer.py
├── mcp_server/
│   └── blender_cinematic_mcp/
│       ├── server.py
│       ├── tools/
│       ├── resources/
│       ├── prompts/
│       ├── schemas/
│       └── security.py
├── addon/
│   └── blender_cinematic_agent/
│       ├── __init__.py
│       ├── ops.py
│       ├── bridge.py
│       ├── validators.py
│       ├── scene_inspector.py
│       ├── renderer.py
│       └── preferences.py
├── benchmarks/
│   ├── tasks/
│   ├── golden/
│   ├── rubrics/
│   └── runners/
├── tests/
│   ├── unit/
│   ├── integration_blender/
│   ├── visual_regression/
│   ├── web_e2e/
│   └── security/
└── examples/
    ├── prompts/
    ├── outputs/
    └── web-demo/
```

---

## 6. Требования к Agent Skill

### 6.1 `SKILL.md` frontmatter

`SKILL.md` должен следовать Agent Skills format: folder + `SKILL.md` + YAML frontmatter + Markdown instructions.

```md
---
name: blender-cinematic-scene
license: MIT
compatibility: "Codex, Claude Code, Cursor, Gemini CLI, other Agent Skills-compatible coding agents. Requires local Blender for execution. No paid APIs required."
description: "Use when the user wants a Blender scene, cinematic 3D render, camera animation, GLB/glTF asset, 3D website hero, scroll-linked 3D effect, reference-based 3D scene, or automated Blender quality iteration. Do not use for ordinary 2D images."
---
```

### 6.2 Обязательные инструкции внутри skill

Skill обязан говорить агенту:

1. Сначала классифицируй задачу: `still`, `animation`, `web_asset`, `interactive_web`, `reference_match`, `scene_repair`, `benchmark`.
2. Перед тяжелым рендером всегда делай hardware preflight.
3. Если пользователь не указал качество — выбирай `auto`.
4. Не запускай финальный 4K сразу.
5. Сначала blockout, потом детали.
6. После серьезного изменения делай preview render/screenshot.
7. Смотри на реальный preview перед заявлением успеха.
8. Используй named cameras и timeline markers.
9. Используй collections: `CAMERAS`, `LIGHTS`, `SUBJECT`, `ENVIRONMENT`, `FX`, `HELPERS`, `EXPORT`.
10. Сохраняй iterations: `.blend`, preview images, eval JSON.
11. Не называй результат final/cinematic/web-ready без artifact paths.
12. Для web export всегда валидируй GLB в локальном viewer/test harness.

### 6.3 Progressive disclosure

`SKILL.md` должен быть компактным. Длинные детали — в `references/`:

- `camera-language.md` — lens, focal length, DOF, composition.
- `lighting-materials.md` — studio, cinematic, neon, product lighting, PBR rules.
- `animation-camera-paths.md` — turntable, flythrough, scroll camera.
- `web-export-threejs-r3f.md` — GLB, Three.js, R3F, ScrollControls, ScrollTrigger.
- `visual-critique-rubric.md` — hard fail, scoring, refinement logic.
- `hardware-quality-profiles.md` — safe_laptop/balanced/cinematic/ultra_4k.

### 6.4 Когда skill должен срабатывать

Examples:

- “Create a cinematic Blender scene.”
- “Make a 4K render of a futuristic engine.”
- “Export this Blender scene to GLB for my website.”
- “Build a Three.js scroll animation from a Blender camera path.”
- “Use this reference image to make a similar 3D scene.”
- “Test whether the generated Blender render is good.”
- “Fix this Blender scene so the camera and lights work.”

### 6.5 Когда skill не нужен

- Обычная 2D image generation.
- CSS-only animation без 3D.
- General Python scripting без Blender.
- CAD/manufacturing precision, если пользователь не просит именно Blender visualization.

---

## 7. Standard scene workflow

### 7.1 Основной loop

```text
1. Intake
2. Hardware/environment preflight
3. Scene manifest
4. Artistic/technical scene plan
5. Blender project initialization
6. Blockout
7. Preview capture
8. Harsh critique
9. Refinement pass
10. Medium-quality render
11. Second critique
12. Final render/export only if checks pass
13. Web/runtime validation if needed
14. Final report
```

### 7.2 Лимит итераций

Default maximum: **10 improvement iterations**.
Default minimum для нетривиальной сцены: **2 iterations**: blockout preview + refinement preview.

Остановиться раньше, если criteria pass. Остановиться с failure report, если 3 итерации подряд не улучшают score.

### 7.3 Обязательные artifacts

```text
artifacts/<task_id>/
├── scene_manifest.json
├── hardware_report.json
├── iterations/
│   ├── iter_01_scene.blend
│   ├── iter_01_preview.png
│   ├── iter_01_eval.json
│   └── ...
├── final/
│   ├── scene_final.blend
│   ├── render_final.png
│   ├── export_final.glb
│   ├── web_validation.json
│   └── final_report.md
└── logs/
```

---

## 8. Scene manifest

### 8.1 Пример `scene_manifest.json`

```json
{
  "schema_version": "0.1",
  "task_id": "2026-05-30_product_hero_watch_001",
  "brief": "Cinematic 3D product hero of a futuristic watch on a dark reflective surface",
  "output_mode": "web_asset",
  "quality_profile": "auto",
  "max_iterations": 10,
  "target": {
    "render_resolution": [3840, 2160],
    "preview_resolution": [1280, 720],
    "final_format": ["blend", "png", "glb"],
    "web_runtime": "react-three-fiber"
  },
  "style": {
    "mood": "premium, cinematic, sharp, high contrast",
    "palette": ["black", "cold blue", "brushed metal", "soft white highlights"],
    "camera_language": "macro product lens, shallow depth of field",
    "lighting_language": "large softbox key, rim light, subtle HDRI-style fill"
  },
  "constraints": {
    "no_paid_apis": true,
    "no_unlicensed_assets": true,
    "safe_hardware_budget": true,
    "max_glb_mb": 20,
    "max_texture_resolution": 2048
  },
  "references": [],
  "success_criteria": {
    "scene_not_empty": true,
    "subject_visible": true,
    "camera_framed": true,
    "lighting_valid": true,
    "web_export_loads": true,
    "visual_score_min": 80
  }
}
```

### 8.2 Валидация manifest

Manifest invalid, если:

- `brief` пустой;
- `output_mode` неизвестный;
- `max_iterations > 10`, если пользователь явно не override;
- 4K final requested, но hardware profile unsafe;
- web export без `max_glb_mb` или target runtime;
- reference image path вне workspace roots;
- output path выходит за sandbox.

---

## 9. Hardware preflight и quality profiles

### 9.1 Почему это обязательно

Skill не должен запускать тяжелый Cycles/volumetrics/high-poly/4K на слабом MacBook или обычном ноутбуке без проверки. Сначала preflight, потом render budget.

### 9.2 Что собрать

`preflight_hardware.py` должен собрать:

- OS и architecture;
- CPU info, physical/logical cores;
- total/available RAM;
- free disk space в project dir;
- GPU vendor/device, если доступно;
- VRAM total/available, если доступно;
- Blender executable path/version;
- доступные Cycles render devices: CUDA, OptiX, HIP, oneAPI, Metal, CPU, если поддерживается;
- thermal/battery status, если доступно;
- memory pressure;
- может ли Blender стартовать в background mode;
- проходит ли tiny test render.

Использовать `psutil` для CPU/RAM/disk/process monitoring. Для NVIDIA — NVML/pynvml или `nvidia-smi`, только если NVIDIA доступна. Для Apple Silicon — Blender device detection/Metal, не NVML.

### 9.3 Quality profiles

| Profile | Purpose | Preview | Final still | Default engine | Texture cap | Samples | Notes |
|---|---:|---:|---:|---|---:|---:|---|
| `safe_laptop` | слабое железо / integrated GPU / low RAM | 512–960 px wide | 1280–1920 px wide | EEVEE/Workbench preview, Cycles only if safe | 1024 | 32–96 | no heavy volumetrics, no 4K default |
| `balanced` | обычный laptop/desktop | 1280×720 | 1920×1080 / 2560×1440 | EEVEE preview, Cycles final | 2048 | 96–256 | denoise, moderate geometry |
| `cinematic` | strong desktop/GPU | 1920×1080 | 3840×2160 optional | Cycles GPU | 2048–4096 | 256–512 | richer lights/materials/DOF |
| `ultra_4k` | strong GPU + large RAM | 1920×1080 | 3840×2160+ | Cycles GPU | 4096 | 512–1024 | only after smaller preview passes |

### 9.4 Safety thresholds

Default safety rules:

- Не стартовать final render, если available RAM < 25% total или ниже configured minimum.
- Не стартовать 4K Cycles, если tiny test render failed.
- Не использовать textures выше profile cap.
- Не включать heavy volumetrics в `safe_laptop`.
- Не создавать unbounded particle counts.
- Abort/downshift, если memory usage выше threshold.
- Save `.blend` перед render/export.
- Preview first, final later.

### 9.5 Render budget report

```json
{
  "quality_profile": "balanced",
  "selected_engine": "CYCLES",
  "device": "GPU_OPTIX",
  "preview_resolution": [1280, 720],
  "final_resolution": [1920, 1080],
  "samples": 192,
  "texture_cap": 2048,
  "volumetrics_allowed": false,
  "reasoning": [
    "Detected 16GB RAM",
    "GPU available",
    "4K disabled because VRAM was below configured threshold"
  ]
}
```

---

## 10. Creative planning requirements

### 10.1 Явный scene plan

До Blender execution агент должен создать structured plan:

```json
{
  "subject": "futuristic watch",
  "composition": {
    "shot_type": "macro three-quarter hero shot",
    "focal_length_mm": 70,
    "camera_angle": "low front 3/4",
    "foreground": "soft reflective surface",
    "midground": "watch body and glowing dial",
    "background": "dark gradient with subtle geometry silhouettes"
  },
  "modeling": [
    "beveled watch case",
    "straps with repeated grooves",
    "dial with layered glass",
    "small screws and tick marks"
  ],
  "materials": [
    "brushed dark titanium",
    "emissive blue UI lines",
    "rough black rubber strap",
    "slightly tinted glass"
  ],
  "lighting": [
    "large soft area key",
    "thin blue rim light",
    "small specular cards"
  ],
  "animation": null,
  "export": {
    "glb": true,
    "web_runtime": "react-three-fiber"
  }
}
```

### 10.2 Visual/aesthetic rubric

Preview score = 100 points:

| Category | Points | Checks |
|---|---:|---|
| Composition | 20 | subject framed, readable silhouette, negative space, foreground/midground/background |
| Lighting | 15 | subject visible, intentional highlights/shadows, no black/white accident |
| Materials | 15 | PBR-like roughness/metalness, bevels catch light, no default gray scene |
| Geometry/detail | 15 | enough details, scale consistency, no random primitives, clean names |
| Camera/cinematic quality | 10 | focal length/DOF/perspective appropriate, final camera saved |
| Reference fidelity | 10 | matches reference/style/palette/silhouette/key elements |
| Technical correctness | 10 | no missing textures, active camera, no broken animation/export |
| Performance/export | 5 | fits profile, GLB size budget, loads in target viewer |

Pass threshold: 80.
Excellent benchmark: 90+.
Hard fail overrides score.

### 10.3 Hard-fail conditions

Preview/final automatically fails, если:

- render почти весь черный/белый без причины;
- subject outside camera frame;
- too few meaningful objects;
- default materials everywhere;
- no active camera;
- no meaningful light/world illumination;
- output file missing/empty;
- Blender reported render/export errors;
- GLB requested but local viewer cannot load it;
- animation requested but frame range/keyframes missing.

---

## 11. Blender scene structure

### 11.1 Collections

Every scene must include:

```text
CAMERAS
LIGHTS
SUBJECT
ENVIRONMENT
FX
HELPERS
EXPORT
```

Optional:

```text
RIGS
SIMULATION
ANNOTATIONS
PROXIES
REFERENCE
```

### 11.2 Object naming

Good:

```text
watch_case_beveled
watch_dial_glass
rim_light_blue_left
camera_hero_macro
background_arch_03
```

Bad:

```text
Cube.084
Cylinder.001
Untitled
object
```

`scene_lint.py` должен fail/warn, если финальная сцена забита default names.

### 11.3 Scene metadata

Store custom scene properties:

```json
{
  "blender_cinematic_skill_version": "0.1",
  "task_id": "...",
  "quality_profile": "balanced",
  "iteration": 4,
  "final_camera": "camera_hero_macro",
  "render_budget": "artifacts/.../render_budget.json",
  "source_manifest": "artifacts/.../scene_manifest.json"
}
```

### 11.4 Cameras

Each scene must have:

- active camera;
- semantic camera name;
- intentional focal length;
- sensible clipping;
- DOF only if useful;
- markers/path for animation/web scroll if needed;
- preview through final camera.

### 11.5 Lighting

Scene must use one lighting strategy:

- three-point lighting;
- environment/world lighting + practical lights;
- studio product lighting;
- stylized neon/emissive setup;
- technical visualization lighting.

Linter catches no-light/default-light scenes unless explicitly allowed.

### 11.6 Materials

Every important material must be named and intentional:

- base color;
- roughness;
- metallic where relevant;
- emission where relevant;
- glass/alpha/transmission only when needed;
- procedural noise/bump/normal for close surfaces.

For GLB/web, unsupported shader tricks must be baked/simplified or reported.

---

## 12. MCP server requirements

### 12.1 Transport

Default: MCP stdio transport to client. Blender bridge default: `127.0.0.1` only. Remote mode only explicit advanced opt-in.

### 12.2 MCP features

Implement:

- tools;
- resources;
- prompts;
- logging/progress;
- cancellation for long jobs where possible.

### 12.3 Tool namespaces

```text
preflight.*
project.*
scene.*
camera.*
lighting.*
material.*
render.*
evaluate.*
export.*
web.*
security.*
```

### 12.4 Required tools

#### `preflight.system_check`

Input:

```json
{
  "project_dir": "string",
  "requested_profile": "auto|safe_laptop|balanced|cinematic|ultra_4k"
}
```

Output:

```json
{
  "ok": true,
  "hardware_report_path": "string",
  "quality_profile": "balanced",
  "warnings": []
}
```

#### `project.create_scene_workspace`

Creates artifact folders and initial manifest.

#### `scene.initialize_blend`

Creates `.blend` with collections, units, camera, lights, metadata.

#### `scene.apply_recipe`

Preferred execution path. Structured operations, not arbitrary Python.

```json
{
  "operations": [
    {"op": "create_mesh_primitive", "type": "cube", "name": "base_pedestal", "location": [0,0,0]},
    {"op": "add_bevel_modifier", "target": "base_pedestal", "width": 0.05, "segments": 6},
    {"op": "assign_material", "target": "base_pedestal", "material": "mat_black_reflective"}
  ]
}
```

#### `scene.execute_blender_python_safe`

Advanced/dev-only tool. Disabled by default. Must enforce:

- workspace sandbox;
- timeout;
- no shell execution;
- no network;
- no writes outside workspace;
- explicit approval where host supports it;
- logs.

Existing MCP projects often expose Python execution. Here raw Python is considered dangerous and not the normal path.

#### `scene.inspect`

Returns:

- collections;
- object counts;
- active camera;
- lights;
- materials;
- modifiers;
- animation data;
- missing files;
- bounding boxes;
- render settings.

#### `camera.plan_and_create`

Creates/updates cameras from composition plan.

#### `lighting.create_setup`

Creates light rig from preset.

#### `material.create_pbr`

Creates PBR/procedural material from schema.

#### `render.preview`

Low/medium preview with temporary safe settings.

#### `render.final`

Final still/animation only after `evaluate.preview` passes or explicit `force`.

#### `evaluate.preview`

Hard checks + optional metrics.

#### `evaluate.scene_lint`

Structural scene lint without rendering.

#### `export.glb`

Exports web-ready `.glb` with metadata.

#### `web.validate_glb`

Loads GLB in local Three.js viewer and checks:

- load success;
- console errors;
- animation clips;
- cameras;
- material/texture warnings;
- bounding box;
- approximate asset size;
- frame loop sanity.

#### `web.generate_integration`

Generates:

- vanilla three.js example;
- React Three Fiber example;
- R3F + Drei ScrollControls example;
- GSAP ScrollTrigger camera timeline example.

#### `project.final_report`

Writes final Markdown/JSON report.

### 12.5 MCP resources

```text
resource://blender/current_scene.json
resource://blender/current_render_settings.json
resource://blender/current_hardware_report.json
resource://blender/last_preview.png
resource://project/scene_manifest.json
resource://project/final_report.md
resource://docs/camera-language.md
resource://docs/visual-critique-rubric.md
```

### 12.6 MCP prompts

```text
prompt://cinematic_scene_workflow
prompt://reference_match_workflow
prompt://web_3d_hero_workflow
prompt://safe_laptop_workflow
prompt://scene_repair_workflow
prompt://benchmark_run_workflow
```

Prompts should accept arguments: brief, output mode, target runtime, quality profile, max iterations.

---

## 13. Blender add-on requirements

### 13.1 Add-on behavior

Add-on must:

- install as normal Blender extension/add-on;
- expose preferences: host, port, auto-start, workspace root, safety mode;
- start/stop bridge manually;
- bind localhost by default;
- process one job at a time unless async manager is safely implemented;
- return structured JSON;
- write logs to workspace.

### 13.2 Safety modes

- `strict` — default, structured operations only.
- `dev` — safe Python with warnings, timeouts, sandbox.
- `unsafe` — must not exist as a default user-facing option.

### 13.3 Job management

Every operation needs:

- job ID;
- start time;
- timeout;
- progress updates where possible;
- cancellation where possible;
- status: `success`, `failed`, `cancelled`, `timeout`.

### 13.4 Background mode

Support CI/headless:

```bash
blender -b --python scripts/run_blender_job.py -- <job-json>
```

Interactive add-on can support viewport screenshots; headless mode must support scene inspection, final renders and exports.

---

## 14. Web export requirements

### 14.1 Formats

Support:

- `.blend`;
- `.png` still;
- image sequence/video when requested;
- `.glb/.gltf`;
- optional `.usd`, `.fbx`, `.obj`.

### 14.2 GLB export rules

For web targets:

- default GLB unless split `.gltf` requested;
- keep under `max_glb_mb`;
- remove invisible/helper objects unless tagged for export;
- apply transforms where appropriate;
- preserve meaningful node names;
- include animation clips if requested;
- include cameras if runtime uses Blender camera path;
- simplify/bake/report unsupported Blender material features;
- validate export after writing.

### 14.3 Optimization

Local optional tools:

- `gltf-transform` for inspect/optimize/texture transforms;
- Draco or Meshopt only when target runtime supports it;
- texture compression only if local toolchain exists and validation passes.

### 14.4 Three.js/R3F integration

Generated web code must include:

- loader setup;
- camera selection/generated camera;
- AnimationMixer handling;
- resize handling;
- disposal notes;
- scroll mapping when requested;
- fallback poster image;
- performance budget comments.

### 14.5 Scroll-linked 3D section

For scroll effects:

- define camera path with named markers in Blender;
- export path as JSON if native camera animation export is unreliable;
- map scroll progress `0..1` to camera position/quaternion or animation time;
- validate that scroll changes camera state;
- include reduced-motion fallback.

---

## 15. Visual evaluation system

### 15.1 Evaluation layers

Do not trust one metric. Use layers:

1. File existence.
2. Scene structure.
3. Render sanity.
4. Reference similarity if reference exists.
5. Aesthetic rubric.
6. Web validation.
7. Human-readable final report.

### 15.2 Render sanity checks

`visual_eval.py` computes:

- image dimensions;
- file size;
- average brightness;
- contrast;
- percent near-black pixels;
- percent near-white pixels;
- edge density / silhouette proxy;
- accidental empty alpha;
- whether render is identical to previous iteration.

### 15.3 Optional reference metrics

If reference image exists:

- SSIM for structural/layout comparison after resize/crop;
- LPIPS optional if local PyTorch dependencies installed;
- pHash/feature matching optional;
- local CLIP/open_clip optional, but tests must pass without huge runtime download.

### 15.4 Self-critique instruction

After each preview:

```text
Inspect the actual preview/render, not the plan.
List 5 concrete visual defects.
List 3 technical defects if any.
Decide whether defects are fixable in remaining iteration budget.
Make one targeted improvement pass; do not randomly rebuild everything.
```

### 15.5 Iteration eval result

```json
{
  "iteration": 3,
  "hard_fail": false,
  "scores": {
    "composition": 15,
    "lighting": 12,
    "materials": 10,
    "geometry_detail": 12,
    "camera": 8,
    "reference_fidelity": 7,
    "technical": 9,
    "performance": 5,
    "total": 78
  },
  "defects": [
    "dial markings are too sparse for close-up",
    "rim light is too strong on left side",
    "background silhouette competes with subject"
  ],
  "next_actions": [
    "add small tick marks and screws",
    "reduce rim light energy by 25%",
    "darken background arches"
  ]
}
```

---

## 16. Benchmark suite

### 16.1 Purpose

Benchmark must compare:

1. Generic agent without skill.
2. Agent + raw Blender MCP tools.
3. Agent + this skill + MCP/tools.

Goal: prove measurable improvement.

### 16.2 Required benchmark tasks

#### A. Product hero still

Prompt: premium cinematic product render of futuristic watch.
Checks: macro camera, bevels, materials, reflections, lighting, subject centered, render exists.

#### B. Sci-fi corridor

Checks: depth, repeated detail, lights, no random cube mess, safe hardware fallback.

#### C. Mechanical exploded view

Checks: components, labels/arrows optional, clean camera, clean materials.

#### D. Web scroll hero

Checks: GLB export, viewer load, camera path JSON/code, scroll validation.

#### E. Low-spec laptop safe mode

Checks: downshift profile, no 4K, preview succeeds, report explains fallback.

#### F. Reference match

Checks: palette, silhouette, key objects, reference metrics.

#### G. Camera animation turntable

Checks: 120 frames/keyframes, smooth path, preview strip.

#### H. Scene repair

Input: broken scene with bad camera/lights/names.
Checks: linter catches, repair fixes, before/after report.

#### I. GLB web export budget

Checks: asset size, texture cap, loader success, clean console.

### 16.3 Benchmark output

```json
{
  "task_id": "product_hero_watch",
  "mode": "skill_plus_mcp",
  "pass": true,
  "visual_score": 84,
  "technical_score": 92,
  "runtime_seconds": 640,
  "iterations": 5,
  "artifacts": ["..."],
  "failures": []
}
```

---

## 17. Testing strategy

### 17.1 Unit tests

Cover:

- manifest validation;
- profile selection;
- render budget;
- path sandbox;
- recipe schema;
- operation allowlist;
- material schema;
- naming linter;
- image sanity metrics;
- report writer.

### 17.2 Blender integration tests

Headless Blender where available:

- create project;
- create collections;
- create simple scene from recipe;
- render thumbnail;
- inspect scene;
- export GLB;
- detect missing textures;
- verify active camera/lights/materials.

### 17.3 Visual regression tests

- Small deterministic scenes.
- 256–512 px renders.
- Golden image with tolerance.
- SSIM/histogram/edge sanity.
- Do not require pixel-perfect output across GPU vendors.

### 17.4 Web E2E tests

Use Playwright or equivalent:

- start local viewer;
- load GLB;
- capture console errors;
- verify canvas non-empty;
- verify AnimationMixer clips;
- verify scroll changes camera/animation;
- verify asset size.

### 17.5 Security tests

Verify:

- paths outside workspace rejected;
- network calls rejected in strict mode;
- raw Python disabled by default;
- shell attempts rejected;
- localhost bind default;
- malformed recipe does not crash Blender;
- long operations timeout/cancel.

### 17.6 CI levels

1. Light CI: unit/schema/docs lint, no Blender.
2. Full CI: Blender installed, headless integration, thumbnails, optional web tests.

---

## 18. Security requirements

### 18.1 Threat model

The system connects an AI agent to Blender, which can execute Python and access local files. Treat every tool call as potentially dangerous.

Risks:

- arbitrary Python execution;
- reading/writing files outside project root;
- command injection;
- prompt injection through filenames, metadata, assets, docs;
- accidentally exposed remote socket;
- malicious third-party skills;
- huge GLB/asset resource bombs;
- denial-of-service through geometry/particles/render settings.

### 18.2 Mandatory controls

- Bind localhost by default.
- Workspace root allowlist.
- Structured operations preferred.
- Raw Python disabled unless explicit dev flag.
- No shell concatenation.
- Subprocess argument arrays only.
- Timeouts for all Blender jobs.
- File size limits for imports/references.
- Complexity budget.
- Render memory guard.
- Human approval for destructive operations where host supports it.
- Logs with tool name, params, duration, result, touched files.
- Dependency pinning/lockfiles.
- PR security checklist.

### 18.3 Import restrictions

Default strict mode: no arbitrary imports inside Blender job code. Use project-owned modules and Blender built-ins. Extra packages require explicit dependency and tests.

### 18.4 Network restrictions

Default: no network.
Optional asset providers must be separate adapters, disabled by default, documented, test-skippable.

---

## 19. Performance/reliability

### 19.1 Timeouts

| Job | Default timeout |
|---|---:|
| preflight | 60 s |
| scene inspection | 30 s |
| thumbnail render | 120 s |
| preview render | 300 s |
| final still render | configurable, default 1800 s |
| animation render | explicit config required |
| GLB export | 300 s |
| web validation | 120 s |

### 19.2 Crash recovery

Before heavy operation:

- save `.blend`;
- write operation plan JSON;
- flush logs.

If Blender crashes:

- report failing operation;
- keep last successful `.blend`;
- preserve artifacts.

### 19.3 Determinism

Where possible:

- set seeds;
- store seed in manifest;
- save Blender version;
- save render settings;
- prefer deterministic procedural generation for tests.

### 19.4 Complexity budget

Scene linter estimates:

- object count;
- vertices/faces;
- modifiers;
- texture dimensions/count;
- particle counts;
- volume usage;
- material node complexity.

Warn/fail above profile budget.

---

## 20. Implementation phases

### Phase 0 — Repository foundation

Deliver:

- repo layout;
- `SKILL.md` MVP;
- `references/` first drafts;
- schemas;
- unit tests;
- source policy;
- security policy.

Exit:

- unit tests pass;
- skill metadata validates;
- manifest schema validates.

### Phase 1 — Local Blender runner

Deliver:

- Blender locator;
- hardware preflight;
- background job runner;
- scene recipe executor;
- thumbnail render;
- scene inspector.

Exit:

- headless test creates scene and thumbnail;
- hardware report created;
- scene lint works.

### Phase 2 — MCP server + add-on

Deliver:

- MCP stdio server;
- Blender add-on bridge;
- strict structured tools;
- resources/prompts;
- logs/timeouts/cancellation.

Exit:

- tools `preflight.system_check`, `scene.initialize_blend`, `render.preview`, `scene.inspect` work;
- raw Python disabled by default.

### Phase 3 — Creative pipeline

Deliver:

- camera presets;
- lighting presets;
- material recipes;
- blockout/refine workflow;
- visual evaluation;
- iteration manager.

Exit:

- benchmark A/B/G pass at preview scale;
- final report generated.

### Phase 4 — Web export

Deliver:

- GLB export;
- glTF optimization adapter;
- Three.js/R3F code generation;
- local web validation;
- scroll-linked camera path.

Exit:

- benchmark D/I pass;
- GLB loads in local viewer.

### Phase 5 — Benchmarks/release

Deliver:

- full benchmark suite;
- baseline comparison;
- docs;
- examples;
- release automation.

Exit:

- required benchmark tasks have results;
- quickstart works;
- license chosen;
- security checklist complete.

---

## 21. Acceptance criteria

### 21.1 MVP accepted when

- Skill installs as folder with valid `SKILL.md`.
- User can run local command to create Blender scene from manifest.
- Preflight selects safe profile.
- Headless Blender test creates collections/camera/lights/materials.
- Preview render produced.
- Visual sanity report produced.
- Final report produced.
- Unit tests pass.
- Security tests for path sandbox + raw Python disabled pass.

### 21.2 v1 accepted when

- MCP server + Blender add-on work locally.
- Agent can create/iterate scene through structured tools.
- At least 9 benchmark tasks exist.
- At least 7 tasks pass under `balanced` profile on normal dev machine.
- GLB export + local web validation work.
- Scroll-linked camera demo works.
- Visual evaluation catches black/off-camera/default-material failures.
- Docs include install, setup, security, troubleshooting, benchmarks.
- No paid API required.

### 21.3 Quality bar

Not done if it only makes simple cube scenes. Must demonstrate:

- semantic object naming;
- bevels/details;
- deliberate lighting;
- deliberate camera;
- material variation;
- preview/critique/refinement loop;
- hardware-aware rendering;
- export validation.

---

## 22. Example workflow

User prompt:

```text
Create a cinematic 3D hero object for my website: a floating AI energy core, dark background, blue light, scroll camera effect, export GLB.
```

Agent must:

```text
1. output_mode = interactive_web.
2. Run preflight.
3. Create manifest.
4. Select balanced/safe profile.
5. Plan: core, rings, emissive circuits, dark stage, camera path.
6. Build blockout.
7. Render preview.
8. Critique: too simple, lacks depth, overbright core.
9. Add detail: inner rings, orbiting elements, rough metal, rim light.
10. Render second preview.
11. If score passes, export GLB.
12. Validate GLB in local Three.js viewer.
13. Generate R3F ScrollControls integration.
14. Produce final report.
```

---

## 23. Example `SKILL.md` draft

```md
# Blender Cinematic Scene Skill

Use this skill for Blender scene generation, cinematic rendering, camera animation, GLB/glTF export, and 3D web integration.

## Mandatory workflow

1. Classify the request as still, animation, web_asset, interactive_web, reference_match, scene_repair, or benchmark.
2. Create/update scene manifest.
3. Run hardware preflight before heavy render.
4. Select safe quality profile: safe_laptop, balanced, cinematic, ultra_4k.
5. Build blockout first.
6. Add intentional camera, lighting, materials, named collections.
7. Render/capture preview.
8. Inspect actual preview and list concrete defects.
9. Improve one targeted group of issues per iteration.
10. Final render/export only after hard checks pass.
11. For web assets, export GLB and validate in local viewer.
12. Produce final report with artifact paths and limitations.

## Never

- Never claim 4K quality just because resolution is 3840×2160.
- Never skip preview inspection.
- Never leave default cube naming in final scenes.
- Never run heavy final renders before preflight.
- Never require paid APIs.
- Never use unlicensed assets.
- Never expose raw Blender Python execution in normal mode.
```

---

## 24. Documentation requirements

Final docs must include:

```text
docs/installation.md
docs/mcp-setup.md
docs/blender-addon.md
docs/skill-authoring.md
docs/web-export.md
docs/security.md
docs/benchmarking.md
docs/troubleshooting.md
```

README must explain:

- what the skill does;
- install steps;
- setup for Codex/Claude/Cursor/Gemini-like agents;
- Blender add-on install;
- MCP setup;
- quickstart scene;
- quickstart GLB/web;
- hardware profiles;
- security model;
- tests;
- benchmarks;
- troubleshooting;
- contribution.

---

## 25. Target developer commands

```bash
# install dev deps
uv sync --all-extras

# validate skill
uv run python scripts/validate_skill.py

# preflight
uv run python scripts/preflight_hardware.py --project-dir ./artifacts/demo

# run manifest through Blender background mode
uv run python scripts/run_blender_job.py --manifest examples/prompts/product_hero_watch.json

# unit tests
uv run pytest tests/unit -q

# full tests with Blender
uv run pytest tests/integration_blender -q --blender-executable /path/to/blender

# benchmark subset
uv run python benchmarks/runners/run_benchmarks.py --profile safe_laptop --tasks product_hero_watch,sci_fi_corridor

# start MCP server
uv run blender-cinematic-mcp

# package skill
uv run python scripts/package_skill.py
```

If `uv` is unavailable, plain `python -m venv` + `pip install -e .[dev]` must work.

---

## 26. Coding standards

- Python with typing where practical.
- Pydantic/dataclasses for schemas.
- TypeScript only for web validation/demo.
- No hidden network dependency in tests.
- `pathlib` for paths.
- All writes through workspace resolver.
- Subprocess calls as argument arrays, not shell strings.
- Separate pure Python logic from Blender-specific `bpy` logic.
- Mock `bpy` only for unit tests; real Blender integration tests required.
- Every tool schema has tests.
- Every safety guard has negative test.

---

## 27. Release requirements

Release must include:

- source archive;
- skill folder package;
- Blender add-on zip;
- MCP server package;
- checksums;
- changelog;
- benchmark summary;
- security notes.

Versioning:

```text
0.x = experimental
1.0 = stable local workflow with skill + MCP + Blender add-on + benchmarks
```

---

## 28. Known hard parts

### 28.1 Beauty is subjective

Mitigation: rubric + hard checks + examples + benchmarks + human review. Do not pretend one metric solves aesthetics.

### 28.2 Agents ignore instructions

Mitigation: short strict `SKILL.md`, schemas that enforce order, final report from real artifacts.

### 28.3 Blender API changes

Mitigation: compatibility matrix, integration tests, version detection, adapters.

### 28.4 Hardware variability

Mitigation: profiles, preview-first, timeouts, memory guards, safe fallback.

### 28.5 glTF export mismatch

Mitigation: validation, material simplification, optional baking, honest report.

### 28.6 Camera animation for web

Mitigation: export native animation and explicit camera path JSON.

### 28.7 Security vs capability

Mitigation: structured operations default, dev-mode Python only, localhost, path sandbox, logs.

---

## 29. Definition of done

Project is done when an agent can take a non-trivial Blender/web 3D prompt and produce:

1. scene manifest;
2. hardware-aware render budget;
3. clean `.blend`;
4. preview renders from actual camera;
5. self-critique reports;
6. refinement iteration;
7. final render/animation;
8. valid GLB/web export when requested;
9. local web validation report when requested;
10. honest final report with artifact paths, passes, failures, limitations.

The project fails if it only gives the model a bigger hammer. It succeeds if it gives the model a disciplined Blender production process.

---

## 30. Immediate implementation tickets

Create these issues first:

1. `repo: create base layout and license`
2. `skill: write first SKILL.md with mandatory workflow`
3. `schema: implement scene_manifest schema and validation`
4. `preflight: hardware and Blender detection`
5. `runner: run Blender background job from manifest`
6. `scene: create required collections/camera/lights/materials`
7. `render: thumbnail preview render with safe settings`
8. `lint: scene structure and render sanity checks`
9. `report: final markdown/json report writer`
10. `tests: unit tests for schemas, path sandbox, profile selection`
11. `integration: headless Blender test creates and renders a scene`
12. `mcp: skeleton server with preflight and scene inspect tools`
13. `addon: local bridge skeleton with strict mode`
14. `benchmark: product hero MVP task`
15. `web: GLB export and local viewer validation MVP`


---

## 31. V2 Deep Coverage Patch: shader, animation, camera, nodes, simulations, compositor

Эта секция обязательна. Она закрывает то, что в базовом SRS было описано слишком общо. Цель V2 — превратить skill из “агент умеет дергать Blender” в “агент умеет строить художественно, технически и производственно пригодную Blender-сцену”.

### 31.1 Главный принцип V2

Агент не должен просто выполнить промпт и срендерить картинку. Он обязан работать как мини-команда:

1. **Art director** — понимает стиль, композицию, референсы, настроение, читаемость сцены.
2. **Technical director** — выбирает правильные ноды, шейдеры, модификаторы, оптимизацию и экспорт.
3. **Cinematographer** — ставит камеру, фокусное расстояние, движение, глубину резкости, кадрирование.
4. **Lighting artist** — строит световую схему, контролирует контраст, блики, читаемость формы.
5. **Material artist** — создает не default-gray, а осмысленные PBR/процедурные материалы.
6. **Animator** — если есть движение, задает timeline, keyframes, easing, camera paths, loops.
7. **QA auditor** — проверяет сцену, рендер, экспорт, web-интеграцию, производительность и визуальное качество.

Skill должен заставлять агента проходить все эти роли через чек-листы, а не надеяться на “модель сама догадается”.

### 31.2 Что считается “учтено”

Функция считается учтенной только если для нее есть:

- явное место в workflow;
- схема входных данных;
- минимальный working implementation;
- linter/validator;
- benchmark task или unit/integration test;
- fallback для слабого железа;
- отчет в `artifacts/.../report.md`.

Если есть только текстовое упоминание — это не считается готовым.

---

## 32. Shader and Material System

### 32.1 Цель

Создать систему материалов, которая не генерирует случайные Blender defaults, а строит контролируемые PBR/процедурные шейдеры под стиль сцены, рендер-профиль и экспортную цель.

### 32.2 Обязательные типы материалов

Skill должен поддерживать минимум такие material presets:

| Preset | Назначение | Обязательные параметры |
|---|---|---|
| `matte_plastic` | продукты, корпуса, простые объекты | color, roughness, bevel support |
| `glossy_plastic` | premium product, tech device | color, roughness, clearcoat |
| `brushed_metal` | металл, оружие, механика, watch render | metallic, roughness, anisotropy approximation |
| `painted_metal` | автомобили, sci-fi корпус | base coat, roughness, edge highlights |
| `glass_clear` | стекло, линзы, панели | transmission/alpha fallback, IOR approximation |
| `frosted_glass` | матовое стекло | roughness, alpha, noise/bump |
| `emissive_neon` | неон, sci-fi lights | emission color, strength, bloom note |
| `rubber_dark` | шины, рукоятки, прокладки | high roughness, subtle noise bump |
| `fabric` | одежда, soft props | weave/noise bump, low sheen |
| `skin_stylized` | stylized character only | color zones, roughness, no uncanny realism |
| `stone_concrete` | architecture, walls | procedural noise, bump, color variation |
| `wood` | furniture/product scene | grain direction, color bands, bump |
| `water_simple` | stylized water/web | alpha, normal noise, export fallback |
| `hologram` | futuristic UI/projection | transparent emission, scanline nodes |

### 32.3 Material schema

Каждый материал должен создаваться по JSON-схеме, а не произвольным кодом:

```json
{
  "name": "brushed_black_titanium",
  "preset": "brushed_metal",
  "target_objects": ["watch_case", "side_buttons"],
  "pbr": {
    "base_color": [0.02, 0.022, 0.026, 1.0],
    "metallic": 1.0,
    "roughness": 0.34,
    "clearcoat": 0.15,
    "alpha": 1.0
  },
  "procedural": {
    "noise": true,
    "noise_scale": 80,
    "bump_strength": 0.035,
    "edge_wear": "subtle"
  },
  "export_policy": {
    "web_safe": true,
    "bake_if_needed": true,
    "fallback_material": "metallic_roughness_pbr"
  }
}
```

### 32.4 Shader node rules

Skill must provide high-level material commands. It must not force the LLM to manually remember Blender node API details for every scene.

Required internal builders:

- `material.create_pbr_material`
- `material.create_procedural_material`
- `material.apply_material`
- `material.validate_materials`
- `material.bake_materials_for_export`
- `material.simplify_materials_for_web`
- `material.generate_material_manifest`

### 32.5 Node naming rules

Every generated node group must use meaningful names:

```text
NG_BrushedMetal_Base
NG_EdgeWear_Subtle
NG_Hologram_Scanlines
NG_Concrete_NoiseBump
NG_Fabric_WeaveBump
```

Bad names are forbidden:

```text
NodeGroup.001
Material.004
Noise Texture.023
```

### 32.6 Procedural shader patterns

The skill must include reference recipes for:

1. **Edge wear** — subtle brightening on bevels/edges.
2. **Dust/dirt layer** — noise mask in cavities or horizontal surfaces.
3. **Micro scratches** — anisotropic line noise for close-up metal.
4. **Fingerprint/smudges** — low-strength roughness variation for glossy surfaces.
5. **Fabric weave** — crossed wave/noise texture bump.
6. **Concrete roughness** — multi-scale noise color and bump.
7. **Hologram scanline** — emission + transparency + horizontal bands.
8. **Glass imperfections** — tiny bump/noise, not perfectly sterile glass.
9. **Energy core** — layered emission, transparent shell, bloom-aware setup.

### 32.7 Render engine compatibility

The material system must store compatibility:

```json
{
  "material_name": "hologram_blue_scanlines",
  "cycles": "full",
  "eevee": "partial",
  "workbench": "fallback",
  "glb_export": "bake_or_simplify",
  "web_realtime": "simplified_emissive_alpha"
}
```

### 32.8 Material linter

Fail or warn when:

- important object has no material;
- material name is generic;
- material uses impossible values accidentally;
- all objects use same material without explicit style reason;
- metallic material has no bevel or no lighting to reveal it;
- glass/transmission used for web export without fallback;
- procedural texture is too heavy for selected profile;
- texture resolution exceeds quality profile cap;
- material graph has too many nodes for web-bound asset;
- material not assigned to target object.

### 32.9 Material benchmarks

Minimum tests:

- create brushed metal watch case;
- create frosted glass panel;
- create neon hologram sign;
- create concrete corridor wall;
- export each to GLB and validate fallback;
- compare render before/after material pass;
- verify no `Material.001` names remain.

---

## 33. Geometry Nodes and Procedural Modeling

### 33.1 Цель

Geometry Nodes нужны не ради сложности, а чтобы агент мог быстро создавать сложные повторяющиеся детали: sci-fi panels, cables, grids, city blocks, rocks, foliage, particles-like distributions, architectural patterns.

### 33.2 Allowed use cases

Geometry Nodes should be used for:

- repeated panels/wall modules;
- cable bundles;
- procedural grids;
- bolts/screws/rivets distribution;
- city/window arrays;
- asteroid/rock scattering;
- low-poly foliage placement;
- decorative trims;
- parametric product details;
- controlled instancing for performance.

### 33.3 Forbidden use cases

Do not use Geometry Nodes when:

- simple mesh/modifier is enough;
- it makes export impossible and no bake path exists;
- it creates unbounded geometry;
- it hides important scene structure from linter;
- it creates random results without seed logging;
- weak hardware profile is active and node complexity is high.

### 33.4 Geometry node schema

```json
{
  "node_group_name": "GN_SciFiWallPanels",
  "target_object": "corridor_wall_left",
  "purpose": "repeat beveled panel modules along wall",
  "inputs": {
    "panel_count": 18,
    "panel_depth": 0.035,
    "bevel_width": 0.015,
    "seed": 42,
    "detail_level": "balanced"
  },
  "export_policy": {
    "apply_before_glb": true,
    "keep_modifier_in_blend": true,
    "max_generated_faces": 120000
  }
}
```

### 33.5 Required procedural recipes

Skill must provide reusable recipes:

1. `GN_PanelWall` — corridor/architecture detail.
2. `GN_BoltDistributor` — bolts/rivets on surfaces.
3. `GN_CableBundle` — controlled bezier/curve cables.
4. `GN_CityWindows` — window grids with emissive variation.
5. `GN_RockScatter` — deterministic rock/asteroid scatter.
6. `GN_TechGreebles` — sci-fi surface details.
7. `GN_LabelArrows` — exploded view arrows/labels as geometry.
8. `GN_OrbitalRings` — rings around energy core/planet/product.
9. `GN_ParticleDots` — lightweight dots/points for hologram/field visualization.
10. `GN_VegetationLow` — simple grass/leaves for safe scenes.

### 33.6 Procedural determinism

Every node group using random values must expose and log:

- `seed`;
- object count;
- estimated face count;
- applied/not applied before export;
- profile-specific simplification.

### 33.7 Geometry linter

Warn/fail when:

- generated face count exceeds budget;
- node group has no meaningful name;
- node group has no seed;
- result is invisible from final camera;
- geometry intersects subject accidentally;
- procedural details dominate the subject;
- export requested but node output not applied/baked;
- too many tiny objects instead of instances/merged geometry.

### 33.8 Geometry benchmarks

Required benchmark tasks:

- create sci-fi corridor wall using procedural panels;
- create mechanical exploded view with bolts and labels;
- create city night skyline with emissive windows;
- export geometry-node scene to GLB after applying/baking;
- compare face count before/after optimization;
- verify deterministic rerun with same seed.

---

## 34. Animation System

### 34.1 Цель

Skill должен уметь делать не только still render, но и controlled animation: turntable, camera flythrough, scroll-linked website camera path, mechanical exploded view, object reveal, lighting pulses, simple character/rig movement if explicitly requested.

### 34.2 Animation modes

Required modes:

| Mode | Purpose | Output |
|---|---|---|
| `turntable` | product/showcase render | frame sequence/video + optional GLB animation |
| `camera_flythrough` | environment/sci-fi corridor | camera path + preview |
| `scroll_linked` | website hero section | GLB + camera path JSON/R3F code |
| `exploded_view` | mechanical/technical object | animated parts + labels |
| `reveal` | object appears/builds up | keyframes/visibility/material alpha |
| `loop_idle` | website/background asset | seamless loop |
| `light_pulse` | energy/neon scene | emission/intensity animation |
| `rig_basic` | basic armature/pose movement | only when requested |

### 34.3 Animation schema

```json
{
  "animation_name": "watch_turntable_120f",
  "mode": "turntable",
  "frame_start": 1,
  "frame_end": 120,
  "fps": 24,
  "loop": true,
  "targets": ["watch_root"],
  "curves": {
    "rotation_z": {
      "from": 0,
      "to": 6.28318,
      "interpolation": "linear"
    }
  },
  "camera": {
    "name": "camera_hero_macro",
    "locked": true,
    "dof_target": "watch_face"
  },
  "export": {
    "include_in_glb": true,
    "clip_name": "Turntable"
  }
}
```

### 34.4 Keyframe rules

- Keyframes must be named in action/clip metadata when possible.
- Timeline markers must identify important beats.
- Interpolation must be intentional: `linear`, `ease_in_out`, `hold`, etc.
- Camera motion must be previewed before final render.
- Loop animations must be checked for first/last frame mismatch.
- Agent must not create random keyframes without explaining them in the manifest.

### 34.5 Camera path animation

Camera paths must include:

- curve/path object or explicit sampled camera transforms;
- focal length changes only when justified;
- DOF target changes only when justified;
- collision/framing check for important objects;
- speed smoothing;
- viewport preview capture.

### 34.6 Scroll-linked animation for websites

For website output, Blender timeline must be convertible to web scroll state:

```json
{
  "scroll_timeline": {
    "duration_pages": 4,
    "segments": [
      {
        "from_scroll": 0.0,
        "to_scroll": 0.25,
        "camera_from_frame": 1,
        "camera_to_frame": 40,
        "text_section": "intro"
      },
      {
        "from_scroll": 0.25,
        "to_scroll": 0.60,
        "camera_from_frame": 41,
        "camera_to_frame": 90,
        "text_section": "feature_reveal"
      }
    ]
  }
}
```

### 34.7 Animation linter

Fail/warn when:

- animation requested but no keyframes/actions exist;
- frame range is default/incorrect;
- camera animation exists but active camera not assigned;
- movement is too fast/jerky;
- first/last loop frames do not match;
- GLB requested but animation clip not exported;
- web scroll requested but no camera path JSON generated;
- timeline markers missing for complex animation;
- object moves outside camera frame;
- viewport preview not generated.

### 34.8 Animation benchmarks

Required:

- 120-frame product turntable;
- 10-second corridor flythrough;
- scroll-linked hero camera path;
- mechanical exploded-view animation;
- looping neon pulse;
- GLB animation load in local viewer;
- screenshot comparison at frames 1/30/60/90/120.

---

## 35. Camera and Cinematography System

### 35.1 Цель

Камера — главный источник “дорого выглядит / дешево выглядит”. Skill должен заставлять агента работать с камерой осознанно, а не ставить `camera at (0, -5, 3)`.

### 35.2 Camera presets

Required presets:

| Preset | Focal feel | Use case |
|---|---|---|
| `macro_product` | close, shallow DOF | watches, gadgets, luxury product |
| `hero_low_angle` | powerful, premium | car/robot/device hero shot |
| `orthographic_technical` | clear, diagram-like | exploded view, technical visualization |
| `wide_environment` | depth, scale | corridor, city, landscape |
| `top_down_layout` | map/diagram | planning, UI/board scene |
| `portrait_medium` | character/object | stylized character/product |
| `scroll_hero_start` | website opening | 3D landing page section |
| `scroll_hero_detail` | feature reveal | web scroll middle section |

### 35.3 Camera schema

```json
{
  "camera_name": "camera_hero_macro",
  "preset": "macro_product",
  "target": "watch_face",
  "composition": {
    "rule": "rule_of_thirds_center_bias",
    "subject_screen_coverage": 0.62,
    "safe_margin": 0.08,
    "leading_lines": true
  },
  "lens": {
    "focal_length_mm": 70,
    "sensor_width_mm": 36,
    "dof": true,
    "focus_target": "watch_face",
    "aperture_fstop": 2.8
  },
  "motion": null
}
```

### 35.4 Composition checks

Skill must calculate or approximate:

- subject bounding box inside camera frame;
- subject coverage percentage;
- clipping/camera intersection;
- horizon/tilt sanity;
- excessive empty space;
- subject hidden by other object;
- focal target exists;
- DOF is not destroying readability;
- camera sees final intended collection.

### 35.5 Camera language in prompts

Agent must translate vague words into camera choices:

- “premium” → controlled focal length, shallow DOF, clean background, rim highlights.
- “cinematic” → foreground/midground/background, intentional contrast, not flat front view.
- “technical” → orthographic/clear perspective, labels, no dramatic distortion.
- “website hero” → camera path safe for scroll, subject not too close, mobile crop considered.
- “epic” → scale reference, low angle/wide lens carefully, atmospheric depth if hardware allows.

### 35.6 Camera linter

Fail/warn when:

- no active camera;
- active camera not named;
- subject not visible;
- subject too tiny or cut off;
- camera inside geometry;
- DOF target missing;
- clipping cuts scene;
- animation camera path has jerks;
- multiple cameras exist but final camera unspecified;
- web scene lacks mobile-safe camera framing.

### 35.7 Camera benchmarks

- product macro shot with readable details;
- orthographic exploded view;
- cinematic corridor with depth;
- scroll camera path with 4 sections;
- mobile crop safety test.

---

## 36. Lighting System

### 36.1 Цель

Lighting должен делать форму читаемой. Skill не должен принимать сцену, где объект темный, плоский, пересвеченный или выглядит как default viewport.

### 36.2 Required lighting rigs

| Rig | Use case |
|---|---|
| `three_point_soft` | generic/product readable lighting |
| `studio_product_large_softbox` | premium product render |
| `neon_cyberpunk` | sci-fi/cyberpunk scenes |
| `corridor_practical_lights` | environment depth |
| `technical_clean` | diagrams/exploded views |
| `dramatic_rim` | hero render with edge highlights |
| `world_hdri_like` | environment fill without paid HDRIs |
| `low_spec_flat_safe` | weak hardware fallback |

### 36.3 Lighting schema

```json
{
  "lighting_rig": "studio_product_large_softbox",
  "lights": [
    {
      "name": "key_softbox_left",
      "type": "AREA",
      "power": 450,
      "size": 5.0,
      "position_role": "front_left_high"
    },
    {
      "name": "rim_blue_right",
      "type": "AREA",
      "power": 120,
      "size": 2.0,
      "color": [0.35, 0.55, 1.0]
    }
  ],
  "world": {
    "color": [0.015, 0.017, 0.022],
    "strength": 0.4
  }
}
```

### 36.4 Lighting validation

Skill must inspect render preview for:

- average brightness;
- black crush;
- overexposure;
- subject/background separation;
- silhouette readability;
- highlight presence on bevels/metal/glass;
- color harmony;
- shadow direction not confusing.

### 36.5 Lighting linter

Fail/warn when:

- only default light exists;
- no light rig selected;
- scene is too dark/bright;
- metallic/glass material has no highlights;
- subject blends into background;
- shadow hides important detail;
- too many high-power lights cause white render;
- volumetric lighting enabled on weak profile.

---

## 37. Modifiers, Modeling and Mesh Quality

### 37.1 Required modifier support

Skill must support controlled usage of:

- bevel;
- weighted normal;
- subdivision surface;
- array;
- mirror;
- solidify;
- curve bevel/depth;
- shrinkwrap when useful;
- boolean only when result is validated;
- decimate for optimization;
- triangulate for export when needed.

### 37.2 Mesh quality rules

- Important hard-surface objects should usually have bevels.
- Bevel size must be proportional to object scale.
- Normals must be recalculated/validated.
- Shading must be smooth only where appropriate.
- Boolean artifacts must be detected.
- Objects must have real scale applied before export when needed.
- No accidental hidden mega-meshes.
- No thousands of duplicate loose objects when array/instances can be used.

### 37.3 Mesh linter

Fail/warn when:

- important object has sharp un-beveled edges in premium render;
- normals are flipped or broken;
- object has unapplied huge transform scale and export requested;
- modifiers exist but are disabled/render-hidden accidentally;
- boolean result has non-manifold artifacts;
- face count exceeds profile budget;
- tiny details exist but are invisible from camera.

---

## 38. Rigging, Drivers and Constraints

### 38.1 Scope

This skill is not primarily a character animation suite, but it must support basic rig/driver workflows for mechanical and product animation.

### 38.2 Required support

- empty-based object rigs;
- parent/child hierarchy;
- constraints: track-to, copy rotation, follow path;
- drivers for simple linked motion;
- armature only for explicit rigging tasks;
- named control objects;
- locked transforms where accidental edits are dangerous.

### 38.3 Rig manifest

```json
{
  "rig_name": "watch_exploded_view_rig",
  "controls": [
    {
      "name": "CTRL_explode_amount",
      "type": "empty",
      "drives": ["case_top", "dial", "battery", "strap_left"]
    }
  ],
  "drivers": [
    {
      "target": "case_top.location.z",
      "driver": "CTRL_explode_amount.location.z * 0.8"
    }
  ]
}
```

### 38.4 Rig linter

Warn/fail when:

- rig controls are unnamed;
- driver target missing;
- constraint target missing;
- rig breaks after export;
- animation depends on unsupported drivers for GLB without baking;
- armature used unnecessarily.

---

## 39. Simulations and VFX

### 39.1 Scope

Simulations are optional and dangerous for performance. Skill should support simple VFX patterns, but must not burn user hardware.

### 39.2 Allowed VFX presets

- `simple_particles_sparks` — limited count sparks;
- `hologram_particles` — lightweight dots/points;
- `energy_core_shell` — emission + transparent shell;
- `smoke_cards` — fake smoke planes instead of heavy volumetrics;
- `dust_motes` — tiny lightweight particles;
- `liquid_simple` — only stylized/simple, no heavy fluid sim by default.

### 39.3 Simulation restrictions

Default behavior:

- no heavy fluid simulation;
- no high-count particles;
- no unbounded cloth/hair sim;
- no high-resolution smoke/fire domain;
- no baking expensive sims without explicit profile approval;
- prefer fake/procedural/geometry VFX for website/export.

### 39.4 VFX schema

```json
{
  "vfx_name": "energy_core_blue",
  "preset": "energy_core_shell",
  "target": "core_sphere",
  "profile": "balanced",
  "params": {
    "emission_strength": 4.0,
    "shell_alpha": 0.28,
    "particle_count": 180,
    "noise_motion": "subtle"
  },
  "fallback": {
    "safe_laptop": "emissive_core_no_particles"
  }
}
```

### 39.5 VFX linter

Warn/fail when:

- particle count too high;
- simulation cache path missing;
- simulation would exceed profile budget;
- VFX invisible from final camera;
- VFX breaks GLB export;
- volumetrics requested on weak hardware.

---

## 40. Compositor and Post-Processing

### 40.1 Цель

Финальный render должен иметь controlled post-processing: не кислотный, не случайный, не “пересветил bloom”.

### 40.2 Required compositor/post presets

- `clean_product` — subtle contrast, transparent/clean background if needed;
- `cinematic_contrast` — controlled contrast, vignette optional;
- `neon_bloom` — glow/emission scenes;
- `technical_flat` — readable, minimal post;
- `atmospheric_depth` — mist/depth feel only when safe;
- `website_hero` — crop-safe, no aggressive color shift.

### 40.3 Post manifest

```json
{
  "post_preset": "cinematic_contrast",
  "view_transform": "Filmic_or_available_equivalent",
  "look": "medium_high_contrast",
  "exposure": 0,
  "gamma": 1,
  "effects": {
    "bloom": "if_engine_supports",
    "vignette": "subtle",
    "mist": false,
    "color_balance": "cool_shadows_warm_highlights"
  }
}
```

### 40.4 Compositor rules

- Post-processing must be documented in manifest.
- Do not hide bad lighting with extreme post.
- Do not overuse bloom.
- Do not crush details in shadows.
- Do not change product/material colors unless requested.
- Always save raw render and post render separately when possible.

### 40.5 Compositor linter

Warn/fail when:

- output is overprocessed;
- highlights clipped;
- shadows crushed;
- colors drift from reference;
- no raw render saved for comparison;
- compositor nodes have generic names;
- post preset conflicts with technical visualization.

---

## 41. Reference Matching System

### 41.1 Цель

Если пользователь дает референс, skill должен не просто “вдохновиться”, а проверить совпадение по измеримым признакам.

### 41.2 Reference extraction

Agent must extract:

- main subject;
- silhouette;
- palette;
- camera angle;
- lighting direction;
- material types;
- background style;
- composition ratio;
- required details;
- forbidden differences.

### 41.3 Reference match manifest

```json
{
  "reference_summary": {
    "subject": "black premium smartwatch on dark reflective surface",
    "palette": ["black", "blue rim", "white highlights"],
    "camera": "macro front 3/4 low angle",
    "lighting": "large softbox plus blue rim",
    "materials": ["brushed metal", "glass", "rubber strap"]
  },
  "match_targets": {
    "palette_similarity": 0.75,
    "composition_similarity": 0.70,
    "required_objects_present": true,
    "forbidden_default_gray": true
  }
}
```

### 41.4 Reference QA

The evaluation step must compare preview render against reference using:

- human-readable critique;
- object checklist;
- color palette comparison;
- approximate composition/framing comparison;
- optional local image metrics if dependencies exist;
- final “acceptable / needs iteration / reject” decision.

---

## 42. Website and Interactive 3D Integration

### 42.1 Required web outputs

If the user requests website integration, skill must generate:

```text
web/
  index.html or React component
  scene.glb
  camera_path.json
  interaction_manifest.json
  validation_report.json
  screenshots/
    desktop.png
    mobile.png
```

### 42.2 Interaction types

Required:

- scroll-linked camera movement;
- hover highlight;
- click-to-focus;
- turntable drag optional;
- section-based animation trigger;
- reduced motion fallback;
- loading state;
- mobile fallback/simplified asset.

### 42.3 Web validation

Must test:

- GLB loads;
- no console errors;
- camera starts correctly;
- scroll sections trigger correct animation segments;
- asset size under budget;
- mobile viewport still readable;
- FPS/performance estimate if possible;
- texture paths are valid;
- reduced motion mode works.

### 42.4 Web linter

Warn/fail when:

- GLB file missing;
- GLB too heavy;
- no loading fallback;
- no mobile consideration;
- scroll camera clips through model;
- animations do not start;
- Three.js/R3F code references missing nodes;
- web page imports unavailable assets;
- user interaction conflicts with scroll.

---

## 43. Agent Iteration Loop V2

### 43.1 Required loop

For every non-trivial scene:

```text
1. Parse user intent
2. Build scene brief
3. Hardware preflight
4. Choose quality profile
5. Create blockout
6. Validate blockout
7. Add camera
8. Validate camera
9. Add lighting
10. Validate lighting
11. Add modeling/detail
12. Validate geometry
13. Add materials/shaders
14. Validate materials
15. Add animation if requested
16. Validate animation
17. Add post/compositor
18. Preview render
19. Visual critique
20. Patch scene
21. Repeat up to iteration budget
22. Final render/export
23. Final technical QA
24. Report artifacts
```

### 43.2 Iteration budget

Default:

- simple still: max 3 iterations;
- product/cinematic still: max 5 iterations;
- animation: max 6 iterations;
- reference match: max 8 iterations;
- complex web export: max 10 iterations.

The skill must stop early when score passes threshold.

### 43.3 Iteration scoring

```json
{
  "iteration": 4,
  "scores": {
    "composition": 82,
    "camera": 88,
    "lighting": 76,
    "materials": 81,
    "geometry": 79,
    "animation": null,
    "export": 92,
    "performance": 86
  },
  "hard_fails": [],
  "next_patch": [
    "increase rim light separation",
    "add bevels to side buttons",
    "reduce background brightness"
  ]
}
```

---

## 44. Expanded MCP Tools for V2

### 44.1 Material tools

```text
material.create_from_schema
material.assign
material.inspect
material.validate
material.bake_for_export
material.simplify_for_web
material.generate_preview_spheres
```

### 44.2 Geometry/node tools

```text
geometry.create_from_recipe
geometry.add_modifier
geometry.create_geometry_nodes_recipe
geometry.apply_geometry_nodes_for_export
geometry.estimate_complexity
geometry.validate_mesh_quality
```

### 44.3 Camera tools

```text
camera.create_preset
camera.frame_subject
camera.validate_framing
camera.create_path
camera.sample_path_to_json
camera.validate_motion
camera.mobile_crop_test
```

### 44.4 Lighting tools

```text
lighting.create_rig
lighting.validate_brightness
lighting.validate_subject_separation
lighting.generate_light_manifest
```

### 44.5 Animation tools

```text
animation.create_turntable
animation.create_camera_flythrough
animation.create_exploded_view
animation.create_scroll_timeline
animation.validate_keyframes
animation.export_clips
```

### 44.6 Compositor/VFX tools

```text
vfx.create_preset
vfx.validate_budget
compositor.apply_preset
compositor.validate_output
```

### 44.7 Web tools

```text
web.export_glb_validated
web.generate_threejs_viewer
web.generate_r3f_component
web.validate_scroll_interaction
web.capture_desktop_mobile
```

---

## 45. Expanded Benchmark Suite V2

### 45.1 Shader benchmark

Prompt:

```text
Create a premium black titanium smartwatch render with brushed metal, glass face, rubber strap, blue rim light and macro camera.
```

Pass:

- has named brushed metal material;
- has glass material with export fallback;
- has rubber material;
- visible bevel highlights;
- no default gray material on main object;
- preview and final render exist.

### 45.2 Geometry Nodes benchmark

Prompt:

```text
Create a sci-fi corridor wall with procedural repeating panels, bolts, cables, emissive strips and deterministic seed.
```

Pass:

- geometry node group exists or equivalent procedural recipe;
- seed logged;
- face count under budget;
- details visible from camera;
- export path works.

### 45.3 Camera benchmark

Prompt:

```text
Make the object look expensive and cinematic, not like a default Blender object.
```

Pass:

- active camera named;
- subject coverage in acceptable range;
- focal length intentional;
- DOF target valid if used;
- preview through final camera saved.

### 45.4 Animation benchmark

Prompt:

```text
Create a 120-frame turntable animation and export a GLB animation clip.
```

Pass:

- frame range correct;
- keyframes exist;
- interpolation correct;
- loop check passes;
- GLB contains animation clip or report explains limitation.

### 45.5 Web scroll benchmark

Prompt:

```text
Create a Three.js/R3F website hero where scrolling moves camera around the product and triggers a glow animation.
```

Pass:

- GLB loads in local viewer;
- camera path JSON exists;
- scroll sections exist;
- glow animation trigger exists;
- desktop and mobile screenshots exist;
- no console errors.

### 45.6 Weak laptop benchmark

Prompt:

```text
Create a cinematic 4K sci-fi scene on safe_laptop profile.
```

Pass:

- refuses/downshifts unsafe 4K;
- creates preview/final safe resolution;
- no heavy volumetrics;
- report explains fallback;
- still produces usable scene.

### 45.7 Reference match benchmark

Prompt:

```text
Match this reference image: dark premium product on reflective surface with blue rim light.
```

Pass:

- reference brief generated;
- palette match attempted;
- camera angle match attempted;
- lighting direction match attempted;
- visual critique lists differences;
- at least one corrective iteration performed.

---

## 46. Hard-Fail Rules V2

A scene must be rejected before final output if any are true:

- no active camera;
- subject not visible from camera;
- render is almost fully black/white by accident;
- main objects have default materials;
- no lighting rig or meaningful illumination;
- requested animation has no keyframes;
- requested GLB cannot load locally;
- requested web hero has no validation screenshot;
- requested reference match has no reference analysis;
- final render uses unsafe profile after preflight warning;
- node/particle/simulation complexity exceeds profile budget;
- exported asset references missing textures;
- final output has no manifest/report.

---

## 47. Final README Requirements After V2

The repository README must clearly say:

1. This is not only a Blender MCP.
2. It is a full Blender agent skill with artistic and technical QA.
3. MCP gives the agent tools; the skill gives the agent rules, taste, tests and iteration behavior.
4. The goal is not magic one-shot perfection; the goal is controlled improvement within max 10 iterations.
5. The system is local-first, open-source-first and no-paid-API by default.
6. Heavy features are profile-gated to protect hardware.
7. Web export is first-class: GLB, camera path, interaction validation, mobile fallback.
8. Materials, camera, lighting, geometry, animation, nodes and compositor must all be validated, not just created.

---

## 48. Updated Definition of Done V2

Project is not done until:

- shader/material system has schemas, presets, validation and export fallback;
- geometry/procedural system has recipes, complexity estimate and deterministic seeds;
- camera system can frame subject, validate coverage and create paths;
- lighting system can create rigs and validate brightness/separation;
- animation system can create and validate turntable, flythrough, exploded view and scroll-linked paths;
- compositor/post system has presets and clipping/overprocessing checks;
- web export can produce GLB + viewer/component + validation screenshots;
- weak hardware profile prevents dangerous renders;
- benchmark suite proves improvement against baseline LLM Blender scripting;
- final report explains every important artistic/technical decision.

---

## 49. Direct Instruction to Coding Agent for V2

Read this whole README before coding. Do not implement a shallow Blender command wrapper. Build the system as a production-grade local skill.

Your implementation order:

1. Create repository structure.
2. Implement `SKILL.md` with mandatory workflow.
3. Implement preflight and profile selection.
4. Implement scene manifest.
5. Implement camera preset + framing validator.
6. Implement lighting preset + brightness validator.
7. Implement material schema + PBR/procedural builders.
8. Implement geometry/modifier recipes.
9. Implement preview render + visual QA report.
10. Implement iteration loop.
11. Implement GLB export validation.
12. Implement web viewer validation.
13. Implement animation presets.
14. Implement compositor/post presets.
15. Add benchmark suite.
16. Add full docs and examples.

Do not mark any task complete unless it has tests and artifacts.
