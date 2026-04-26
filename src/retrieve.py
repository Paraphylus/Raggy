import json
import os
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")


def resolve_data_path(raw_path: str, default_name: str) -> Path:
    if raw_path:
        candidate = Path(raw_path)
        if candidate.is_absolute():
            if candidate.exists():
                return candidate

            docker_style = PROJECT_ROOT / candidate.name
            if docker_style.exists():
                return docker_style

            return candidate

        return (PROJECT_ROOT / candidate).resolve()

    return PROJECT_ROOT / default_name


INDEX_PATH = resolve_data_path(os.getenv("FAISS_INDEX_PATH", ""), "faiss_index.index")
META_PATH = resolve_data_path(os.getenv("FAISS_META_PATH", ""), "faiss_meta.json")


class Retriever:
    def __init__(self, index_path: Path = INDEX_PATH, meta_path: Path = META_PATH, model_name: str = EMBED_MODEL):
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.model = TextEmbedding(model_name)
        self.index = None
        self.meta = []
        self._load()

    def _load(self):
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        else:
            self.index = self._build_empty_index()

        if self.meta_path.exists():
            with open(self.meta_path, "r", encoding="utf-8") as file_obj:
                self.meta = json.load(file_obj)
        else:
            self.meta = []

    def _build_empty_index(self):
        sample_embedding = self._encode(["dimension probe"])
        dimension = int(sample_embedding.shape[1])
        return faiss.IndexFlatIP(dimension)

    def _encode(self, texts):
        embeddings = list(self.model.embed(texts))
        embeddings = np.asarray(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings)
        return embeddings

    def save(self):
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as file_obj:
            json.dump(self.meta, file_obj, ensure_ascii=False)

    def reset(self):
        self.index = self._build_empty_index()
        self.meta = []
        self.save()

    def replace_all_chunks(self, chunks):
        if not chunks:
            self.reset()
            return {"added_chunks": 0, "replaced_sources": []}

        embeddings = self._encode([chunk["text"] for chunk in chunks])
        new_index = faiss.IndexFlatIP(embeddings.shape[1])
        new_index.add(embeddings)

        self.index = new_index
        self.meta = [{"id": chunk["id"], "text": chunk["text"], "meta": chunk["meta"]} for chunk in chunks]
        self.save()

        return {
            "added_chunks": len(chunks),
            "replaced_sources": sorted({chunk["meta"]["source"] for chunk in chunks}),
        }

    def document_names(self):
        return sorted({item["meta"]["source"] for item in self.meta})

    def stats(self):
        doc_count = len(self.document_names())
        chunk_count = int(self.index.ntotal)
        total_characters = sum(len(item["text"]) for item in self.meta)
        average_chunk_chars = round(total_characters / chunk_count, 1) if chunk_count else 0
        index_size_bytes = self.index_path.stat().st_size if self.index_path.exists() else 0
        meta_size_bytes = self.meta_path.stat().st_size if self.meta_path.exists() else 0

        return {
            "documents": doc_count,
            "chunks": chunk_count,
            "total_characters": total_characters,
            "average_chunk_chars": average_chunk_chars,
            "index_size_bytes": index_size_bytes,
            "metadata_size_bytes": meta_size_bytes,
        }

    def query(self, text, top_k=5):
        if self.index.ntotal == 0 or not self.meta:
            return []

        qvec = self._encode([text])
        limit = min(top_k, self.index.ntotal)
        distances, idxs = self.index.search(qvec, limit)
        results = []
        for score, idx in zip(distances[0], idxs[0]):
            metadata = self.meta[idx]
            results.append(
                {
                    "score": float(score),
                    "id": metadata["id"],
                    "text": metadata["text"],
                    "meta": metadata["meta"],
                }
            )
        return results

    def upsert_chunks(self, chunks):
        if not chunks:
            return {"added_chunks": 0, "replaced_sources": []}

        sources_to_replace = {chunk["meta"]["source"] for chunk in chunks}
        retained_meta = [item for item in self.meta if item["meta"]["source"] not in sources_to_replace]

        if retained_meta:
            retained_embeddings = self._encode([item["text"] for item in retained_meta])
            new_index = faiss.IndexFlatIP(retained_embeddings.shape[1])
            new_index.add(retained_embeddings)
        else:
            new_index = self._build_empty_index()

        new_meta = [{"id": chunk["id"], "text": chunk["text"], "meta": chunk["meta"]} for chunk in chunks]
        new_embeddings = self._encode([chunk["text"] for chunk in chunks])
        new_index.add(new_embeddings)

        self.index = new_index
        self.meta = retained_meta + new_meta
        self.save()

        return {"added_chunks": len(new_meta), "replaced_sources": sorted(sources_to_replace)}


if __name__ == "__main__":
    retriever = Retriever()
    sample_question = "What is phishing?"
    print(retriever.query(sample_question, top_k=3))
