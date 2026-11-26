# EDITH Memory System — Technical Architecture, Data Flow & Debugging Guide

**Project:** EDITH  
**Document type:** Engineering reference / troubleshooting manual  
**Implementation baseline:** Memory-system code and runtime evidence shared in the EDITH project conversations through **15 November 2026**  
**Repository root:** `D:\Edith`  
**Primary implementation language:** Python  
**Persistence:** SQLite  
**Local semantic retrieval:** Sentence Transformers embeddings + cosine similarity  
**LLM integration:** Ollama (local model)

> **Important source-of-truth note**
>
> This document is based on the actual EDITH memory code and logs shared during development, not a fresh checkout of `D:\Edith`. It documents the verified implementation and explicitly labels areas where the exact source implementation was not available. If the current repository differs, the repository wins. In particular, the detailed internals of `extractor.py`, `memory_manager.py`, the worker implementations, and every SQL table definition were not present in the inspected source excerpts; those sections explain their known responsibility without inventing implementation details.

---

# 1. Purpose of the Memory System

EDITH's memory system exists to let the assistant use information from previous interactions rather than treating every request as an isolated conversation.

It has two distinct memory representations:

1. **Conversation memory** — the original messages exchanged between the user and EDITH. These preserve what was actually said, who said it, when it was said, and which session it belonged to.
2. **Structured memory** — compact facts or preferences represented as typed key/value records. For example:
   - `type = project`
   - `key = favorite_project`
   - `value = edith`

The system also creates semantic embeddings for messages so that a future query can retrieve messages based on meaning rather than exact keyword matches.

The retrieved information is formatted into a text context and supplied to the local LLM. The memory database does not itself write the final natural-language answer. It supplies evidence; Ollama generates the response using that evidence and the assistant's behavior/system instructions.

## 1.1 What the system is intended to do

- Persist conversation messages across sessions.
- Retrieve semantically related previous messages.
- Retrieve messages from a requested historical time range.
- Keep compact structured facts and preferences.
- Include surrounding conversation messages when a matching message needs context.
- Make recently received messages searchable even while background persistence/indexing is pending (in the version that contains the pending-message cache).
- Build a clearly labelled memory context for the LLM.
- Work locally without requiring a hosted memory service.

## 1.2 What it does not automatically guarantee

Memory retrieval is not the same as perfect human recall.

- A stored message may not be retrieved if its embedding is weakly related to the query.
- A structured fact may exist but not be selected by the current keyword-based structured-memory matcher.
- A retrieved memory may be ignored or misinterpreted by the LLM if prompt grounding is weak.
- A conversation record is evidence of what was said, not proof that the statement was objectively true.
- Semantic similarity is not a truth score.
- The existence of an `extractor.py` module does not, by itself, prove that every conversation is successfully converted into structured memories.

---

# 2. High-Level Architecture

```text
                  USER INPUT
                      |
                      v
            Conversation / Assistant Layer
                      |
          +-----------+------------+
          |                        |
          v                        v
   Save conversation          Memory extraction
   message record             / management path
          |                        |
          v                        v
    message_store.py          extractor.py
          |                        |
          v                        v
       database.py        memory_manager.py
          |                        |
          |                        v
          |                structured_service.py
          |                        |
          |                        v
          |                structured_store.py
          |                        |
          +------------+-----------+
                       |
                       v
                 SQLite database
                       |
          +------------+-------------+
          |                          |
          v                          v
    vector_store.py             Structured records
          ^
          |
    embeddings.py
          ^
          |
     EmbeddingService
          |
          v
      search.py
          |
          v
     MemoryService
          |
          +--> semantic retrieval
          +--> historical retrieval
          +--> structured-memory matching
          +--> conversation-context expansion
          |
          v
  build_memory_context() / get_context()
          |
          v
    Conversation service
          |
          v
       Ollama client
          |
          v
      EDITH response
```

This diagram shows the responsibilities and connections established by the shared code/module map. It does not assert that every arrow is a synchronous call or that all extraction work happens in the same thread. Worker scheduling and exact call order must be checked in the current source.

---

# 3. Two Memory Layers: Conversation vs Structured

Understanding this distinction is the most important part of debugging EDITH memory.

## 3.1 Conversation memory

Conversation memory stores message-level records.

A record returned by the memory layer can contain fields such as:

| Field | Meaning |
|---|---|
| `message_id` | Persistent database message identifier; pending records may have `None` |
| `session_id` | Conversation/session association |
| `role` | `user` or `assistant` |
| `content` | Original message text |
| `created_at` | Timestamp, represented in the code as UTC-style text |
| `score` | Semantic similarity score when returned by semantic search |
| `is_match` | Marks a direct search result versus surrounding context in the newer context-expansion path |
| `pending` | Indicates that the result is still in the in-memory pending-message path |
| `pending_id` | Temporary identifier for a pending message |

Conversation memory is the detailed record. It is useful for questions such as:

- “What did I tell you about this project?”
- “What did we discuss yesterday?”
- “What was the exact model I mentioned?”
- “What did you recommend after I showed you the logs?”

## 3.2 Structured memory

Structured memory stores a compact representation of selected information.

The context builder expects records with at least:

- `type`
- `key`
- `value`

Example context output:

```text
KNOWN FACTS AND PREFERENCES
- project: favorite_project = edith
```

Structured memory is intended for direct facts and preferences that should be easy to identify without retrieving an entire conversation.

It is useful for questions such as:

- “What is my favorite project?”
- “Which programming stack am I using?”
- “What is my preferred architecture?”

The exact extraction criteria, confidence rules, conflict-resolution policy, and deletion semantics of the current extractor were not available in the inspected code excerpts. Do not assume those behaviors without checking `extractor.py`, `memory_manager.py`, and `structured_store.py`.

