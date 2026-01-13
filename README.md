# RAG AI Decision Assistant for Volleyball Athletes

A specialized AI decision assistant built with Retrieval-Augmented Generation (RAG) that provides evidence-based answers exclusively from a knowledge base. Designed specifically for volleyball athletes, supporting both Russian and English languages.

**Current Status**: ✅ Fully operational with Gemini 3 Flash Preview, local embeddings, and multi-provider support.

## 🎯 Key Features

- **RAG-Based Architecture**: Answers only from provided knowledge base (no hallucinations)
- **Multi-Provider Support**: Works with OpenAI, DeepSeek, or Google Gemini
- **Local Embeddings Fallback**: Uses HuggingFace embeddings when API quota is exceeded
- **Structured Responses**: Returns answers with source citations and confidence scores
- **Session Management**: Tracks conversation history per user
- **Triple Interface**: Web UI, REST API, and Telegram bot
- **Production Ready**: Docker support, error handling, logging

## 🏗️ Architecture

```
┌─────────────────┐
│  Knowledge Base │  (PDF, DOCX, TXT, MD files)
│  (Documents)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   ingest.py     │  → Text Chunking → Embeddings → FAISS Index
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  retriever.py   │  → Vector Search → Context Retrieval → LLM
└────────┬────────┘
         │
         ├──────────────┬──────────────┐
         ▼              ▼              ▼
    ┌─────────┐   ┌──────────┐   ┌──────────┐
    │ app.py  │   │ bot.py   │   │  Users   │
    │ (API)   │   │(Telegram)│   │          │
    └─────────┘   └──────────┘   └──────────┘
```

### Components

1. **ingest.py**: Document ingestion and indexing
   - Loads documents (PDF, DOCX, TXT, MD)
   - Chunks text with configurable size/overlap
   - Creates embeddings using OpenAI
   - Builds FAISS vector index

2. **retriever.py**: RAG retrieval and generation
   - Loads FAISS vector store
   - Performs similarity search
   - Uses strict anti-hallucination prompts
   - Returns structured responses with sources

3. **app.py**: FastAPI REST API
   - `/ask` endpoint for questions
   - Session management
   - Health checks
   - CORS enabled

4. **bot.py**: Telegram bot interface
   - Modern python-telegram-bot v20+ API
   - User session tracking
   - Multilingual support

5. **config.py**: Centralized configuration
   - Environment variable management
   - Pydantic settings validation

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- API key for one of the supported providers:
  - **Google Gemini** (recommended) - Get key at https://ai.google.dev
  - OpenAI - Get key at https://platform.openai.com
  - DeepSeek - Get key at https://platform.deepseek.com
- Telegram Bot Token (optional, for bot interface)
- Knowledge base documents

### Installation

```bash
# Clone repository
git clone <your-repo-url>
cd Rag_AI_Assistant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Configuration

1. Create `.env` file:

```bash
# Provider Selection (openai, deepseek, or gemini)
PROVIDER=gemini

# OpenAI Configuration (if using OpenAI)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# DeepSeek Configuration (if using DeepSeek)
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_MODEL=deepseek-chat

# Google Gemini Configuration (if using Gemini)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3-flash-preview

# Telegram Bot (optional)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# RAG Configuration
TEMPERATURE=0.0
CHUNK_SIZE=1000
CHUNK_OVERLAP=100
TOP_K_RESULTS=3

# Data Configuration
DATA_DIR=knowledge_data
INDEX_FILE=faiss_index.pkl

# Logging
LOG_LEVEL=INFO
```

**Note**: The system will automatically use local HuggingFace embeddings if the OpenAI API quota is exceeded, ensuring the system always works even without API access for embeddings.

2. Prepare knowledge base:

```bash
mkdir knowledge_data
# Add your documents (PDF, DOCX, TXT, MD) to knowledge_data/
```

3. Ingest knowledge base:

```bash
python ingest.py
```

This creates `faiss_index.pkl` with your indexed documents.

### Running

**Option 1: Web UI (Recommended)**
```bash
python app.py
# Open browser: http://localhost:8000
# Beautiful web interface with chat UI
```

**Option 2: REST API only**
```bash
python app.py
# API available at http://localhost:8000
# Web UI at http://localhost:8000
# API docs at http://localhost:8000/docs
```

**Option 3: Telegram Bot**
```bash
python bot.py
```

**Option 4: Both Web UI and Telegram Bot**
```bash
# Terminal 1
python app.py

