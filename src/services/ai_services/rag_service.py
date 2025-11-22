"""
Retrieval-Augmented Generation (RAG) service
Handles document processing, context retrieval, and knowledge integration
"""
import os
import json
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger = logging.getLogger(__name__)
    logger.warning("NumPy not available - using simplified embedding operations")

logger = logging.getLogger(__name__)

@dataclass
class Document:
    """Document representation for RAG system"""
    id: str
    content: str
    metadata: Dict
    embedding: Optional[List[float]] = None
    timestamp: float = 0.0

class RAGService:
    """Retrieval-Augmented Generation service for context-aware responses"""
    
    def __init__(self):
        self.documents: List[Document] = []
        self.document_store: Dict[str, Document] = {}
        self.embeddings_cache: Dict[str, List[float]] = {}
        self.knowledge_base_path = "data/knowledge_base"
        self.max_context_length = 4000
        self.similarity_threshold = 0.7
        
        self.knowledge_base_loaded = False

    def _ensure_knowledge_base_loaded(self):
        """Ensure the knowledge base is loaded before use"""
        if not self.knowledge_base_loaded:
            self._load_knowledge_base()
            self.knowledge_base_loaded = True
    
    def _load_knowledge_base(self):
        """Load existing knowledge base from disk"""
        try:
            kb_path = Path(self.knowledge_base_path)
            if kb_path.exists():
                for file_path in kb_path.glob("*.json"):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        doc = Document(**data)
                        self.add_document(doc)
                logger.info(f"Loaded {len(self.documents)} documents from knowledge base")
            else:
                logger.info("No existing knowledge base found, creating new one")
                self._initialize_default_knowledge()
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            self._initialize_default_knowledge()
    
    def _initialize_default_knowledge(self):
        """Initialize with default sales training knowledge"""
        default_docs = [
            {
                "id": "sales_techniques_basic",
                "content": """
                Basic Sales Techniques:
                1. NEPQ (Neuro Emotional Persuasion Questioning) - Ask questions that create emotional responses
                2. Active Listening - Focus entirely on the prospect, ask follow-up questions
                3. Feature-Benefit-Proof - Present features, explain benefits, provide proof
                4. Objection Handling - Listen, acknowledge, respond with facts and benefits
                5. Closing Techniques - Assumptive close, urgency close, alternative choice close
                """,
                "metadata": {
                    "category": "sales_techniques",
                    "difficulty": "basic",
                    "tags": ["nepq", "listening", "closing", "objections"]
                }
            },
            {
                "id": "prospect_personas",
                "content": """
                Common Prospect Personas:
                1. The Analytical - Needs data, statistics, detailed information
                2. The Driver - Wants quick decisions, bottom line results
                3. The Expressive - Enjoys relationships, stories, social proof
                4. The Amiable - Prefers trust-building, low-pressure approaches
                5. The Skeptical - Questions everything, needs strong proof
                """,
                "metadata": {
                    "category": "personas",
                    "difficulty": "intermediate",
                    "tags": ["personality", "approach", "communication"]
                }
            },
            {
                "id": "objection_responses",
                "content": """
                Common Objections and Responses:
                1. "It's too expensive" - Focus on value, ROI, cost of inaction
                2. "I need to think about it" - Uncover real concerns, create urgency
                3. "I'm not interested" - Ask permission to ask why, find pain points
                4. "We're happy with current solution" - Identify gaps and improvements
                5. "I don't have time" - Respect time, offer quick value demonstration
                """,
                "metadata": {
                    "category": "objection_handling",
                    "difficulty": "intermediate",
                    "tags": ["objections", "responses", "techniques"]
                }
            }
        ]
        
        for doc_data in default_docs:
            doc = Document(**doc_data, timestamp=datetime.now().timestamp())
            self.add_document(doc)
    
    def add_document(self, document: Document):
        """Add a document to the knowledge base"""
        self.documents.append(document)
        self.document_store[document.id] = document
        
        document.embedding = self._generate_simple_embedding(document.content)
        
        logger.debug(f"Added document: {document.id}")
    
    def _generate_simple_embedding(self, text: str) -> List[float]:
        """Generate a simple text embedding (placeholder for proper embeddings)"""
        words = text.lower().split()
        vocab = set(words)
        
        embedding = [0.0] * 100
        for i, word in enumerate(list(vocab)[:100]):
            embedding[i] = words.count(word) / len(words) if words else 0.0
        
        if HAS_NUMPY:
            embedding_array = np.array(embedding)
            norm = np.linalg.norm(embedding_array)
            if norm > 0:
                embedding_array = embedding_array / norm
            return embedding_array.tolist()
        else:
            norm = sum(x*x for x in embedding) ** 0.5
            if norm > 0:
                embedding = [x / norm for x in embedding]
            return embedding
    
    def retrieve_relevant_context(self, query: str, max_docs: int = 3) -> List[Document]:
        """Retrieve relevant documents for the given query"""
        self._ensure_knowledge_base_loaded()
        if not self.documents:
            return []
        
        query_embedding = self._generate_simple_embedding(query)
        
        similarities = []
        for doc in self.documents:
            if doc.embedding is not None:
                if HAS_NUMPY:
                    similarity = np.dot(query_embedding, doc.embedding)
                else:
                    similarity = sum(a * b for a, b in zip(query_embedding, doc.embedding))
                similarities.append((doc, similarity))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        relevant_docs = []
        for doc, sim in similarities[:max_docs]:
            if sim >= self.similarity_threshold:
                relevant_docs.append(doc)
        
        return relevant_docs
    
    def build_context(self, query: str, conversation_history: List[Dict], user_profile: Dict = None) -> str:
        """Build context for the AI model using RAG"""
        context_parts = []
        
        relevant_docs = self.retrieve_relevant_context(query)
        if relevant_docs:
            context_parts.append("=== RELEVANT KNOWLEDGE ===")
            for doc in relevant_docs:
                context_parts.append(f"[{doc.metadata.get('category', 'general')}] {doc.content}")
        
        if conversation_history:
            context_parts.append("\n=== CONVERSATION HISTORY ===")
            for entry in conversation_history[-3:]:
                context_parts.append(f"User: {entry.get('user', '')}")
                context_parts.append(f"Assistant: {entry.get('response', '')}")
        
        if user_profile:
            context_parts.append("\n=== USER PROFILE ===")
            for key, value in user_profile.items():
                context_parts.append(f"{key}: {value}")
        
        full_context = "\n".join(context_parts)
        if len(full_context) > self.max_context_length:
            full_context = full_context[:self.max_context_length] + "..."
        
        return full_context
    
    def enhance_prompt(self, base_prompt: str, query: str, conversation_history: List[Dict], user_profile: Dict = None) -> str:
        """Enhance the base prompt with RAG context"""
        rag_context = self.build_context(query, conversation_history, user_profile)
        
        enhanced_prompt = f"""
{rag_context}

=== CURRENT SITUATION ===
{base_prompt}

User Query: {query}

Please respond as Mary, incorporating relevant knowledge from above while maintaining character consistency.
"""
        return enhanced_prompt
    
    def add_sales_knowledge(self, content: str, category: str, tags: List[str] = None):
        """Add new sales knowledge to the system"""
        doc_id = f"sales_{category}_{datetime.now().timestamp()}"
        
        document = Document(
            id=doc_id,
            content=content,
            metadata={
                "category": category,
                "tags": tags or [],
                "added_by": "system",
                "timestamp": datetime.now().isoformat()
            },
            timestamp=datetime.now().timestamp()
        )
        
        self.add_document(document)
        logger.info(f"Added sales knowledge: {doc_id}")
    
    def search_knowledge(self, query: str, category: str = None) -> List[Dict]:
        """Search knowledge base for specific information"""
        results = []
        
        for doc in self.documents:
            if category and doc.metadata.get('category') != category:
                continue
            
            if query.lower() in doc.content.lower():
                results.append({
                    "id": doc.id,
                    "content": doc.content,
                    "metadata": doc.metadata,
                    "relevance_score": self._calculate_relevance(query, doc.content)
                })
        
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results
    
    def _calculate_relevance(self, query: str, content: str) -> float:
        """Calculate relevance score between query and content"""
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        
        if not query_words:
            return 0.0
        
        intersection = query_words.intersection(content_words)
        return len(intersection) / len(query_words)
    
    def get_stats(self) -> Dict:
        """Get RAG system statistics"""
        categories = {}
        for doc in self.documents:
            category = doc.metadata.get('category', 'uncategorized')
            categories[category] = categories.get(category, 0) + 1
        
        return {
            "total_documents": len(self.documents),
            "categories": categories,
            "knowledge_base_path": self.knowledge_base_path,
            "max_context_length": self.max_context_length,
            "similarity_threshold": self.similarity_threshold
        }

rag_service = RAGService()