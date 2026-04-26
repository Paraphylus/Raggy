# RAG Retrieval System

A lightweight Retrieval-Augmented Generation app that lets users upload PDF or TXT documents, ask natural-language questions, and receive answers backed by the most relevant document chunks.

This project was built to make document search feel less like keyword hunting and more like a conversation. The backend indexes uploaded documents with sentence embeddings and FAISS, retrieves the strongest matches for each question, and sends the grounded context to a Groq-hosted LLM for a concise answer with source references.

## Live Demo Flow

1. Open the app in a browser.
2. Upload a PDF or TXT document, or use the bundled demo document.
3. Ask a question about the document.
4. Review the generated answer, retrieved sources, latency, and index metrics.

## What It Does

- Serves a clean browser-based chat UI from `demo/`
- Accepts PDF and TXT uploads
- Extracts document text with PyMuPDF for PDFs
- Splits content into overlapping chunks
- Creates semantic embeddings with `fastembed` (ONNX-based, lightweight. Previously used sentence-transformers which increased deployment space)
- Stores and searches vectors with FAISS
- Retrieves the top matching chunks for each query
- Generates grounded answers through Groq
- Exposes health, document, upload, and question-answering APIs

## Architecture

```text
PDF/TXT upload
    -> text extraction
    -> chunking, 500 chars with 50 char overlap
    -> sentence-transformer embeddings
    -> FAISS vector index
    -> top-k retrieval
    -> prompt construction
    -> Groq LLM response
    -> answer + sources + latency
```

## Current Project Metrics

These numbers describe the current local project snapshot.

| Metric | Value |
| --- | ---: |
| Demo documents in `data/` | 1 PDF |
| Demo corpus size | ~476 KB |
| Backend source files | 7 |
| Frontend files | 3 |
| App source size, excluding virtual envs | ~45 KB |
| Chunk size | 500 characters |
| Chunk overlap | 50 characters |
| Default retrieval depth | Top 5 chunks |
| Local FAISS index snapshot | ~771 KB |
| Local FAISS metadata snapshot | ~169 KB |
| Local indexed chunks snapshot | 257 chunks |
| Local indexed text snapshot | ~128,972 characters |
| Average indexed chunk size snapshot | ~502 characters |

Note: the app rebuilds the FAISS index from files in `data/` when the server starts. If you remove or replace demo files before deployment, the live metrics will update automatically.

## Tech Stack

| Layer | Tools |
| --- | --- |
| Backend API | FastAPI, Uvicorn |
| Frontend | HTML, CSS, JavaScript |
| Embeddings | FastEmbed |
| Vector Search | FAISS |
| PDF Parsing | PyMuPDF |
| LLM Generation | Groq API |
| Deployment | Docker, Docker Compose |

## API Endpoints

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/` | GET | Serves the frontend |
| `/health` | GET | Shows app status, index paths, metrics, and loaded sources |
| `/documents` | GET | Lists indexed documents and retrieval metrics |
| `/upload` | POST | Uploads and indexes a PDF or TXT file |
| `/ask` | POST | Retrieves relevant chunks and generates an answer |

Example `/ask` request:

```json
{
  "question": "What is the document about?",
  "top_k": 5
}
```

## Run Locally

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
EMBED_MODEL=BAAI/bge-small-en-v1.5
HOST=127.0.0.1
PORT=8080
TOP_K=5
```

Install dependencies and start the app:

```bash
pip install -r requirements.txt
uvicorn src.server:app --host 127.0.0.1 --port 8080 --reload
```

Open:

```text
http://127.0.0.1:8080
```

## Run With Docker

```bash
docker build -t rag-retrieval-system .
docker run --rm -p 8080:8080 --env-file .env rag-retrieval-system
```

Or with Docker Compose:

```bash
docker compose up --build
```

## Deployment Notes

Required production environment variables:

```env
GROQ_API_KEY=your_groq_api_key
EMBED_MODEL=BAAI/bge-small-en-v1.5
HOST=0.0.0.0
PORT=8080
TOP_K=5
```

## Why This Project Matters

This project demonstrates the core pieces of a practical RAG system: document ingestion, chunking strategy, vector indexing, semantic retrieval, prompt construction, answer generation, and a usable interface for non-technical users. It is small enough to deploy easily, but complete enough to show the full retrieval pipeline in action.