# Terminal 2
python bot.py
```

## 📖 Usage

### Web UI

The easiest way to interact with the assistant is through the web interface:

1. Start the server:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

3. Start asking questions in the chat interface!

**Features:**
- Clean, modern chat interface
- Real-time responses
- Confidence scores
- Source citations
- Session management
- Responsive design (works on mobile)

### REST API

**Health Check:**
```bash
curl http://localhost:8000/health
```

**Ask a Question:**
```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the key strategies for serving in volleyball?",
    "user_id": "user123"
  }'
```

**Response:**
```json
{
  "answer": "Based on the knowledge base...",
  "session_id": "uuid-here",
  "sources": [
    {
      "content_preview": "...",
      "metadata": {}
    }
  ],
  "confidence": 0.85,
  "timestamp": "2024-01-01T12:00:00"
}
```

### Telegram Bot

1. Create a bot via [@BotFather](https://t.me/botfather)
2. Get your bot token
3. Add token to `.env` file
4. Run `python bot.py`
5. Start chatting with your bot

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions.

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROVIDER` | AI provider: `openai`, `deepseek`, or `gemini` | `gemini` |
| `OPENAI_API_KEY` | OpenAI API key (if using OpenAI) | - |
| `DEEPSEEK_API_KEY` | DeepSeek API key (if using DeepSeek) | - |
| `GEMINI_API_KEY` | Gemini API key (if using Gemini) | - |
| `OPENAI_MODEL` | OpenAI model name | `gpt-4o-mini` |
| `DEEPSEEK_MODEL` | DeepSeek model name | `deepseek-chat` |
| `GEMINI_MODEL` | Gemini model name | `gemini-3-flash-preview` |
| `EMBEDDING_MODEL` | Embedding model (OpenAI) | `text-embedding-3-small` |
| `TEMPERATURE` | LLM temperature (0.0 = deterministic) | `0.0` |
| `CHUNK_SIZE` | Text chunk size | `1000` |
| `CHUNK_OVERLAP` | Chunk overlap | `100` |
| `TOP_K_RESULTS` | Number of retrieved chunks | `3` |
| `DATA_DIR` | Knowledge base directory | `knowledge_data` |
| `INDEX_FILE` | FAISS index file | `faiss_index.pkl` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (optional) | - |
| `LOG_LEVEL` | Logging level | `INFO` |

### Anti-Hallucination Measures

1. **Strict System Prompt**: Explicitly instructs model to only use provided context
2. **Low Temperature**: Set to 0.0 for deterministic, factual responses
3. **Source Citation**: Returns source documents with answers
4. **Confidence Scoring**: Indicates answer reliability
5. **Context Limitation**: Only answers from retrieved knowledge base chunks

## 📁 Project Structure

```
Rag_AI_Assistant/
├── app.py              # FastAPI REST API + Web UI
├── bot.py              # Telegram bot
├── ingest.py           # Document ingestion and indexing
├── retriever.py        # RAG retrieval and generation
├── config.py           # Configuration management
├── requirements.txt    # Python dependencies
├── templates/          # Web UI templates
│   └── index.html      # Main web interface
├── static/             # Static files (CSS, JS)
│   ├── style.css       # Web UI styling
│   └── script.js       # Web UI JavaScript
├── Dockerfile          # Docker image definition
├── docker-compose.yml  # Docker Compose configuration
├── .gitignore          # Git ignore rules
├── .dockerignore       # Docker ignore rules
├── README.md           # This file
├── DEPLOYMENT.md       # Deployment guide
└── knowledge_data/     # Your documents go here
```

## 🧪 Testing

```bash
# Test API health
curl http://localhost:8000/health

# Test question endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test question"}'
```

## 🔒 Security

- ✅ Environment variables for secrets
- ✅ `.gitignore` to prevent committing sensitive files
- ✅ Input validation on API endpoints
- ✅ Error handling without exposing internals
- ✅ Multi-provider support for redundancy
- ✅ Local embeddings fallback (no API dependency for embeddings)
- ⚠️ **Production**: Restrict CORS origins, enable HTTPS, use firewall