## 3.3 Why both layers are necessary

A structured fact is compact but loses surrounding detail. A conversation message preserves detail but can be expensive and noisy to search through.

For example:

**Structured fact**
```text
project | favorite_project | edith
```

**Conversation evidence**
```text
Prayag: My favorite project is EDITH and I am working on it
and I am building it in Python.
```

The structured record can answer the simple question quickly. The conversation record can answer the follow-up about what was said regarding how the project is being built.

---

# 4. Module Map and Responsibility

The following module names were present in the EDITH memory module map shared during development.

| Module | Responsibility |
|---|---|
| `database.py` | Shared SQLite database setup/connection and database-level operations |
| `message_store.py` | Conversation message persistence |
| `vector_store.py` | Persistent embedding/vector records and similarity-search support |
| `embeddings.py` | Embedding model/service wrapper |
| `search.py` | Semantic search, historical search, indexing and conversation-context expansion |
| `service.py` | Main conversation-memory API and context construction |
| `structured_store.py` | Persistence operations for structured facts |
| `structured_service.py` | Service-level structured-memory operations |
| `time_parser.py` | Detects time/date intent and produces a time range |
| `extractor.py` | Memory extraction component; exact implementation details require source inspection |
| `memory_manager.py` | Memory orchestration/management component; exact implementation details require source inspection |
| Worker modules | Background processing; exact worker names and queue contracts must be verified in the repository |
| `conversation_service.py` | Connects conversation handling with memory and response generation |
| `ollama_client.py` | Local LLM client used to generate assistant responses |

## 4.1 Debug by ownership

When something breaks, identify the responsible layer before changing code.

- Message missing from database → inspect `message_store.py` and `database.py`.
- Message exists but no embedding → inspect `embeddings.py`, `vector_store.py`, and the indexing path in `search.py`.
- Similar messages are not found → inspect `search.py`, embedding generation, threshold, and query text.
- Date-specific recall fails → inspect `time_parser.py`, time-range search, and timestamp conventions.
- Structured fact is absent → inspect extraction and structured persistence modules.
- Memory exists but is not sent to the LLM → inspect `service.py` and `conversation_service.py`.
- Memory is sent but the answer ignores it → inspect the Ollama prompt and grounding instructions in the conversation/LLM layer.

---

# 5. SQLite Persistence Layer

EDITH uses SQLite as its local persistent memory database.

The memory module map includes `database.py`, `message_store.py`, `vector_store.py`, and `structured_store.py`. The exact current database filename, full DDL, column constraints, indexes, foreign keys, and migration strategy were not included in the inspected source excerpts. Confirm these directly in `database.py` and the store modules before performing schema changes.

## 5.1 Logical data groups

The implementation has at least three logical data categories:

1. Conversation messages.
2. Embedding/vector data associated with messages.
3. Structured memory records.

The reported database diagnostic on 15 November 2026 showed:

| Diagnostic | Reported count |
|---|---:|
| Conversation messages | 226 |
| Embeddings | 226 |
| Structured memories | 15 |

These are historical observed counts, not a guarantee of the current database state.

## 5.2 Message persistence

The shared `MemoryService.store_message()` implementation calls:

```python
message_id = save_message(
    session_id,
    role,
    content,
)
```

The save operation is delegated to `app.memory.message_store`.

The inspected implementation validates the role against `user` and `assistant`, and rejects empty content. One earlier version shown in the conversation did not contain those validations, so use the current checked-out `service.py` as the authority.

## 5.3 Embedding persistence

In the inspected 15 November implementation, `store_message()` then:

1. Imports `save_embedding` from `app.memory.vector_store`.
2. Generates an embedding using `self.embedding_service.encode(content)`.
3. Saves the embedding against the newly created `message_id`.
4. Returns the message ID.

That excerpt shows embedding creation after message persistence for the call path represented there. It does not prove that every background worker uses exactly the same sequence.

## 5.4 Database integrity checks

Useful checks to run against the actual SQLite database:

- Count message rows.
- Count embedding rows.
- Count structured-memory rows.
- Find messages with no corresponding embedding.
- Find embeddings whose message no longer exists.
- Find duplicate message content/timestamps where duplicates are unexpected.
- Inspect indexes on message timestamps, session identifiers, and embedding-to-message lookup columns.
- Confirm that all timestamps use a consistent format and timezone convention.

Do not run destructive cleanup SQL until the table names, primary keys, and foreign-key relationships have been verified from the live schema.

---

# 6. Embedding Generation

Semantic retrieval depends on converting text into numerical vectors.

## 6.1 Component

`app.memory.embeddings.EmbeddingService` is instantiated by `MemoryService`:

```python
self.embedding_service = EmbeddingService()
```

The service exposes `encode(text)` in the inspected code. The pending-message path also accesses `self.embedding_service.model.encode(...)` directly for a batch of texts.

The exact embedding model name, model revision, vector dimension, normalization configuration, and device selection were not present in the inspected source excerpts. Verify them in `embeddings.py` rather than assuming a particular Sentence Transformers model.

## 6.2 Why embeddings are required

Keyword search asks whether words overlap.

Semantic search asks whether two pieces of text are close in vector space.

Example:

```text
Stored: "My favorite project is EDITH."
Query:  "Which project do I like the most?"
```

The wording differs, but the meaning is similar. An embedding model can map both into vectors whose cosine similarity is relatively high.

## 6.3 Important compatibility rule

The query embedding and stored message embeddings must be produced by compatible model/configuration settings.

If the embedding model changes, old vectors may no longer be comparable to new vectors. A model migration therefore requires a controlled re-indexing plan. Do not simply change the model name and continue mixing old and new vectors.

