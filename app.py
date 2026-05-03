"""
FastAPI backend for RAG AI Decision Assistant
Provides REST API endpoints for question-answering with session management
"""
import asyncio
import json
import logging
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from retriever import get_answer
from config import settings

# Redis import with fallback
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available. Install with: pip install redis")

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG AI Decision Assistant API",
    description="AI decision assistant for volleyball athletes using RAG",
    version="1.0.0"
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis client (with fallback to in-memory)
_redis_client = None
_redis_unavailable = False  # Set True after first failure to skip retries
_fallback_sessions: Dict[str, Dict] = {}  # Fallback if Redis unavailable
SESSION_TTL = 86400  # 24 hours in seconds


def get_redis_client():
    """Get or create Redis client"""
    global _redis_client, _redis_unavailable

    if not REDIS_AVAILABLE or _redis_unavailable:
        return None

    if _redis_client is not None:
        return _redis_client

    try:
        _redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password if settings.redis_password else None,
            ssl=settings.redis_ssl,
            decode_responses=settings.redis_decode_responses,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # Test connection
        _redis_client.ping()
        logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis connection failed: {str(e)}. Using in-memory storage.")
        _redis_client = None
        _redis_unavailable = True
        return None


def get_session(session_id: str) -> Optional[Dict]:
    """Get session from Redis or fallback storage"""
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            data = redis_client.get(f"session:{session_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Error reading from Redis: {str(e)}")
            # Fallback to in-memory
            return _fallback_sessions.get(session_id)
    else:
        return _fallback_sessions.get(session_id)


def save_session(session_id: str, session_data: Dict) -> None:
    """Save session to Redis or fallback storage"""
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            redis_client.setex(
                f"session:{session_id}",
                SESSION_TTL,
                json.dumps(session_data)
            )
        except Exception as e:
            logger.error(f"Error writing to Redis: {str(e)}")
            # Fallback to in-memory
            _fallback_sessions[session_id] = session_data
    else:
        _fallback_sessions[session_id] = session_data


def delete_session(session_id: str) -> bool:
    """Delete session from Redis or fallback storage"""
    redis_client = get_redis_client()
    
    if redis_client:
        try:
            deleted = redis_client.delete(f"session:{session_id}")
            return deleted > 0
        except Exception as e:
            logger.error(f"Error deleting from Redis: {str(e)}")
            # Fallback to in-memory
            if session_id in _fallback_sessions:
                del _fallback_sessions[session_id]
                return True
            return False
    else:
        if session_id in _fallback_sessions:
            del _fallback_sessions[session_id]
            return True
        return False


class QueryRequest(BaseModel):
    """Request model for asking questions"""
    user_id: Optional[str] = Field(None, description="User identifier")
    question: str = Field(..., min_length=1, max_length=1000, description="User's question")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation tracking")


class QueryResponse(BaseModel):
    """Response model for answers"""
    answer: str
    session_id: str
    sources: list
    confidence: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    timestamp: str


def get_or_create_session(session_id: Optional[str] = None) -> str:
    """
    Get existing session or create a new one
    
    Args:
        session_id: Optional existing session ID
        
    Returns:
        Session ID string
    """
    if session_id:
        existing_session = get_session(session_id)
        if existing_session:
            return session_id
    
    new_session_id = str(uuid.uuid4())
    session_data = {
        "created_at": datetime.utcnow().isoformat(),
        "messages": []
    }
    save_session(new_session_id, session_data)
    return new_session_id


@app.get("/")
async def home():
    """Serve the web UI"""
    return FileResponse("templates/index.html")

