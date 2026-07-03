# memory — Agent memory & experience engine

## Responsibility
Powers the agent's memory system: stores facts, preferences, conventions, and success experience; provides semantic recall, fusion, self-optimization (dream), and reinforcement learning via experience feedback. Uses pgvector (1024-dim) for vector similarity search.

## Public capabilities

19 capabilities registered:

| Capability | Parameters | Returns | min_role |
|---|---|---|---|
| `memory:save` | `text` (str), `tags` (str?), `source` (str?) | `{id}` | viewer |
| `memory:recall` | `query` (str), `limit` (int?), `expand_chain` (bool?) | `[{id, text, summary, tags, confidence, similarity, ...}]` | viewer |
| `memory:list` | `limit` (int?), `offset` (int?) | `[{id, text, ...}]` | viewer |
| `memory:delete` | `id` (int) | `{id, status}` | viewer |
| `memory:fuse` | `query` (str), `ids` ([int]) | `{fused, source_ids}` | viewer |
| `memory:rethink` | `id` (int), `text` (str), `tags` (str?) | `{id, status}` | viewer |
| `memory:replace` | `id` (int), `old_text` (str), `new_text` (str) | `{id, status}` | viewer |
| `memory:insert` | `id` (int), `text` (str) | `{id, status}` | viewer |
| `memory:dream` | (none) | `{memory: {merged, links_created, decayed}, experience: {merged, deactivated}}` | editor |

Experience and governance capabilities (also registered under memory module):
| `memory:save_experience` | `trigger_condition` (str), `steps` (str\|list), `tools_used` (str?), `source_conversation_id` (int?) | `{id, deduplicated, success_weight}` | viewer |
| `memory:match_experience` | `query` (str), `limit` (int?) | `[{id, trigger_condition, steps, success_weight, similarity, ...}]` | viewer |
| `memory:experience_feedback` | `experience_id` (int), `success` (bool), `note` (str?) | `{id, success_weight, fail_count}` | viewer |
| `memory:overview_stats` | none | `{memory, experience}` aggregate counts | admin |
| `memory:backfill_embeddings` | `dry_run` (bool), `limit` (int?), `owner_id` (int?), `run_dream` (bool?) | record embedding backfill report | admin |
| `memory:backfill_links` | `dry_run` (bool), `limit` (int?), `owner_id` (int?) | missing semantic link report | admin |
| `memory:backfill_chunk_embeddings` | `dry_run` (bool), `limit` (int?), `owner_id` (int?) | chunk embedding backfill report | admin |
| `memory:recall_stable_rules` | `rule_types` (list[str]?) | active stable rules sorted by priority | viewer |
| `memory:recall_chunk` | `query` (str), `limit` (int?) | chunk-level memory hits with provenance | viewer |
| `memory:save_stable_rule` | `rule_type` (str), `content` (str), `priority` (int?), `source` (str?) | `{id, status}` | viewer |

## HTTP endpoints

All under `/api/memory`:

| Method | Path | Purpose |
|---|---|---|
| POST | `/save` | Save a memory (sync embedding + async distill) |
| POST | `/recall` | Hybrid semantic recall (vector → rerank → keyword → chain expand) |
| GET | `/list` | List memories (paginated, newest first) |
| POST | `/delete` | Delete a memory (cascade deletes links) |
| POST | `/fuse` | On-demand fusion of multiple memories into a query-tailored brief |
| POST | `/rethink` | Rewrite a memory entirely |
| POST | `/replace` | Replace a text fragment in a memory |
| POST | `/insert` | Append text to a memory |
| POST | `/dream` | Trigger dream self-optimization (admin only) |

## Data tables

All `agent_*` prefix (shared with agent's `agent_*` convention):

| Table | Purpose |
|---|---|
| `memory_records` | Memory entries with text, summary, tags, confidence, recency_score, embedding (Vector(1024)) |
| `memory_links` | Directed weighted links between memories (from_id, to_id, relation, weight) |
| `memory_experiences` | Success experiences with trigger_condition, steps, tools_used, success_weight, fail_count, trigger_embedding (Vector(1024)) |

## How to query/use
Agent engine calls memory capabilities during conversations: `save` for facts, `recall`/`match_experience` for retrieval, `fuse` for summarization, `dream` for periodic optimization. All calls go through framework `call_capability("memory", "...", {...})`.

## Boundaries/notes
- Embeddings use framework `model_services.get_embedding()` (bge-m3, 1024 dim).
- Embedding writes validate exactly 1024 finite numeric dimensions before storing. Wrong backend/model dimensions are logged and treated as a failed embedding, not fake success.
- Cheap model for distillation/fusion uses `deepseek-v4-flash` via framework gateway.
- Recall pipeline: vector cosine ≥ 0.3 → rerank via framework → top_k → optional chain expansion (links ≥ 0.4).
- Dream runs merge (duplicates ≥ 0.92 similarity), link creation (≥ 0.55), and decay (30d, access < 3).
- Experience dedup threshold = 0.85; net weight = success_weight - fail_count × 2.
- Experience dream also merges near-duplicates and deactivates low-quality (net ≤ 0, fail ≥ 3).
- Post-save processing (embedding + LLM distillation) is offloaded via `SystemTaskQueue` (`memory_post_save` handler).
- All queries scoped by `owner_id` — users only see their own memories.
- `memory_records` and `memory_links` tables are shared memory infrastructure; `memory_experiences` is the experience learning subsystem.
- Deleting or merging a memory also deletes dependent `memory_chunks` and `memory_links`; `run_init()` prunes historical orphan chunks/links and ensures vector indexes for both record and chunk recall.
- Capability inputs clamp/validate `limit`, `offset`, ids, booleans, stable-rule filters, and non-empty text/query fields so bad tool parameters return structured validation errors instead of HTTP 500.

## Latest audit notes

2026-07-03 quality pass:

- Live dry-run found `memory_records`: 43 total, 20 with embeddings, 23 missing; `memory_chunks`: 13 total, all with embeddings. Use `memory:backfill_embeddings` with `dry_run=false` after confirming embedding service health.
- DB shape audit found 1 orphan chunk and 8 orphan links before this pass; module initialization now removes those safely.
- Bad `limit` parameters previously produced 500 for `memory:list`, `memory:recall`, and `memory:recall_chunk`; the module now validates them before SQL execution.
