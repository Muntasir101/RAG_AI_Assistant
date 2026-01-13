"""
RAG retrieval module for AI Decision Assistant
Implements strict anti-hallucination controls to ensure answers only from knowledge base
"""
import pickle
import logging
from pathlib import Path
from typing import Dict, List, Optional

from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# Try to import Gemini
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from config import settings

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables for lazy loading
_vector_store: Optional[FAISS] = None
_qa_chain: Optional[object] = None


def load_vector_store() -> FAISS:
    """
    Load the FAISS vector store from disk
    
    Returns:
        FAISS vector store instance
        
    Raises:
        FileNotFoundError: If index file doesn't exist
        Exception: If loading fails
    """
    global _vector_store
    
    if _vector_store is not None:
        return _vector_store
    
    index_path = Path(settings.index_file)
    
    if not index_path.exists():
        raise FileNotFoundError(
            f"Index file '{settings.index_file}' not found. "
            "Please run ingest.py first to create the knowledge base index."
        )
    
    try:
        logger.info(f"Loading vector store from {settings.index_file}...")
        with open(settings.index_file, "rb") as f:
            _vector_store = pickle.load(f)
        logger.info("Vector store loaded successfully")
        return _vector_store
    except Exception as e:
        logger.error(f"Error loading vector store: {str(e)}")
        raise


def get_qa_chain():
    """
    Initialize and return the QA chain with anti-hallucination prompt
    
    Returns:
        RetrievalQA chain instance
    """
    global _qa_chain
    
    if _qa_chain is not None:
        return _qa_chain
    
    try:
        vector_store = load_vector_store()
        
        # Create retriever
        retriever = vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": settings.top_k_results}
        )
        
        # Anti-hallucination system prompt
        # This ensures the model only answers based on retrieved context
        prompt_template = """You are a specialized AI decision assistant for volleyball athletes. 
Your role is to provide accurate, evidence-based answers ONLY from the provided knowledge base.

CRITICAL RULES:
1. Answer ONLY based on the context provided below
2. If the context does not contain enough information to answer the question, say: "I don't have enough information in my knowledge base to answer this question accurately."
3. Do NOT make up information, statistics, or facts
4. Do NOT provide general knowledge that is not in the context
5. If asked about something not in the knowledge base, politely decline and suggest consulting the knowledge base
6. Support your answers with specific details from the context when available
7. You can answer in both Russian and English, matching the language of the question

Context from knowledge base:
{context}

Question: {question}

Answer (based ONLY on the context above):"""

        PROMPT = PromptTemplate(
            template=prompt_template,
            input_variables=["context", "question"]
        )
        
        # Initialize LLM based on provider
        if settings.provider.lower() == "gemini":
            if not GEMINI_AVAILABLE:
                raise ValueError("Gemini support not available. Install: pip install langchain-google-genai")
            if not settings.gemini_api_key:
                raise ValueError("Gemini API key required. Set GEMINI_API_KEY in .env file")
            llm = ChatGoogleGenerativeAI(
                model=settings.gemini_model,
                temperature=settings.temperature,
                google_api_key=settings.gemini_api_key
            )
        elif settings.provider.lower() == "deepseek":
            if not settings.deepseek_api_key:
                raise ValueError("DeepSeek API key required. Set DEEPSEEK_API_KEY in .env file")
            llm = ChatOpenAI(
                model=settings.deepseek_model,
                temperature=settings.temperature,
                openai_api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url
            )
        else:
            # Use OpenAI
            if not settings.openai_api_key or settings.openai_api_key == "your_openai_api_key_here":
                raise ValueError("OpenAI API key required. Set OPENAI_API_KEY in .env file")
            llm = ChatOpenAI(
                model_name=settings.openai_model,
                temperature=settings.temperature,
                openai_api_key=settings.openai_api_key,
                base_url=settings.openai_base_url
            )
        
        # Create QA chain using LangChain 1.x API
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | PROMPT
            | llm
            | StrOutputParser()
        )
        
        _qa_chain = {
            "chain": rag_chain,
            "retriever": retriever
        }
        
        logger.info("QA chain initialized successfully")
        return _qa_chain
        
    except Exception as e:
        logger.error(f"Error initializing QA chain: {str(e)}")
        raise


def get_answer(question: str, user_id: Optional[str] = None) -> Dict[str, any]:
    """
    Get answer to a question using RAG pipeline
    
    Args:
        question: User's question
        user_id: Optional user ID for logging/tracking
        
    Returns:
        Dictionary with 'answer', 'sources', and 'confidence' fields
        
    Raises:
        Exception: If retrieval or generation fails
    """
    if not question or not question.strip():
        return {
            "answer": "Please provide a valid question.",
            "sources": [],
            "confidence": 0.0
        }
    
    try:
        logger.info(f"Processing question from user {user_id}: {question[:100]}...")
        
        qa_chain_dict = get_qa_chain()
        rag_chain = qa_chain_dict["chain"]
        retriever = qa_chain_dict["retriever"]
        
        # Retrieve documents
        source_documents = retriever.invoke(question)
        
        # Run the QA chain
        answer = rag_chain.invoke(question)
        
        # Extract source information
        sources = []
        for doc in source_documents[:3]:  # Limit to top 3 sources
            sources.append({
                "content_preview": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content,
                "metadata": doc.metadata if hasattr(doc, 'metadata') else {}
            })
        
        # Simple confidence metric based on number of sources
        confidence = min(1.0, len(source_documents) / settings.top_k_results)
        
        logger.info(f"Answer generated successfully (confidence: {confidence:.2f})")
        
        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence
        }
        
    except FileNotFoundError as e:
        logger.error(f"Index not found: {str(e)}")
        return {
            "answer": "Knowledge base not initialized. Please run the ingestion process first.",
            "sources": [],
            "confidence": 0.0
        }
    except Exception as e:
        logger.error(f"Error generating answer: {str(e)}")
        return {
            "answer": f"I encountered an error while processing your question: {str(e)}. Please try again.",
            "sources": [],
            "confidence": 0.0
        }


# Initialize on module import (lazy loading)
try:
    load_vector_store()
except FileNotFoundError:
    logger.warning("Vector store not found. Run ingest.py to create the index.")
except Exception as e:
    logger.error(f"Error during initialization: {str(e)}")
