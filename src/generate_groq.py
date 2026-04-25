import os
from dotenv import load_dotenv
import os

load_dotenv()
from groq import Groq

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def generate_answer(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for RAG-based QA."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content