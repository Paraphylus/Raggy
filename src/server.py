import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.generate_groq import generate_answer
from src.preprocess import chunk_documents, load_uploaded_document, try_load_document
from src.prompt_builder import build_prompt
from src.retrieve import INDEX_PATH, META_PATH, Retriever


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEMO_DIR = PROJECT_ROOT / "demo"
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

app = FastAPI(title="RAG Q&A")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

retriever = Retriever()


def format_bytes(size_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(size_bytes)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024

    return f"{size_bytes} B"


def data_dir_stats():
    files = [path for path in DATA_DIR.iterdir() if path.is_file() and path.suffix.lower() in {".pdf", ".txt"}]
    total_size_bytes = sum(path.stat().st_size for path in files)
    return {
        "files": len(files),
        "data_size_bytes": total_size_bytes,
        "data_size_human": format_bytes(total_size_bytes),
    }


def app_metrics():
    retriever_stats = retriever.stats()
    directory_stats = data_dir_stats()
    total_index_bytes = retriever_stats["index_size_bytes"] + retriever_stats["metadata_size_bytes"]

    return {
        "documents": retriever_stats["documents"],
        "chunks": retriever_stats["chunks"],
        "total_characters": retriever_stats["total_characters"],
        "average_chunk_chars": retriever_stats["average_chunk_chars"],
        "index_size_bytes": retriever_stats["index_size_bytes"],
        "metadata_size_bytes": retriever_stats["metadata_size_bytes"],
        "index_size_human": format_bytes(total_index_bytes),
        "data_size_bytes": directory_stats["data_size_bytes"],
        "data_size_human": directory_stats["data_size_human"],
        "uploaded_files": directory_stats["files"],
    }


def sync_data_dir_to_index():
    documents = []
    skipped_files = []

    for path in sorted(DATA_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in {".pdf", ".txt"}:
            continue

        document, error = try_load_document(path)
        if error:
            skipped_files.append({"file": path.name, "reason": error})
            print(f"Skipping {path.name}: {error}")
            continue

        if document and document["text"].strip():
            documents.append(document)

    chunks = chunk_documents(documents)
    retriever.replace_all_chunks(chunks)
    return skipped_files


@app.on_event("startup")
def startup_sync():
    skipped_files = sync_data_dir_to_index()
    app.state.skipped_files = skipped_files


class QueryIn(BaseModel):
    question: str
    top_k: int = int(os.getenv("TOP_K", "5"))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "index_path": str(INDEX_PATH),
        "meta_path": str(META_PATH),
        "demo_served": DEMO_DIR.exists(),
        "indexed_chunks": retriever.index.ntotal,
        "sources": retriever.document_names(),
        "metrics": app_metrics(),
        "skipped_files": getattr(app.state, "skipped_files", []),
    }


@app.get("/documents")
def documents():
    return {
        "documents": retriever.document_names(),
        "indexed_chunks": retriever.index.ntotal,
        "metrics": app_metrics(),
        "skipped_files": getattr(app.state, "skipped_files", []),
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please choose a document to upload.")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="Only PDF and TXT uploads are supported.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        document = load_uploaded_document(file.filename, file_bytes)
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="TXT files must be UTF-8 encoded.") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not document["text"].strip():
        raise HTTPException(status_code=400, detail="No readable text was found in the uploaded document.")

    safe_name = Path(file.filename).name
    target_path = DATA_DIR / safe_name
    target_path.write_bytes(file_bytes)

    chunks = chunk_documents([document])
    result = retriever.upsert_chunks(chunks)

    return {
        "message": f"{safe_name} uploaded and indexed.",
        "filename": safe_name,
        "chunks_added": result["added_chunks"],
        "documents": retriever.document_names(),
        "metrics": app_metrics(),
    }


@app.post("/ask")
def ask(query: QueryIn):
    start = time.time()
    retrieved = retriever.query(query.question, top_k=query.top_k)

    if not retrieved:
        raise HTTPException(
            status_code=400,
            detail="No indexed content is available yet. Upload a PDF or TXT document first.",
        )

    prompt = build_prompt(retrieved, query.question)

    try:
        answer = generate_answer(prompt)
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    latency = time.time() - start

    return {
        "answer": answer,
        "sources": [
            {
                "source": item["meta"]["source"],
                "chunk": item["meta"]["chunk"],
                "score": item["score"],
            }
            for item in retrieved
        ],
        "latency_s": latency,
        "metrics": app_metrics(),
    }


if DEMO_DIR.exists():
    app.mount("/", StaticFiles(directory=DEMO_DIR, html=True), name="demo")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.server:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8080")),
        reload=True,
    )
