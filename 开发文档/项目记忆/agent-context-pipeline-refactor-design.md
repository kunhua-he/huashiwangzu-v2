# Agent Context Pipeline Refactor Design

## Background

The current Agent context assembly path has grown into a large orchestration function. It already handles:

- event projection from `agent_events`
- token budget enforcement
- compaction and snapshots
- workflow strategy injection
- success experience injection
- skills injection
- layered memory injection
- diagnostics collection

This makes the code difficult to extend, hard to test, and fragile to modify. The goal of this refactor is not to minimize changes, but to make the system more engineering-grade: stable, reusable, testable, and easy to extend with rule-based or LLM-based logic later.

## Goals

1. Split context assembly into explicit stages.
2. Make tool-result reduction a first-class subsystem.
3. Make success experience a workflow-advice system, not a raw-data replay system.
4. Preserve current behavior while refactoring.
5. Make each stage independently testable.
6. Keep rule-based algorithms as the default path, with LLM only as fallback.

## Problems With The Current Design

### 1. `assemble_context()` does too much

`modules/agent/backend/engine/engine.py` currently owns:

- agent config resolution
- event projection
- compression trigger decisions
- skills injection
- token budget reduction
- layered memory injection
- workflow injection
- success experience injection
- diagnostics assembly

This is not a sustainable boundary. Adding one more policy makes the function harder to understand and riskier to change.

### 2. Injection order is implicit

Some logic mutates the first system message in place. Some logic appends to system content before assembly. Tool results are represented structurally through event projection. The precedence rules are not obvious.

### 3. Tool results are not reduced systematically

Large tool outputs can still enter context in a mostly raw form. That is acceptable for small payloads, but not engineering-grade for local models or long-lived conversations.

### 4. Success experience is currently too close to data replay

The current experience path is closer to matching previous data than extracting reusable workflow advice. What we really want is:

- what sequence of tools worked best
- what order minimized retries
- what advice should be injected as prompt-level guidance

That is a workflow recipe, not raw event replay.

## Proposed Architecture

### Overview

```
project_history
    -> reduce_context
    -> inject_context_layers
    -> assemble_context
```

### 1. `project_history`

Responsibilities:

- read `agent_events`
- project events into model messages
- preserve atomic tool turns
- preserve compaction summaries

Suggested location:

- `modules/agent/backend/engine/context_projector.py`

### 2. `reduce_context`

Responsibilities:

- enforce token budget
- apply rule-based compression
- optionally fall back to LLM-based compression
- perform hard truncation if all else fails
- keep diagnostics about what was removed and why

Suggested location:

- `modules/agent/backend/engine/context_reducer.py`

### 3. `inject_context_layers`

Responsibilities:

- inject workflow advice
- inject success experience advice
- inject tool-derived context variables
- inject skills/system guidance

Suggested location:

- `modules/agent/backend/engine/context_injectors/`

### 4. `assemble_context`

Responsibilities:

- orchestrate the pipeline
- keep order stable
- produce final `messages` and `diagnosis`
- avoid embedding policy logic directly

Suggested location:

- `modules/agent/backend/engine/context_pipeline.py`
- `engine.py` should become a thin compatibility wrapper

## Tool Result Compression Strategy

### Principle

Use rules first. Use LLM only when rules cannot produce a compact enough representation.

### Recommended Rule Set

#### A. Structured search/list results
Examples:

- `list_files`
- `search`
- `query`

Keep:

- total count
- the first N items
- stable identifiers
- key fields like `id`, `name`, `type`, `size`

Drop or compress:

- verbose repetitive metadata
- full arrays when they are long

#### B. Describe / schema-like results
Examples:

- `skill_describe`
- schema inspection

Keep:

- parameters
- required fields
- short summary

Compress:

- large prose descriptions

#### C. Content / document results
Examples:

- file content
- document extraction

Keep:

- title
- head and tail
- detected structure
- important numeric / named entities

Compress:

- middle sections
- repeated paragraphs
- raw formatting noise

#### D. JSON-heavy tool results
Keep only schema-approved keys. Avoid replaying the full payload unless the model truly needs it.

### Fallback Chain

1. Rule compression
2. Head/tail truncation
3. LLM summary
4. Hard truncate

