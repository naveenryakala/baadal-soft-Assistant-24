import os
import json
import numpy as np
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from google import genai
from groq import Groq
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = genai.Client(api_key=GOOGLE_API_KEY)
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# RAG Components
DOCUMENT_CHUNKS = []
CHUNK_EMBEDDINGS = []
CONVERSATION_HISTORY = [] # Maintain last 5 message pairs
HISTORY_FILE = 'chat_history.json'

def load_history():
    global CONVERSATION_HISTORY
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                CONVERSATION_HISTORY = json.load(f)
            print(f"Loaded {len(CONVERSATION_HISTORY)} messages from history.")
    except Exception as e:
        print(f"Error loading history: {e}")

def save_history():
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(CONVERSATION_HISTORY, f, indent=4)
    except Exception as e:
        print(f"Error saving history: {e}")

def load_and_chunk_documents():
    global DOCUMENT_CHUNKS, CHUNK_EMBEDDINGS
    try:
        if not os.path.exists('docs.json'):
            print("Error: docs.json not found.")
            return

        with open('docs.json', 'r', encoding='utf-8-sig') as f:
            docs = json.load(f)
        
        # In a real app, we'd chunk here. For this simple assignment, we treat each entry as a chunk.
        DOCUMENT_CHUNKS = docs
        print(f"Loaded {len(DOCUMENT_CHUNKS)} documents.")
        
        generate_all_embeddings()
        
    except Exception as e:
        print(f"Error loading docs: {e}")

def generate_all_embeddings():
    global CHUNK_EMBEDDINGS
    CHUNK_EMBEDDINGS = []
    for chunk in DOCUMENT_CHUNKS:
        embedding = generate_embedding(chunk['content'])
        CHUNK_EMBEDDINGS.append(embedding)

def generate_embedding(text):
    try:
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config={"task_type": "RETRIEVAL_DOCUMENT"}
        )
        return result.embeddings[0].values
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return [0.0] * 768 # Dummy embedding

def cosine_similarity(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

def find_relevant_chunks(query_embedding, top_k=3):
    if not CHUNK_EMBEDDINGS:
        return []
    similarities = [cosine_similarity(query_embedding, emb) for emb in CHUNK_EMBEDDINGS]
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    return [DOCUMENT_CHUNKS[i] for i in top_indices]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    global CONVERSATION_HISTORY
    data = request.json
    user_query = data.get('query')
    
    if not user_query:
        return jsonify({"error": "No query provided"}), 400

    query_embedding = generate_embedding(user_query)
    
    relevant_chunks = find_relevant_chunks(query_embedding)
    
    # Build context string
    context_list = []
    for c in relevant_chunks:
        title = c.get('title', 'Unknown')
        content = c.get('content', '')
        context_list.append(f"Doc: {title}\nContent: {content}")
    context = "\n\n".join(context_list)
    
    history_str = "\n".join([f"User: {h['user']}\nAssistant: {h['assistant']}" for h in CONVERSATION_HISTORY])
    
    prompt = f"""
You are a helpful GenAI Assistant. Use the following context to answer the user's question accurately.
If the answer is not in the context, say you don't know based on the provided documents.

Context:
{context}

Recent Conversation History:
{history_str}

User Question: {user_query}
Assistant:"""

    try:
        try:
            # Primary: Google Gemini
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt
            )
            assistant_answer = response.text
            provider = "Gemini"
        except Exception as gemini_err:
            print(f"Gemini Error: {gemini_err}. Attempting fallback to Groq...")
            # Fallback: Groq (Llama 3 8B)
            if not groq_client:
                raise Exception("Gemini failed and Groq client not configured.")
            
            groq_response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a helpful GenAI Assistant. Answer the user based on the provided context."},
                    {"role": "user", "content": prompt}
                ]
            )
            assistant_answer = groq_response.choices[0].message.content
            provider = "Groq (Llama 3)"

        CONVERSATION_HISTORY.append({"user": user_query, "assistant": assistant_answer})
        if len(CONVERSATION_HISTORY) > 5:
            CONVERSATION_HISTORY.pop(0)
            
        save_history()

        return jsonify({
            "answer": assistant_answer,
            "context_used": [c.get('title', 'Unknown') for c in relevant_chunks],
            "provider": provider
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# Initialize data for WSGI servers
load_and_chunk_documents()
load_history()

if __name__ == '__main__':
    app.run(debug=True, port=5000)