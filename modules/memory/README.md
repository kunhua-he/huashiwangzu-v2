# memory — Agent memory & experience engine

## Responsibility
Powers the agent's memory system: stores facts, preferences, conventions, and success experience; provides semantic recall, fusion, self-optimization (dream), and reinforcement learning via experience feedback. Uses pgvector (1024-dim) for vector similarity search.

## Public capabilities

9 capabilities registered:

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

Experience capabilities (also registered under memory module):
| `memory:save_experience` | `trigger_condition` (str), `steps` (str\|list), `tools_used` (str?), `source_conversation_id` (int?) | `{id, deduplicated, success_weight}` | viewer |
| `memory:match_experience` | `query` (str), `limit` (int?) | `[{id, trigger_condition, steps, success_weight, similarity, ...}]` | viewer |
| `memory:experience_feedback` | `experience_id` (int), `success` (bool), `note` (str?) | `{id, success_weight, fail_count}` | viewer |

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
| `agent_memory` | Memory entries with text, summary, tags, confidence, recency_score, embedding (Vector(1024)) |
| `memory_links` | Directed weighted links between memories (from_id, to_id, relation, weight) |
| `agent_experiences` | Success experiences with trigger_condition, steps, tools_used, success_weight, fail_count, trigger_embedding (Vector(1024)) |

## How to query/use
Agent engine calls memory capabilities during conversations: `save` for facts, `recall`/`match_experience` for retrieval, `fuse` for summarization, `dream` for periodic optimization. All calls go through framework `call_capability("memory", "...", {...})`.

## Boundaries/notes
- Embeddings use framework `model_services.get_embedding()` (bge-m3, 1024 dim).
- Cheap model for distillation/fusion uses `deepseek-v4-flash` via framework gateway.
- Recall pipeline: vector cosine ≥ 0.3 → rerank via framework → top_k → optional chain expansion (links ≥ 0.4).
- Dream runs merge (duplicates ≥ 0.92 similarity), link creation (≥ 0.55), and decay (30d, access < 3).
- Experience dedup threshold = 0.85; net weight = success_weight - fail_count × 2.
- Experience dream also merges near-duplicates and deactivates low-quality (net ≤ 0, fail ≥ 3).
- Post-save processing (embedding + LLM distillation) is offloaded via `SystemTaskQueue` (`memory_post_save` handler).
- All queries scoped by `owner_id` — users only see their own memories.
- `agent_memory` and `memory_links` tables are shared memory infrastructure; `agent_experiences` is the experience learning subsystem.