This mirrors the engineering direction from Claude/Letta-style systems, but stays simpler for our backend.

## Success Experience Strategy

### Current problem

The existing experience system is too close to raw history matching.

### What we actually want

A **workflow recipe** system:

- When the user intent is X
- Prefer tool sequence Y
- Avoid path Z
- Use advice A to save token and retries

### Recommended data model concept

#### `workflow_recipe`

Fields:

- intent label
- matched trigger text
- recommended tool sequence
- expected outcome
- failure fallback
- average cost / average time
- last success time
- success count
- confidence / priority

### Recommendation policy

- rank by success rate
- rank by speed
- rank by recency
- decay older recipes over time

### Prompt injection form

Inject as concise prompt-level advice, not raw logs.

Example:

```text
【推荐流程】
当目标是“查看桌面文件”时，优先：skill_list -> skill_describe -> skill_use。
若已有 file_id，则直接进入读取/打开，不要重复查找。
```

This is much more reusable than replaying prior payloads.

## Context Variables

The current `context_vars.py` is a good seam and should become a dedicated injector.

Use it for:

- `file_id`
- `folder_id`
- current document name
- desktop file list hints
- other tool-derived stable variables

This is the bridge from raw tool output to compact prompt advice.

## Workflow Injection

`workflow_strategy.py` is already a good seam. It should be kept, but moved behind a dedicated injector stage.

Responsibilities:

- detect workflow keywords
- map to workflow label
- emit workflow advice
- keep diagnostics

## Reuse Instead Of Rewrite

The refactor should preserve these existing building blocks:

- `event_store.project_to_messages()` for event projection
- `compressor.py` and `context_snapshot.py` for compaction/snapshot
- `workflow_strategy.py` for workflow advice
- `experience_memory.py` for success-memory retrieval
- `context_vars.py` for tool-derived variables

The main change is not the features themselves, but **the boundaries**.

## Recommended Refactor Sequence

### Phase 1: Extract pipeline skeleton

- create `context_pipeline.py`
- keep behavior identical
- move orchestration out of `engine.py`

### Phase 2: Extract injectors

- workflow injector
- experience injector
- context vars injector
- skills injector

### Phase 3: Add reducer layer

- structured tool-result compression
- fallback truncation
- LLM summary fallback

### Phase 4: Shrink `assemble_context()`

- make it a thin orchestrator
- keep only routing and diagnostics aggregation

## Testing Strategy

### Unit tests

#### `context_projector`

- tool turns stay atomic
- compaction summaries are preserved
- orphan tool results do not break ordering

#### `context_reducer`

- budget enough -> no reduction
- budget tight -> rule compression
- rule compression insufficient -> LLM fallback
- fallback failure -> hard truncate

#### `experience_injector`

- recipe ranking by success / speed / recency
- injection only into system block
- empty or malformed experience returns safe no-op

#### `workflow_injector`

- keyword match injects guidance
- overlapping matches resolve deterministically
- no system message does not crash

#### `context_vars_injector`

- extracts stable variables from tool results
- formats them into compact prompt text
- ignores noisy / unstable payload fields

### Integration tests

- full `assemble_context` order is stable
- workflow + experience + context vars all appear in the correct order
- budget reduction happens before final injection or after, according to the chosen policy
- diagnosis fields remain stable

### Regression tests

- desktop file flow: `list_files -> describe -> use`
- document flow: open, summarize, follow-up question
- long tool result flow: compressed rather than flooding context

## Migration Safety

To avoid regression:

1. Keep `assemble_context()` behavior stable in the first pass.
2. Write tests before moving logic.
3. Move one stage at a time.
4. Keep the old path behind the new pipeline until tests pass.
5. Preserve diagnostics shape for existing UI/log consumers.

## Why This Is More Engineering-Grade

- Single responsibility per stage
- Easy to test and swap algorithms
- Rule compression is deterministic and cheap
- LLM compression becomes a fallback, not the main path
- Success experience becomes reusable prompt advice
- Future changes become additive, not invasive

## Recommended Next Step

Implement the pipeline skeleton first, then migrate the existing workflow / experience / context-vars logic into it, and only after that add the tool-result reducer.
