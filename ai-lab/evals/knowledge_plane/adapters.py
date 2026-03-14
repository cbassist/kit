"""Retriever protocol, local and hosted implementations, and context packing."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Protocol

from .normalization import canonical_doc_id, normalize_hosted_doc_id


@dataclass
class RetrievedChunk:
    doc_id: str
    chunk_id: str
    text: str
    score: float
    source: str
    metadata: dict[str, Any] | None = None


class LocalSearchBackend(Protocol):
    def search(self, query: str, top_k: int = 8) -> list[dict[str, Any]]:
        ...


class LocalRetriever:
    def __init__(self, backend: LocalSearchBackend):
        self.backend = backend

    def retrieve(self, query: str, k: int = 8) -> list[RetrievedChunk]:
        rows = self.backend.search(query=query, top_k=k)
        chunks: list[RetrievedChunk] = []
        for i, row in enumerate(rows):
            chunks.append(
                RetrievedChunk(
                    doc_id=canonical_doc_id(str(row.get("doc_id", "unknown"))),
                    chunk_id=str(row.get("chunk_id", f"local-{i}")),
                    text=str(row.get("text", "")),
                    score=float(row.get("score", 0.0)),
                    source="local",
                    metadata=row.get("metadata", {}),
                )
            )
        return chunks


class OpenAIFileSearchRetriever:
    def __init__(
        self,
        client: Any,
        vector_store_id: str,
        model: str,
        manifest_index: dict[str, Any],
    ):
        self.client = client
        self.vector_store_id = vector_store_id
        self.model = model
        self.manifest_index = manifest_index

    def retrieve(self, query: str, k: int = 8) -> list[RetrievedChunk]:
        resp = self.client.responses.create(
            model=self.model,
            input=query,
            tools=[
                {
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id],
                    "max_num_results": k,
                }
            ],
            tool_choice={"type": "file_search"},
            include=["file_search_call.results"],
            store=False,
        )

        chunks: list[RetrievedChunk] = []

        for item in getattr(resp, "output", []):
            if getattr(item, "type", None) != "file_search_call":
                continue

            for i, result in enumerate(getattr(item, "results", []) or []):
                filename = getattr(result, "filename", None)
                file_id = getattr(result, "file_id", None)

                doc_id = normalize_hosted_doc_id(
                    filename=filename,
                    file_id=file_id,
                    manifest_index=self.manifest_index,
                )

                chunks.append(
                    RetrievedChunk(
                        doc_id=doc_id,
                        chunk_id=f"{doc_id}::hosted-{i}",
                        text=getattr(result, "text", "") or "",
                        score=float(getattr(result, "score", 0.0) or 0.0),
                        source="openai_file_search",
                        metadata={
                            "filename": filename,
                            "file_id": file_id,
                        },
                    )
                )

        return chunks


def build_context_pack(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "No retrieved evidence."

    lines: list[str] = []
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(
            f"[{idx}] doc_id={chunk.doc_id} chunk_id={chunk.chunk_id} "
            f"score={chunk.score:.4f} source={chunk.source}\n{chunk.text}".strip()
        )
    return "\n\n".join(lines)


def chunks_to_jsonable(chunks: list[RetrievedChunk]) -> list[dict[str, Any]]:
    return [asdict(c) for c in chunks]