## 6.4 Embedding failure symptoms

| Symptom | Likely area to inspect |
|---|---|
| Message stored but not searchable | Embedding generation/save path |
| Embedding count lower than message count | Failed or skipped indexing |
| Similarity scores unexpectedly low | Model mismatch, text preprocessing, vector normalization, or query quality |
| Search crashes on vector dimensions | Mixed embedding models/dimensions or malformed vector data |
| First query is unusually slow | Model loading/initialization |
| Repeated high memory use | Repeated model initialization or multiple service instances |

A known concern from the 15 November diagnostic was repeated embedding-model initialization. Check whether `EmbeddingService` is instantiated more than once across workers/services. Do not create additional instances merely to make a new feature work.

---

# 7. Vector Store and Semantic Search

## 7.1 Search entry point

In the later inspected implementation, `MemoryService.search()` delegates to:

```python
return search_memory(
    text,
    self.embedding_service,
    top_k=top_k,
    min_score=min_score,
)
```

The earlier implementation shown on 14 November performed the steps more explicitly:

1. Generate query embedding once.
2. Call `search_similar_memories(...)` for persistent records.
3. Retrieve in-memory pending user messages.
4. Batch-encode pending message content.
5. Compute cosine similarity using `sentence_transformers.util.cos_sim`.
6. Combine persistent and pending results.
7. Sort by descending score.
8. Return the first `top_k` results.

The code excerpts therefore show an implementation evolution. The newer service delegates more of the search behavior to `search.py`; the pending-cache logic was visible in the earlier version. Confirm whether pending-message support remains active in the current checkout before relying on it.

## 7.2 Parameters

The inspected service signatures use:

| Parameter | Meaning | Observed default |
|---|---|---:|
| `top_k` | Maximum number of search results requested | 10 or 20 depending on method/version |
| `min_score` | Minimum semantic similarity score | 0.30 in the later code |
| `window` | Number of neighboring messages to include around a match | 1 |
| `max_messages` | Maximum expanded conversation messages | 30 |
| `max_anchors` | Maximum direct search matches used as expansion anchors | 5 |

The defaults differ across methods and historical code versions. Check the actual call site and current `service.py` signature when debugging. Do not assume a single global `top_k` or threshold.

## 7.3 Meaning of `min_score`

`min_score` is a retrieval cutoff. A result below the threshold is excluded.

- Too high: relevant memories can be missed.
- Too low: unrelated memories can enter the context.
- A score is a similarity measure, not a confidence that the stored statement is true.

A threshold of `0.30` was present in the later service code. Earlier development had used `0.45` in at least one search path. These values should not be treated as interchangeable without testing the current embedding model and corpus.

## 7.4 `top_k`

`top_k` limits how many results are returned from a search path.

A small value may hide useful evidence. A very large value can flood the LLM context with unrelated messages and increase prompt size.

The later `get_relevant_memories()` path calls `expand_conversation_context()` with a maximum of 30 messages and at most 5 match anchors. This means the final context can contain more messages than the number of direct semantic matches.

## 7.5 Sorting

The earlier pending-aware search combined persistent and pending results and sorted them by descending semantic score.

Historical time-range search sorted by timestamp instead. These are different ordering rules for different query types:

- General semantic search: relevance ordering.
- Historical range retrieval: chronological ordering.

Do not “fix” chronological ordering by sorting historical records by semantic score unless the desired behavior has deliberately changed.

---

# 8. Conversation Context Expansion

A matching message can be difficult to understand without the messages immediately before or after it.

The later `get_relevant_memories()` implementation calls:

```python
return expand_conversation_context(
    results,
    window=1,
    max_messages=30,
    max_anchors=5,
)
```

## 8.1 What this is for

Suppose the direct match is:

```text
Prayag: What did we decide to build next?
```

The surrounding messages may contain the actual decision. Context expansion allows the retrieval layer to include neighboring messages rather than returning only the matching line.

## 8.2 `MATCH` and `CONTEXT`

The newer context builder labels results:

- `MATCH` — a direct retrieval result.
- `CONTEXT` — a surrounding message included to preserve conversation meaning.

Example:

```text
[MATCH]   [timestamp] Prayag: My favorite project is EDITH.
[CONTEXT] [timestamp] EDITH: What are you trying to build next?
```

This distinction matters when reading debug output. A `CONTEXT` record was not necessarily independently similar to the query; it may have been included because it was adjacent to a direct match.

## 8.3 Debugging expansion

If the correct match is present but the surrounding messages are wrong or missing:

1. Confirm the correct `message_id` is returned by the direct search.
2. Inspect the session identifier and chronological ordering.
3. Inspect the implementation of `expand_conversation_context()`.
4. Confirm the configured window and limits.
5. Check whether messages from separate sessions are accidentally mixed.

Do not tune embedding thresholds to fix a conversation-neighbor problem. These are separate stages.

---

# 9. Historical / Date-Specific Memory Retrieval

EDITH has a time-aware retrieval path.

## 9.1 Time parser

`app.memory.time_parser.get_time_range(text)` is used by `MemoryService.get_relevant_memories()`.

The flow is:

```text
User query
   |
   v
get_time_range(query)
   |
   +---- time range found ----> search_in_time_range(...)
   |
   +---- no time range -------> semantic search(...)
```

Examples of date intent include “yesterday,” “on October 9,” or “last week,” depending on what the parser currently supports. The exact supported phrases and parser rules must be verified in `time_parser.py`.

## 9.2 Time-range search

The service delegates historical search to:

```python
search_messages_in_range(
    text,
    start_time,
    end_time,
    self.embedding_service,
    top_k=top_k,
    min_score=min_score,
)
```