@app.get("/api/health", response_model=HealthResponse)
async def health_check_api():
    """Health check endpoint (API)"""
    return {
        "status": "healthy",
        "message": "RAG AI Decision Assistant API is running ✅",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check endpoint"""
    try:
        # Try to load the vector store to verify system is ready
        from retriever import load_vector_store
        load_vector_store()
        
        # Check Redis connection
        redis_status = "not configured (using in-memory)"
        redis_client = get_redis_client()
        if redis_client:
            try:
                redis_client.ping()
                redis_status = "connected"
            except Exception as e:
                redis_status = f"disconnected: {str(e)} (using fallback)"
        
        return {
            "status": "healthy",
            "message": f"System is operational. Knowledge base loaded. Redis: {redis_status}",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"System not ready: {str(e)}"
        )


@app.post("/ask", response_model=QueryResponse)
async def ask(query: QueryRequest):
    """
    Main endpoint for asking questions
    
    Args:
        query: Query request with question and optional session info
        
    Returns:
        QueryResponse with answer, sources, and metadata
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        # Validate question
        if not query.question or not query.question.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty"
            )
        
        # Get or create session
        session_id = get_or_create_session(query.session_id)
        
        # Get answer from RAG system
        logger.info(f"Processing question for session {session_id}")
        result = get_answer(query.question, user_id=query.user_id or session_id)
        
        # Update session history
        session_data = get_session(session_id) or {
            "created_at": datetime.utcnow().isoformat(),
            "messages": []
        }
        session_data["messages"].append({
            "question": query.question,
            "answer": result["answer"],
            "timestamp": datetime.utcnow().isoformat()
        })
        session_data["updated_at"] = datetime.utcnow().isoformat()
        save_session(session_id, session_data)
        
        # Return structured response
        return QueryResponse(
            answer=result["answer"],
            session_id=session_id,
            sources=result.get("sources", []),
            confidence=result.get("confidence", 0.0),
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing question: {str(e)}"
        )


@app.get("/sessions/{session_id}")
async def get_session_endpoint(session_id: str):
    """Get session history"""
    session_data = get_session(session_id)
    
    if not session_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return session_data


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session"""
    deleted = delete_session(session_id)
    
    if deleted:
        return {"message": "Session deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )


_ALLOWED_EXTS = {".pdf", ".docx", ".txt", ".md"}

@app.get("/files")
async def list_files():
    data_dir = Path(settings.data_dir)
    files = []
    if data_dir.exists():
        for f in sorted(data_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if f.is_file() and f.suffix.lower() in _ALLOWED_EXTS:
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "type": f.suffix.lower().lstrip(".")
                })
    return {"files": files}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise HTTPException(status_code=400, detail=f"Unsupported type '{ext}'. Allowed: PDF, DOCX, TXT, MD")
    if "/" in file.filename or "\\" in file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    dest = Path(settings.data_dir) / file.filename
    content = await file.read()
    dest.write_bytes(content)
    logger.info(f"Uploaded {file.filename} ({len(content):,} bytes)")
    return {"filename": file.filename, "size": len(content)}


@app.delete("/files/{filename}")
async def delete_file(filename: str):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = Path(settings.data_dir) / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    path.unlink()
    logger.info(f"Deleted {filename}")
    return {"message": f"{filename} deleted"}


_reindex_state: Dict = {"status": "idle", "message": ""}


@app.get("/reindex/status")
async def reindex_status():
    return _reindex_state


@app.post("/reindex")
async def trigger_reindex():
    global _reindex_state
    if _reindex_state["status"] == "running":
        raise HTTPException(status_code=409, detail="Reindex already in progress")
    _reindex_state = {"status": "running", "message": "Rebuilding knowledge base…"}
    asyncio.create_task(_run_reindex())
    return {"message": "Reindex started"}


async def _run_reindex():
    global _reindex_state
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "ingest.py",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(__file__).parent)
        )
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            import retriever
            retriever._vector_store = None
            retriever._qa_chain = None
            _reindex_state = {"status": "done", "message": "Knowledge base rebuilt successfully"}
            logger.info("Reindex completed")
        else:
            _reindex_state = {"status": "error", "message": stderr.decode()[:400]}
            logger.error(f"Reindex failed: {stderr.decode()}")
    except Exception as e:
        _reindex_state = {"status": "error", "message": str(e)}
        logger.error(f"Reindex error: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )
