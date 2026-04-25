from typing import List

SYSTEM_PROMPT = "You are a helpful assistant. Use the context below to answer the question. If information is missing, say you don't know."

def build_prompt(retrieved: List[dict], question: str, max_chars_context=3000):
    context = ""
    for r in retrieved:
        context += f"Source: {r['meta']['source']} (chunk {r['meta']['chunk']})\n{r['text']}\n---\n"
        if len(context) > max_chars_context:
            break
    prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\nQuestion: {question}\nAnswer in clear concise sentences. Cite sources where relevant."
    return prompt