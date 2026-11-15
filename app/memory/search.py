import re
import numpy as np

from app.memory.vector_store import load_embeddings, save_embedding
from app.memory.message_store import (
    load_messages,
    load_messages_between,
    load_messages_around,
)
from app.memory.embeddings import EmbeddingService


# --------------------------------------------------
# QUERY ANALYSIS
# --------------------------------------------------

_ROLE_PATTERNS = {
    "assistant": re.compile(
        r"\b(?:what did you explain|what did you tell me|"
        r"what did you say|what was your answer|"
        r"your previous response|you previously explained|"
        r"what have you explained|what did you teach me)\b",
        re.IGNORECASE,
    ),
    "user": re.compile(
        r"\b(?:what did i tell|what did i say|"
        r"what have i told|what did i mention|"
        r"what did i share|my previous statement|"
        r"what was i working on)\b",
        re.IGNORECASE,
    ),
}

_QUERY_STOP_WORDS = {
    "about", "and", "are", "did", "does", "for",
    "from", "have", "how", "into", "is", "me",
    "my", "of", "on", "or", "our", "please",
    "say", "tell", "the", "to", "was", "we",
    "were", "what", "when", "where", "which",
    "who", "why", "you", "your", "yesterday",
    "today", "previously", "previous", "earlier",
    "discuss", "discussed", "conversation",
    "conversations", "remember", "recall",
    "summarize", "summary", "last", "day",
}

_TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)


def _preferred_role(text: str):
    if _ROLE_PATTERNS["assistant"].search(text):
        return "assistant"

    if _ROLE_PATTERNS["user"].search(text):
        return "user"

    return None


def _query_terms(text: str) -> set[str]:
    return {
        word
        for word in _TOKEN_PATTERN.findall(text.casefold())
        if len(word) > 1 and word not in _QUERY_STOP_WORDS
    }


def _lexical_score(query_terms: set[str], content_terms: set[str]) -> float:
    if not query_terms or not content_terms:
        return 0.0

    return len(query_terms & content_terms) / len(query_terms)


# --------------------------------------------------
# VECTOR VALIDATION AND SIMILARITY
# --------------------------------------------------

def _prepare_query_vector(query_embedding):
    vector = np.asarray(query_embedding, dtype=np.float32).reshape(-1)

    if vector.size == 0 or not np.isfinite(vector).all():
        raise ValueError("Invalid query embedding.")

    norm = np.linalg.norm(vector)

    if norm == 0:
        raise ValueError("Query embedding has zero magnitude.")

    return vector / norm


def _cosine_scores(query_vector, embeddings):
    """
    Calculate cosine similarity using NumPy.

    Invalid vectors and dimension mismatches receive
    no semantic score instead of breaking retrieval.
    """

    scores = np.zeros(len(embeddings), dtype=np.float32)

    valid_indexes = []
    valid_vectors = []

    for index, embedding in enumerate(embeddings):
        try:
            vector = np.asarray(embedding, dtype=np.float32).reshape(-1)

            if (
                vector.shape != query_vector.shape
                or not np.isfinite(vector).all()
            ):
                continue

            norm = np.linalg.norm(vector)

            if norm == 0:
                continue

            valid_indexes.append(index)
            valid_vectors.append(vector / norm)

        except (TypeError, ValueError):
            continue

    if valid_vectors:
        matrix = np.vstack(valid_vectors)
        similarities = matrix @ query_vector

        scores[valid_indexes] = similarities

    return scores


# --------------------------------------------------
# MESSAGE RANKING
# --------------------------------------------------

def _rank_messages(
    messages,
    message_embeddings,
    query_embedding,
    top_k,
    min_score,
    preferred_role=None,
    query_terms=None,
):
    if not messages or top_k <= 0:
        return []

    if len(messages) != len(message_embeddings):
        raise ValueError(
            "Message and embedding counts do not match."
        )

    query_vector = _prepare_query_vector(query_embedding)

    similarities = _cosine_scores(
        query_vector,
        message_embeddings,
    )

    query_terms = query_terms or set()

    results = []

    for index, message in enumerate(messages):

        if (
            preferred_role
            and message["role"] != preferred_role
        ):
            continue

        similarity_score = float(similarities[index])

        content = message["content"]

        content_terms = _query_terms(content)

        lexical_score = _lexical_score(
            query_terms,
            content_terms,
        )

        ranking_score = (
            similarity_score * 0.65
            + lexical_score * 0.35
        )

        if (
            similarity_score < min_score
            and lexical_score < 0.5
        ):
            continue

        results.append({
            "message_id": message["id"],
            "score": ranking_score,
            "similarity": similarity_score,
            "lexical_score": lexical_score,
            "role": message["role"],
            "content": content,
            "created_at": message["created_at"],
            "session_id": message["session_id"],
            "is_match": True,
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]


# --------------------------------------------------
# GLOBAL SEMANTIC SEARCH
# --------------------------------------------------

def search_similar_memories(
    query_embedding,
    top_k: int = 5,
    min_score: float = 0.30,
    preferred_role=None,
    query_terms=None,
):
    if top_k <= 0:
        return []

    stored_embeddings = load_embeddings()

    if not stored_embeddings:
        return []

    messages = load_messages()

    messages_by_id = {
        message["id"]: message
        for message in messages
    }

    valid_messages = []
    valid_embeddings = []

    for item in stored_embeddings:

        message = messages_by_id.get(item["message_id"])

        if message is None:
            continue

        valid_messages.append(message)
        valid_embeddings.append(item["embedding"])

    return _rank_messages(
        messages=valid_messages,
        message_embeddings=valid_embeddings,
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        preferred_role=preferred_role,
        query_terms=query_terms,
    )


# --------------------------------------------------
# HISTORICAL SEARCH
# --------------------------------------------------

def search_messages_in_range(
    text: str,
    start_time: str,
    end_time: str,
    embedding_service: EmbeddingService,
    top_k: int = 20,
    min_score: float = 0.25,
):
    if not text or not text.strip() or top_k <= 0:
        return []

    messages = load_messages_between(
        start_time,
        end_time,
    )

    if not messages:
        return []

    query_terms = _query_terms(text)

    # No meaningful topic: return recent records directly.
    # Avoid generating embeddings unnecessarily.
    if not query_terms:

        return [
            {
                "message_id": message["id"],
                "score": 1.0,
                "similarity": 1.0,
                "lexical_score": 0.0,
                "role": message["role"],
                "content": message["content"],
                "created_at": message["created_at"],
                "session_id": message["session_id"],
                "is_match": True,
            }
            for message in messages[-top_k:]
        ]

    preferred_role = _preferred_role(text)

    stored_embeddings = load_embeddings()

    embeddings_by_id = {
        item["message_id"]: item["embedding"]
        for item in stored_embeddings
    }

    message_embeddings = []

    for message in messages:

        message_id = message["id"]

        embedding = embeddings_by_id.get(message_id)

        if embedding is None:

            embedding = embedding_service.encode(
                message["content"]
            )

            save_embedding(
                message_id,
                embedding,
            )

        message_embeddings.append(embedding)

    query_embedding = embedding_service.encode(text)

    return _rank_messages(
        messages=messages,
        message_embeddings=message_embeddings,
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        preferred_role=preferred_role,
        query_terms=query_terms,
    )


# --------------------------------------------------
# CONVERSATION CONTEXT EXPANSION
# --------------------------------------------------

def expand_conversation_context(
    results,
    window: int = 1,
    max_messages: int = 30,
    max_anchors: int = 5,
):
    if not results:
        return []

    if max_messages <= 0 or max_anchors <= 0:
        return []

    expanded = {}

    anchors = results[:max_anchors]

    for result in anchors:

        message_id = result.get("message_id")
        session_id = result.get("session_id")

        if message_id is None or session_id is None:
            continue

        nearby_messages = load_messages_around(
            message_id=message_id,
            session_id=session_id,
            window=window,
        )

        for message in nearby_messages:

            current_id = message["id"]

            is_match = current_id == message_id

            if current_id in expanded:

                if is_match:
                    expanded[current_id].update({
                        "is_match": True,
                        "score": result["score"],
                        "similarity": result.get("similarity", 0.0),
                        "lexical_score": result.get(
                            "lexical_score",
                            0.0,
                        ),
                    })

                continue

            expanded[current_id] = {
                "message_id": current_id,
                "score": (
                    result["score"]
                    if is_match
                    else result["score"] - 0.03
                ),
                "similarity": (
                    result.get("similarity", 0.0)
                    if is_match
                    else 0.0
                ),
                "lexical_score": (
                    result.get("lexical_score", 0.0)
                    if is_match
                    else 0.0
                ),
                "role": message["role"],
                "content": message["content"],
                "created_at": message["created_at"],
                "session_id": message["session_id"],
                "is_match": is_match,
            }

    ordered_results = sorted(
        expanded.values(),
        key=lambda item: item["message_id"],
    )

    return ordered_results[:max_messages]


# --------------------------------------------------
# MEMORY SEARCH ENTRY POINT
# --------------------------------------------------

def search_memory(
    text: str,
    embedding_service: EmbeddingService,
    top_k: int = 5,
    min_score: float = 0.30,
):
    if not text or not text.strip() or top_k <= 0:
        return []

    query_embedding = embedding_service.encode(text)

    return search_similar_memories(
        query_embedding=query_embedding,
        top_k=top_k,
        min_score=min_score,
        preferred_role=_preferred_role(text),
        query_terms=_query_terms(text),
    )


# --------------------------------------------------
# HISTORICAL EMBEDDING INDEXING
# --------------------------------------------------

def index_messages():
    embedding_service = EmbeddingService()

    existing_embeddings = load_embeddings()

    indexed_message_ids = {
        item["message_id"]
        for item in existing_embeddings
    }

    messages = load_messages()

    missing_messages = [
        message
        for message in messages
        if message["id"] not in indexed_message_ids
    ]

    indexed_count = 0

    for message in missing_messages:

        embedding = embedding_service.encode(
            message["content"]
        )

        save_embedding(
            message["id"],
            embedding,
        )

        indexed_count += 1

    return indexed_count