In the earlier pending-aware implementation, messages still in the pending cache were also checked against the time interval and appended with a score of `1.0`. That score means the pending message was included by the date-range path; it is not a semantic similarity measurement.

## 9.3 UTC and India Standard Time

The context builder uses:

```python
ZoneInfo("Asia/Kolkata")
```

It parses the start of the requested time range as UTC and converts it to India Standard Time for the human-readable requested date.

The inspected code formats message timestamps with UTC-style strings. The date parser, database storage, and search SQL must all agree on the same convention. A timezone mismatch can make “yesterday” retrieve the wrong day or no messages.

## 9.4 Historical context output

The context builder creates a dedicated section:

```text
HISTORICAL CONVERSATION RECORDS
Requested date: YYYY-MM-DD (India Standard Time)
The following messages were retrieved from the requested period.
MATCH means a direct retrieval result.
CONTEXT means it is surrounding conversation.
```

Then it appends chronological message lines with speaker and timestamp.

## 9.5 Historical recall troubleshooting

If EDITH recalls the wrong date:

1. Print the raw user query.
2. Print the exact `get_time_range()` result.
3. Print `start_time` and `end_time`.
4. Confirm whether those values are UTC or local time.
5. Inspect a known message timestamp directly in SQLite.
6. Run the time-range SQL/search independently.
7. Confirm the returned records are sorted chronologically.
8. Inspect the context text before it reaches Ollama.

Do not start by changing the LLM prompt. First establish whether the correct records were retrieved.

---

# 10. Structured Memory Retrieval

The later inspected `MemoryService` includes `_memory_terms()` and `search_structured_memories()`.

## 10.1 Query-term normalization

`_memory_terms(text)`:

1. Converts alphanumeric characters to a normalized string.
2. Uses `casefold()` for case-insensitive matching.
3. Splits into words.
4. Removes words of length 2 or less.
5. Removes a stop-word set such as `what`, `my`, `the`, `is`, `you`, `about`, and `please`.

This reduces noise from common question wording.

## 10.2 Matching rule

The inspected implementation:

1. Loads all structured records with `self.structured_memory.get_all()`.
2. Builds normalized terms from the query.
3. Builds normalized terms from each memory's `key` and `value`.
4. Intersects query terms and memory terms.
5. Includes a record if there is at least one matching term and the number of matching terms is at least `min(2, len(query_words))`.

In plain language:
- If the query has one meaningful term, one match is enough.
- If the query has two or more meaningful terms, at least two matching terms are required.

This is a lightweight lexical matcher, not semantic vector search.

## 10.3 Consequence

A structured memory can exist in SQLite and still not be selected if the query uses words that do not overlap with its key/value terms.

For example, a record with key `favorite_project` and value `edith` may match a query containing “project” or “edith”, but a query phrased only as “what do I love building?” may not overlap enough after stop-word removal.

That is a retrieval limitation, not necessarily a storage failure.

## 10.4 Debug structured memory in stages

- `get_all()` returns the record → persistence is working.
- `_memory_terms(query)` contains useful terms → query normalization is working.
- `_memory_terms(key + value)` contains expected terms → record normalization is working.
- Intersection is non-empty → lexical matching has a candidate.
- Candidate is included in `search_structured_memories()` output → structured retrieval is working.
- Candidate appears under `KNOWN FACTS AND PREFERENCES` → context builder is working.
- Candidate appears in the prompt sent to Ollama → conversation integration is working.

This staged method isolates the failure instead of changing multiple layers at once.

---

# 11. Memory Context Builder

`MemoryService.build_memory_context()` is the boundary between retrieval and the LLM.

It returns a text string, not a database object.

## 11.1 General query path

When `get_time_range(text)` returns no historical range:

1. Retrieve relevant conversation memories.
2. Retrieve relevant structured memories.
3. If structured records exist, add `KNOWN FACTS AND PREFERENCES`.
4. If conversation records exist, add `RELEVANT MEMORIES FROM PREVIOUS CONVERSATIONS`.
5. Label direct matches and surrounding context.
6. Join the sections with blank lines.
7. If no sections exist, return `No relevant memory was found.`

## 11.2 Historical query path

When a time range is detected:

1. Retrieve messages from the requested time range.
2. Convert the requested UTC start time to an India-local date for display.
3. Add `HISTORICAL CONVERSATION RECORDS`.
4. Include the matching and surrounding messages with timestamps and speaker names.
5. If no records are returned, state that no relevant messages were found in the requested period.

The inspected implementation uses the historical branch instead of the general structured-memory branch. Therefore, do not assume structured facts are always included in a date-specific context.

## 11.3 Why the context builder matters

A memory can be stored and successfully retrieved but still fail to help EDITH if it is not formatted or passed to the LLM.

The context builder is therefore a critical boundary. Debug its output independently of the LLM response.

## 11.4 Golden debugging rule

Always inspect the exact memory context sent to Ollama.

If the correct fact is absent, debug storage/retrieval/context construction.

If the correct fact is present but EDITH answers incorrectly, debug prompt instructions, message assembly, model behavior, or response parsing. Do not rewrite the database search code to fix a prompt-grounding problem.

---

# 12. LLM Grounding and Memory Use

Memory retrieval and answer generation are separate responsibilities.

```text
Memory database
      |
      v
MemoryService.get_context(query)
      |
      v
Formatted memory text
      |
      v
Conversation service / prompt assembly
      |
      v
Ollama client
      |
      v
Generated answer
```

A previous runtime test demonstrated this distinction:

The memory context sent to Ollama contained:

