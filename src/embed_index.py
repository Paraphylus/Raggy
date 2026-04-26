import json
import os
from pathlib import Path

import faiss
import numpy as np
from fastembed import TextEmbedding

from src.preprocess import docs_to_chunks
from src.retrieve import EMBED_MODEL, resolve_data_path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = resolve_data_path(os.getenv("FAISS_INDEX_PATH", ""), "faiss_index.index")
META_PATH = resolve_data_path(os.getenv("FAISS_META_PATH", ""), "faiss_meta.json")


def build_index(chunks, model_name=EMBED_MODEL, index_path=INDEX_PATH, meta_path=META_PATH):
    model = TextEmbedding(model_name)
    texts = [chunk["text"] for chunk in chunks]
    embeddings = np.asarray(list(model.embed(texts)), dtype=np.float32)
    dim = int(embeddings.shape[1])
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    faiss.write_index(index, str(index_path))
    metadata = [{"id": chunk["id"], "text": chunk["text"], "meta": chunk["meta"]} for chunk in chunks]
    with open(meta_path, "w", encoding="utf-8") as file_obj:
        json.dump(metadata, file_obj, ensure_ascii=False)
    print(f"Index saved to {index_path}, meta saved to {meta_path}")


if __name__ == "__main__":
    data_path = PROJECT_ROOT / "data"
    print("Using data path:", data_path)

    chunks = docs_to_chunks(str(data_path))

    print("Chunks:", len(chunks))
    print("Sample chunk:", chunks[:1])

    if not chunks:
        raise ValueError("No chunks generated. Check preprocess.py or the data folder.")

    build_index(chunks)
