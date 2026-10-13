import numpy as np
from sentence_transformers import util

from app.memory.vector_store import load_embeddings, save_embedding
from app.memory.message_store import (
    load_messages,
    load_message,
    load_messages_between,
)
from app.memory.embeddings import EmbeddingService


def search_similar_memories(
    query_embedding,
    top_k: int = 5,
    min_score: float = 0.30,
):
    stored_embeddings = load_embeddings()

    if not stored_embeddings or top_k <= 0:
        return []

    vectors = np.asarray(
        [item["embedding"] for item in stored_embeddings],
        dtype=np.float32,
    )

    query_vector = np.asarray(
        query_embedding,
        dtype=np.float32,
    )

    scores = util.cos_sim(query_vector, vectors)[0]
    results = []

    for index, score in enumerate(scores):
        score_value = float(score)

        if score_value < min_score:
            continue

        message_id = stored_embeddings[index]["message_id"]
        message = load_message(message_id)

        if message is None:
            continue

        results.append({
            "message_id": message_id,
            "score": score_value,
            "role": message["role"],
            "content": message["content"],
            "created_at": message["created_at"],
            "session_id": message["session_id"],
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]


def _select_balanced_messages(messages, top_k: int):
    """Select messages distributed across the complete time range."""

    if top_k <= 0:
        return []

    if len(messages) <= top_k:
        return messages

    if top_k == 1:
        return [messages[len(messages) // 2]]

    indices = [
        round(index * (len(messages) - 1) / (top_k - 1))
        for index in range(top_k)
    ]

    return [messages[index] for index in indices]


def search_messages_in_range(
    text: str,
    start_time: str,
    end_time: str,
    embedding_service: EmbeddingService,
    top_k: int = 20,
    min_score: float = 0.30,
):
    messages = load_messages_between(
        start_time,
        end_time,
    )

    selected_messages = _select_balanced_messages(
        messages,
        top_k,
    )

    return [
        {
            "message_id": message["id"],
            "score": 1.0,
            "role": message["role"],
            "content": message["content"],
            "created_at": message["created_at"],
            "session_id": message["session_id"],
        }
        for message in selected_messages
    ]


def search_memory(
    text: str,
    embedding_service: EmbeddingService,
    top_k: int = 5,
    min_score: float = 0.30,
):
    query_embedding = embedding_service.encode(text)

    return search_similar_memories(
        query_embedding,
        top_k=top_k,
        min_score=min_score,
    )


def index_messages():
    embedding_service = EmbeddingService()

    existing_embeddings = load_embeddings()

    indexed_message_ids = {
        item["message_id"]
        for item in existing_embeddings
    }

    messages = load_messages()
    indexed_count = 0

    for message in messages:
        message_id = message["id"]

        if message_id in indexed_message_ids:
            continue

        embedding = embedding_service.encode(
            message["content"]
        )

        save_embedding(
            message_id,
            embedding,
        )

        indexed_count += 1

    return indexed_count