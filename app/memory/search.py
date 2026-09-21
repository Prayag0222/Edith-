import numpy as np
from sentence_transformers import util
from app.memory.database import (
    load_messages,
    load_message,
    load_embeddings,
    save_embedding,
    load_messages_between
)

from app.memory.embeddings import EmbeddingService

from app.memory.database import load_embeddings


def search_similar_memories(
    query_embedding,
    top_k: int = 5,
    min_score:float = 0.3,
):
    stored_embeddings = load_embeddings()

    if not stored_embeddings:
        return []

    vectors = np.array([
        item["embedding"]
        for item in stored_embeddings
    ],

    dtype=np.float32)

    query_vector = np.array(query_embedding,dtype=np.float32)

    scores = util.cos_sim(
        query_vector,
        vectors,
    )[0]

    results = []

    for index, score in enumerate(scores):
      message_id = stored_embeddings[index]["message_id"]
      message = load_message(message_id)

      if message is None:
          continue 

      score_value = float(score)

      if score_value < min_score:
          continue

      results.append({
           "message_id": message_id,
        "score": float(score),
        "role": message["role"],
        "content": message["content"],
        "created_at": message["created_at"],
      })
    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]


def search_messages_in_range(
    text: str,
    start_time: str,
    end_time: str,
    embedding_service: EmbeddingService,
    top_k: int = 5,
    min_score: float = 0.30,
):
    messages = load_messages_between(
        start_time,
        end_time,
    )

    if not messages:
        return []

    query_embedding = embedding_service.encode(text)

    stored_embeddings = load_embeddings()

    embedding_map = {
        item["message_id"]: item["embedding"]
        for item in stored_embeddings
    }

    results = []

    for message in messages:
        message_id = message.get("id")

        if message_id is None:
            continue

        stored_embedding = embedding_map.get(message_id)

        if stored_embedding is None:
            continue

        score = util.cos_sim(
            np.array(query_embedding, dtype=np.float32),
            np.array(stored_embedding, dtype=np.float32),
        )[0][0]

        score_value = float(score)

        if score_value < min_score:
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

def search_memory(
    text: str,
    embedding_service: EmbeddingService ,
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