```text
KNOWN FACTS AND PREFERENCES
- project: favorite_project = edith

RELEVANT MEMORIES FROM PREVIOUS CONVERSATIONS
[MATCH] Prayag: My favorite project is edith and I am working on it
and I am building it in python
```

This showed that structured retrieval and semantic retrieval could both provide relevant evidence. During earlier development, the LLM initially failed to use retrieved context reliably; the behavior prompt was subsequently corrected.

## 12.1 Grounding requirements for the prompt

The LLM instruction should make clear that:

- Supplied memory context is evidence from previous interactions.
- `MATCH` is a direct retrieval result.
- `CONTEXT` is surrounding conversation.
- A stored user statement should not be silently converted into a different fact.
- If evidence is absent or insufficient, EDITH should say it cannot find enough information.
- EDITH should not claim to remember details that were not supplied in the current context or otherwise available to it.

The exact current prompt text is not reproduced here because the latest full prompt source was not included in the inspected excerpts.

## 12.2 Debug the LLM boundary

Capture, in order:

1. User query.
2. `MemoryService.get_context()` output.
3. Final assembled prompt/messages.
4. Raw Ollama response.
5. Parsed assistant response.

This shows whether the failure occurred before the LLM, during prompt assembly, or during generation.

---

# 13. Pending Messages and Background Persistence

An earlier `service.py` version included a pending-message cache.

This section is important because the inspected code shows two versions of the service with different behavior.

## 13.1 Why pending messages existed

A message may be received now but not yet persisted/indexed by a background worker. If EDITH immediately asks memory to retrieve it, the persistent search might not see it.

The pending cache made recent messages temporarily available to retrieval before background persistence completed.

## 13.2 Earlier implementation

The earlier code included:

- `self._pending_messages = {}`
- `self._pending_lock = threading.RLock()`
- `register_pending_message(...)`
- `mark_message_indexed(pending_id)`
- `get_pending_messages()`

The pending record included:

- `pending_id`
- `session_id`
- `role`
- `content`
- `created_at`

The lock protected concurrent access from the conversation thread and background worker.

## 13.3 Pending-aware semantic search

The earlier implementation:
- Queried persistent vectors.
- Selected pending `user` messages.
- Encoded pending text in a batch.
- Calculated cosine similarity against the query vector.
- Combined persistent and pending results.
- Sorted by score.
- Returned the top results.

The earlier historical path also appended pending records whose timestamps fell inside the requested range.

## 13.4 Pending lifecycle

The intended lifecycle in the code comments was:

```text
Message arrives
    |
    v
register_pending_message()
    |
    +----> Immediately visible to retrieval
    |
    v
Background persistence/indexing
    |
    +----> save message
    +----> create/save embedding
    |
    v
mark_message_indexed()
    |
    v
Remove temporary pending record
```

The exact worker implementation and failure/retry behavior were not available in the inspected source. Confirm how it handles exceptions and whether it always calls `mark_message_indexed()` only after both the database message and embedding are safely available.

## 13.5 Pending-cache failure modes

- If the pending record is removed too early, the message can temporarily disappear from retrieval.
- If it is never removed, the same message may appear in both pending and persistent results.
- If the worker saves the message but fails to save its embedding, the database can contain a message that semantic search cannot find.
- If the worker retries without an idempotency check, duplicate messages or embeddings may be created.
- If the application exits before background work completes, pending-only records may be lost.

Because the later inspected service excerpt did not include pending-cache methods, verify whether this path remains in the current version before debugging it.

---

# 14. Extraction and Memory Management Components

The EDITH memory module map includes:

- `extractor.py`
- `memory_manager.py`
- `structured_store.py`
- `structured_service.py`
- worker modules

These names establish that the project has dedicated extraction and management components. However, the full source for these modules was not included in the inspected excerpts. This document therefore does not invent their prompt, JSON schema, filtering logic, confidence threshold, deduplication algorithm, or conflict-resolution rules.

## 14.1 Conceptual responsibility boundary

The expected responsibility separation is:

- **Extractor:** identify candidate facts or memory items from conversation content.
- **Memory manager:** coordinate memory lifecycle and operations.
- **Structured service:** expose structured-memory operations to the rest of the application.
- **Structured store:** persist and retrieve structured records.
- **Workers:** run any deferred/background work assigned to them.

Treat this as a responsibility map, not a verified line-by-line call graph.

## 14.2 How to debug extraction

When a fact is missing from structured memory, inspect the pipeline in this order:

1. Was the source user message persisted?
2. Was the extraction job created or invoked?
3. Did the extractor receive the correct message text?
4. Did the extractor return a candidate?
5. Was the candidate parsed/validated?
6. Did the memory manager accept or reject it?
7. Did the structured service receive the accepted item?
8. Did the structured store persist it?
9. Does `get_all()` return it?
10. Does `search_structured_memories()` select it for the current query?
11. Does `build_memory_context()` include it?

Log each stage with a message ID or another traceable identifier. Do not log only “memory extraction completed”; that does not tell you where a candidate disappeared.

## 14.3 Debugging extraction versus retrieval

These are different failure classes:

| Situation | Diagnosis |
|---|---|
| Candidate never extracted | Extraction input/model/prompt issue |
| Candidate extracted but rejected | Validation/manager policy |
| Candidate accepted but not stored | Structured persistence issue |
| Candidate stored but not selected | Structured retrieval matcher |
| Candidate selected but absent from context | Context builder issue |
| Candidate in context but answer wrong | LLM grounding issue |

---

# 15. Conversation Service Integration

The module map includes `conversation_service.py` and `ollama_client.py`.

The memory system must be connected to the active conversation path. Having a working database alone is not enough.

A typical interaction should have these logical stages:

1. Receive the user message.
2. Make the current message available to the memory layer according to the active persistence path.
3. Retrieve memory relevant to the current query.
4. Build the memory context.
5. Assemble the LLM prompt/messages.
6. Call the local Ollama client.
7. Receive the assistant response.
8. Persist the assistant response as conversation history according to the current application flow.
9. Run any configured extraction/management work.

The exact ordering of user/assistant persistence, extraction scheduling, and background worker execution must be verified in the current `conversation_service.py` and worker files. This sequence is a logical integration model, not a claim that all steps are synchronous.

## 15.1 Important role distinction

The later `store_message()` code accepts both `user` and `assistant` roles and creates an embedding in that implementation. Another earlier version only embedded user messages. Search behavior and stored vector coverage therefore changed during development.

Inspect the current `store_message()` before assuming that assistant messages are or are not embedded.

---

# 16. Known Development Findings and Risks

The following findings were recorded during the EDITH memory work.

## 16.1 Observed database counts

A diagnostic reported:

- 226 messages
- 226 embeddings
- 15 structured memories

These counts were observed at that time only.

## 16.2 Known issues or concerns

The November 15 project summary identified:

- Duplicate embeddings/messages.
- Missing database indexes.
- Repeated embedding-model initialization.
- Weak memory extraction/retrieval behavior in some cases.

These should be treated as known areas to verify, not proof that every issue remains in the current checkout.

## 16.3 Retrieval can work while the answer fails

A runtime trace showed relevant structured and conversation memories being included in the debug context sent to Ollama. Earlier, EDITH still failed to answer from the retrieved evidence until the behavior prompt was corrected.

This is an important diagnostic lesson: retrieval success does not prove answer-grounding success.

## 16.4 Historical code evolution

The inspected excerpts from 14 and 15 November differed:

- The earlier service had pending-message management and explicit vector search orchestration.
- The later service delegated semantic search to `search_memory(...)`.
- The later service included a stop-word-aware structured-memory matcher.
- The later service expanded conversation context and labelled `MATCH` versus `CONTEXT`.

Do not combine snippets from different dates into a fictional single implementation. Check the current files before editing.

---

# 17. End-to-End Data Flow: Saving a Conversation

This is the logical save/index flow supported by the shared implementation.

```text
User message
    |
    v
Conversation layer
    |
    v
MemoryService.store_message(session_id, role, content)
    |
    v
Validate role and non-empty content
    |
    v
message_store.save_message(...)
    |
    v
SQLite message record
    |
    v
EmbeddingService.encode(content)
    |
    v
vector_store.save_embedding(message_id, embedding)
    |
    v
Message is available for persistent retrieval
```

If the active version uses a background worker and pending cache, insert that temporary stage according to the actual worker call graph. The code excerpt from the earlier implementation shows that design, but the later service excerpt does not.

## Save-flow checkpoints

| Checkpoint | What to inspect |
|---|---|
| Message received | Conversation handler input |
| Save method called | `MemoryService.store_message()` |
| Message ID returned | `message_store.py` |
| SQLite row exists | Actual database |
| Embedding generated | `EmbeddingService.encode()` |
| Embedding saved | `vector_store.py` |
| Counts consistent | Database diagnostics |
| Retrieval sees record | `search.py` |

---

# 18. End-to-End Data Flow: Answering From Memory

```text
New user query
    |
    v
MemoryService.get_context(query)
    |
    v
get_time_range(query)
    |
    +------------------------------+
    |                              |
    v                              v
Historical query              General query
    |                              |
    v                              v
Search in time range          Semantic search
    |                              |
    |                              +--> Expand conversation context
    |                              |
    |                              +--> Search structured memories
    |                              |
    +---------------+--------------+
                    |
                    v
           Build memory context
                    |
                    v
          Return formatted text
                    |
                    v
      conversation_service.py
                    |
                    v
            Prompt assembly
                    |
                    v
             ollama_client.py
                    |
                    v
             EDITH response
```

## Retrieval-flow checkpoints

1. Is the query correct after STT/text input?
2. Did `get_time_range()` return a range unexpectedly?
3. Did semantic search return the expected message?
4. Did context expansion include appropriate neighbors?
5. Did structured search return the expected facts?
6. Did the context builder format them correctly?
7. Was the exact context passed to the LLM?
8. Did the LLM follow the evidence?

---

# 19. Debugging Playbook

Use this sequence. Change one layer at a time.

## Problem A: EDITH says it does not remember something that was said

1. Search the SQLite messages table for a unique phrase.
2. If absent, debug message persistence.
3. If present, check whether the message has an embedding.
4. If no embedding, debug embedding creation/indexing.
5. If embedding exists, call semantic search directly with a simple query.
6. Print scores and compare them with `min_score`.
7. If the result is found, inspect context expansion.
8. Inspect `build_memory_context()`.
9. Inspect the exact context sent to Ollama.

## Problem B: EDITH remembers the topic but not the exact detail

Likely causes:
- The direct match was too broad.
- The matching message was not indexed.
- The relevant detail was in a neighboring message not included by expansion.
- `top_k`, `max_anchors`, or `max_messages` constrained the result.
- The LLM summarized instead of preserving the precise value.

Debug the raw records and `MATCH`/`CONTEXT` labels before changing thresholds.

## Problem C: Structured memory exists but EDITH cannot answer a direct fact

1. Confirm `StructuredMemoryService.get_all()` returns the record.
2. Print `_memory_terms(query)`.
3. Print `_memory_terms(key + value)`.
4. Inspect the intersection and matching rule.
5. Confirm `search_structured_memories()` returns it.
6. Confirm the context includes `KNOWN FACTS AND PREFERENCES`.
7. Confirm Ollama receives the context.

## Problem D: EDITH recalls the wrong day

