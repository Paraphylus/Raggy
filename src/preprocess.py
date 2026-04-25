from pathlib import Path


def _get_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise ImportError(
            "PDF support requires PyMuPDF. Install it in the active virtual environment to index PDF files."
        ) from exc

    return fitz


def read_pdf(file_path):
    fitz = _get_fitz()
    document = fitz.open(file_path)
    pages = []

    for page in document:
        pages.append(str(page.get_text("text")))

    return "\n".join(pages)


def read_pdf_bytes(file_bytes):
    fitz = _get_fitz()
    document = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []

    for page in document:
        pages.append(str(page.get_text("text")))

    return "\n".join(pages)


def read_txt(file_path):
    with open(file_path, "r", encoding="utf-8") as file_obj:
        return file_obj.read()


def read_txt_bytes(file_bytes):
    return file_bytes.decode("utf-8")


def load_document(path):
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix == ".pdf":
        return {"text": read_pdf(str(file_path)), "source": file_path.name}

    if suffix == ".txt":
        return {"text": read_txt(str(file_path)), "source": file_path.name}

    return None


def try_load_document(path):
    try:
        return load_document(path), None
    except Exception as exc:
        return None, str(exc)


def load_uploaded_document(filename, file_bytes):
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        text = read_pdf_bytes(file_bytes)
    elif suffix == ".txt":
        text = read_txt_bytes(file_bytes)
    else:
        raise ValueError("Only .pdf and .txt files are supported.")

    return {"text": text, "source": Path(filename).name}


def chunk_documents(documents, chunk_size=500, overlap=50):
    chunks = []

    for document in documents:
        text = document["text"]
        source = document["source"]
        local_chunk = 0

        for start in range(0, len(text), chunk_size - overlap):
            chunk_text = text[start:start + chunk_size]

            if chunk_text.strip():
                chunks.append(
                    {
                        "id": f"{source}_chunk_{local_chunk}",
                        "text": chunk_text,
                        "meta": {
                            "source": source,
                            "chunk": local_chunk,
                        },
                    }
                )
                local_chunk += 1

    return chunks


def docs_to_chunks(data_dir, chunk_size=500, overlap=50):
    documents = []

    for path in Path(data_dir).iterdir():
        if not path.is_file():
            continue

        document = load_document(path)
        if document and document["text"].strip():
            documents.append(document)

    print(f"Loaded docs: {len(documents)}")
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)
    print(f"Generated chunks: {len(chunks)}")
    return chunks