## 🤖 Supported AI Providers

### Google Gemini (Recommended)
- **Model**: `gemini-3-flash-preview` (default)
- **Advantages**: Fast, cost-effective, good multilingual support
- **Setup**: Get API key from https://ai.google.dev
- **Status**: ✅ Currently configured and working

### OpenAI
- **Model**: `gpt-4o-mini` (default)
- **Advantages**: High quality, reliable
- **Setup**: Get API key from https://platform.openai.com
- **Note**: Requires quota/billing for embeddings

### DeepSeek
- **Model**: `deepseek-chat` (default)
- **Advantages**: Cost-effective alternative
- **Setup**: Get API key from https://platform.deepseek.com
- **Note**: Uses OpenAI for embeddings (DeepSeek doesn't provide embeddings API)

### Embeddings
- **Primary**: OpenAI embeddings (if API key available)
- **Fallback**: Local HuggingFace embeddings (automatic if OpenAI quota exceeded)
- **Model**: `paraphrase-multilingual-MiniLM-L12-v2` (supports English and Russian)

## 📝 API Endpoints

### `GET /`
Health check endpoint

### `GET /health`
Detailed health check with system status

### `POST /ask`
Ask a question

**Request:**
```json
{
  "question": "Your question here",
  "user_id": "optional_user_id",
  "session_id": "optional_session_id"
}
```

**Response:**
```json
{
  "answer": "Answer text",
  "session_id": "session_uuid",
  "sources": [...],
  "confidence": 0.85,
  "timestamp": "ISO timestamp"
}
```

### `GET /sessions/{session_id}`
Get session history

### `DELETE /sessions/{session_id}`
Delete a session

## 🐛 Troubleshooting

### Index file not found
```bash
python ingest.py  # Re-run ingestion
```

### API Provider Errors

**OpenAI API errors:**
- Verify API key is correct
- Check API quota/limits
- System will automatically fall back to local embeddings if quota exceeded

**Gemini API errors:**
- Verify API key is correct
- Check quota at https://ai.dev/rate-limit
- Try a different model (e.g., `gemini-2.0-flash`)

**DeepSeek API errors:**
- Verify API key is correct
- Check account balance
- Note: DeepSeek requires OpenAI API key for embeddings

### Embeddings Issues
- If OpenAI quota exceeded, system automatically uses local HuggingFace embeddings
- Local embeddings require `sentence-transformers` package (installed automatically)
- First run will download the model (~400MB)

### Telegram bot not responding
- Verify bot token in `.env`
- Check API is running (`http://localhost:8000/health`)
- Review bot logs

### Memory issues
- Reduce `CHUNK_SIZE` and `TOP_K_RESULTS`
- Use smaller embedding model
- Consider FAISS-GPU for faster processing

## 🚧 Future Enhancements

- [x] Multi-provider support (OpenAI, DeepSeek, Gemini)
- [x] Local embeddings fallback
- [x] Web UI interface
- [ ] Redis for session storage
- [ ] Advanced caching
- [ ] Multi-tenant support
- [ ] Analytics and usage tracking
- [ ] Fine-tuning on domain-specific data
- [ ] Additional embedding providers (Cohere, HuggingFace Inference API)

## 📄 License

[Your License Here]

## 👥 Contributing

[Your Contributing Guidelines Here]

## 📧 Support

For issues and questions, please open an issue in the repository.

---

## 📊 Current System Status

- ✅ **Knowledge Base**: 6 documents indexed (31 chunks)
- ✅ **Embeddings**: Local HuggingFace (multilingual)
- ✅ **LLM Provider**: Google Gemini (gemini-3-flash-preview)
- ✅ **Vector Store**: FAISS index (457 MB)
- ✅ **API Server**: FastAPI on port 8000
- ✅ **Languages**: English and Russian supported

## 🎓 Example Questions

Try asking:
- "When should I use a jump serve?"
- "Что делать при счете 24-24?" (Russian)
- "How do I decide when to substitute a player?"
- "What are the responsibilities of a libero?"
- "When should I call a timeout?"

---

**Built with**: Python, FastAPI, LangChain, Google Gemini, OpenAI, DeepSeek, FAISS, HuggingFace, python-telegram-bot
