"""Root llm package proxy."""

import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent.parent / "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.llm.embeddings import (
    EMBEDDING_DIM,
    clear_vector_index,
    cosine_similarity,
    embed_batch,
    embed_text,
    get_vector_index,
    index_network_embeddings,
    search_vector_index,
    upsert_entity_embedding,
)

__all__ = [
    "EMBEDDING_DIM",
    "clear_vector_index",
    "cosine_similarity",
    "embed_batch",
    "embed_text",
    "get_vector_index",
    "index_network_embeddings",
    "search_vector_index",
    "upsert_entity_embedding",
]