1. Print the query.
2. Print `get_time_range(query)`.
3. Check timezone assumptions.
4. Check the SQL time predicate.
5. Check timestamp string format.
6. Check start-inclusive/end-exclusive semantics.
7. Inspect the returned records in chronological order.
8. Inspect the final historical context.

## Problem E: Same message appears multiple times

Check:
- Whether the conversation handler calls persistence more than once.
- Whether a worker retries a save after an ambiguous failure.
- Whether the pending record and persistent record are both returned.
- Whether the indexing process is idempotent.
- Whether the same message ID can receive multiple embeddings.
- Whether duplicate detection exists in the current schema/store.

The project diagnostic identified duplicate messages/embeddings as a concern. Do not delete rows until the exact relationship and canonical record are established.

## Problem F: Memory works after restart but not immediately

This can indicate an indexing/pending-state timing problem.

Check:
- Pending registration.
- Background queue insertion.
- Worker startup.
- Save completion.
- Embedding completion.
- Pending removal timing.
- Whether retrieval searches pending records in the active version.

## Problem G: Memory is present in debug context but answer is wrong

Do not modify SQLite or embeddings first.

Inspect:
- Final prompt assembly.
- Whether memory text is truncated.
- Whether the system prompt tells Ollama to use retrieved memory.
- Whether `MATCH` and `CONTEXT` labels are explained.
- Whether the prompt accidentally contradicts the memory.
- Raw model response versus parsed response.

---

# 20. Diagnostic Logging Recommendations

For debugging, use one trace/correlation identifier per user turn and carry it through retrieval and persistence.

Recommended events:

```text
[memory] turn_id=... message_received role=user
[memory] turn_id=... message_saved message_id=...
[memory] turn_id=... embedding_created dimension=...
[memory] turn_id=... embedding_saved message_id=...
[memory] turn_id=... time_range=...
[memory] turn_id=... semantic_search query=... top_k=... min_score=...
[memory] turn_id=... semantic_results count=...
[memory] turn_id=... structured_results count=...
[memory] turn_id=... context_expansion anchors=... messages=...
[memory] turn_id=... context_built chars=...
[memory] turn_id=... context_sent_to_llm=true
[memory] turn_id=... extraction_started message_id=...
[memory] turn_id=... extraction_completed candidates=...
[memory] turn_id=... structured_write_completed ...
```

Do not print private conversation content in production logs by default. For local development, use a deliberate debug mode and redact sensitive values when sharing logs.

---

# 21. Safe Database and Index Maintenance

The project has reported duplicate records, missing indexes, and repeated embedding initialization as areas of concern.

Before maintenance:

1. Stop EDITH and all memory workers.
2. Identify the actual SQLite database path from `database.py`.
3. Make a copy of the database file.
4. Inspect the actual schema using SQLite metadata.
5. Count messages, embeddings, and structured memories.
6. Identify orphaned embeddings and messages without embeddings.
7. Identify duplicates using stable IDs and content/timestamp/session evidence.
8. Decide which record is canonical before deleting anything.
9. Apply schema/index changes through the project's existing database initialization/migration mechanism.
10. Restart EDITH and run retrieval smoke tests.

Do not invent table names or run a generic delete query based on this document. The actual schema was not fully available in the inspected excerpts.

---

# 22. Verification and Smoke-Test Plan

Run these tests after any memory-related code change.

## Test 1 — Message persistence

- Send a unique test message.
- Confirm a message ID is returned.
- Confirm the row exists in SQLite.
- Confirm the role, content, session, and timestamp are correct.

## Test 2 — Embedding persistence

- Confirm the message has an embedding.
- Confirm vector dimension matches the configured embedding model.
- Confirm the vector can be loaded and compared.

## Test 3 — Semantic retrieval

Store a test statement:

```text
My favorite project is EDITH.
```

Query with different wording:

```text
Which project do I like the most?
```

Confirm the original message appears in the result set with a score above the active threshold.

## Test 4 — Structured-memory CRUD

Using a safe test key:
- Create a structured record.
- Read it with `get_all()`.
- Update it if update behavior is supported.
- Delete it if delete behavior is supported.
- Confirm the database reflects the operation.

The exact public CRUD method names must be read from `structured_service.py` and `structured_store.py`.

## Test 5 — Structured retrieval

Create or use a known record such as:

```text
type=project
key=favorite_project
value=edith
```

Query using words that overlap the key/value. Confirm it is selected by `search_structured_memories()` and appears in the context.

## Test 6 — Conversation context expansion

Create a small conversation with a clear target message and adjacent messages. Confirm:
- Direct match is labelled `MATCH`.
- Neighbor messages are labelled `CONTEXT`.
- Messages are in the expected order.
- Expansion respects the configured limits.

## Test 7 — Historical retrieval

Store messages with known timestamps. Query for the intended date. Confirm:
- `get_time_range()` returns the expected range.
- The UTC/local date conversion is correct.
- The expected messages are returned chronologically.

## Test 8 — LLM grounding

Ask a question whose answer exists in the test memory. Confirm:
- Context contains the exact evidence.
- Final prompt contains the context.
- EDITH answers from that evidence.
- EDITH does not invent missing details.

## Test 9 — Restart persistence

- Stop EDITH.
- Restart it.
- Repeat retrieval for the same stored fact.
- Confirm that persistent data is available without relying on process-local pending state.

## Test 10 — Duplicate protection

Submit a test message once and verify expected row/embedding counts. If retry behavior exists, simulate a retry and verify that the system does not silently create duplicate logical records.

---

# 23. Performance and Resource Considerations

## 23.1 Embedding model lifecycle

Repeated embedding model initialization was identified as a concern. A model should not be reloaded for every individual query or message if the existing architecture is intended to reuse a service instance.

Check:
- Number of `EmbeddingService` instances.
- Whether worker processes/threads construct separate instances.
- Whether `MemoryService` is recreated for every turn.
- Whether the model is cached inside `EmbeddingService`.

Do not change lifecycle behavior until the actual instantiation path is mapped.

## 23.2 Search cost

A semantic query typically requires:
- Encoding the query.
- Loading or reading candidate vectors.
- Calculating similarity.
- Sorting/filtering results.
- Expanding conversation context.

The cost depends on corpus size, vector storage format, model speed, and indexing strategy.

## 23.3 Database indexes

Missing indexes were identified as a concern. Historical queries are particularly sensitive to timestamp indexing as the message table grows. Session-based neighbor expansion may also benefit from an index over the fields used by its actual SQL query.

The exact index definitions should be derived from the SQL statements in `message_store.py`, `vector_store.py`, and `search.py`. Do not add speculative indexes without checking query patterns.

---

# 24. Known Limitations of the Current Design

Based on the inspected code and development notes:

1. Structured-memory retrieval is lexical/key-value matching, not semantic vector retrieval.
2. Semantic retrieval depends on embedding quality and `min_score`.
3. The context builder has separate historical and general-memory branches.
4. `MATCH` and `CONTEXT` labels depend on the context-expansion implementation.
5. The pending-message cache was present in an earlier service version, but its presence in the later version must be verified.
6. Exact extraction quality and conflict handling cannot be documented without the current extractor and manager source.
7. The exact database schema and migration rules were not available in the inspected excerpts.
8. The exact embedding model name and dimensions were not available in the inspected excerpts.
9. Retrieval success does not guarantee the LLM will follow the retrieved evidence.
10. Duplicate records, missing indexes, and repeated model initialization were identified as areas to audit.

---

# 25. Future Extension Points — Not Claims About Current Features

These are possible future improvements, not statements that the current system already implements them:

- Confidence and provenance metadata for structured facts.
- Explicit source message IDs attached to extracted facts.
- Fact versioning and conflict resolution when preferences change.
- Memory expiration or review policies for temporary facts.
- A safe “show memory / correct memory / forget memory” interface.
- Hybrid lexical + semantic structured-memory retrieval.
- Re-ranking retrieved conversation results.
- Automated consistency checks between messages and embeddings.
- Database migrations with schema versioning.
- Extraction evaluation tests using a fixed benchmark dataset.
- Memory quality metrics: precision, recall, duplicate rate, extraction acceptance rate.
- A trace viewer showing each memory decision from source message to final prompt.

Do not add these to the stable v0.1 system until the existing memory path is measured and verified.

---

# 26. Source Files to Inspect First When Returning to Memory Work

Open these files in this order:

1. `app/memory/service.py` — public memory API and context construction.
2. `app/memory/database.py` — actual database path, connection setup, schema initialization.
3. `app/memory/message_store.py` — message persistence.
4. `app/memory/embeddings.py` — embedding model and lifecycle.
5. `app/memory/vector_store.py` — vector persistence and similarity access.
6. `app/memory/search.py` — semantic search, date search, indexing, context expansion.
7. `app/memory/time_parser.py` — natural-language date parsing.
8. `app/memory/structured_service.py` — structured memory API.
9. `app/memory/structured_store.py` — structured record persistence.
10. `app/memory/extractor.py` — extraction behavior.
11. `app/memory/memory_manager.py` — memory orchestration.
12. Worker modules — queue, retries, error handling, and pending lifecycle.
13. `app/conversation_service.py` — integration and prompt assembly.
14. `app/ollama_client.py` — local model request/response boundary.

Use the actual repository paths if the project layout has changed.

---

# 27. A Repeatable Debugging Procedure

When EDITH gives a wrong memory answer, do not change five files at once.

Follow this exact sequence:

**Step 1 — Identify the expected evidence.**  
Write down the exact fact or message that EDITH should have retrieved.

**Step 2 — Verify persistence.**  
Find the record in SQLite.

**Step 3 — Verify its index.**  
Confirm the associated embedding exists and is compatible with the active model.

**Step 4 — Test retrieval independently.**  
Call the relevant search method without involving Ollama.

**Step 5 — Inspect context expansion.**  
Confirm direct matches and neighboring messages.

**Step 6 — Inspect structured retrieval.**  
If the fact is structured, test `get_all()` and the lexical matcher separately.

**Step 7 — Inspect final context.**  
Read the exact string returned by `get_context()`.

**Step 8 — Inspect final prompt.**  
Confirm the conversation service actually passes the context to Ollama.

**Step 9 — Inspect model behavior.**  
Only now debug the LLM grounding prompt or response handling.

**Step 10 — Add a regression test.**  
The bug is not considered fixed until the same failure scenario passes again.

This process separates persistence, indexing, retrieval, formatting, and generation. It prevents prompt changes from hiding database bugs and database changes from masking prompt bugs.

---

# 28. Final Mental Model

Think of EDITH memory as five connected but independently debuggable stages:

```text
1. CAPTURE
   Store what the user and EDITH said.

2. REPRESENT
   Convert selected messages into embeddings.
   Convert selected facts into structured key/value records.

3. RETRIEVE
   Search by semantic similarity, date range, or structured terms.

4. PACKAGE
   Expand conversation context and build a labelled memory text block.

5. USE
   Pass that block to Ollama so EDITH can answer from evidence.
```

If the answer is wrong, identify which stage failed before changing code.

**The core rule:** a memory is useful only when it is correctly stored, correctly indexed or structured, correctly retrieved, correctly included in the prompt, and correctly used by the LLM. Each of those is a separate engineering responsibility.
