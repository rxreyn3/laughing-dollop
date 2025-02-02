import os
from typing import List
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline, IngestionCache, DocstoreStrategy
from llama_index.core.node_parser import TokenTextSplitter
import llama_config as config

# Load environment variables
load_dotenv()

def get_db_connection():
    """Create database connection"""
    engine = create_engine("sqlite:///slack_messages.db")
    return engine.connect()

def fetch_conversations() -> List[Document]:
    """Fetch all conversations from SQLite and convert them to Documents"""
    conn = get_db_connection()
    
    # Fetch all conversations
    query = text("""
        SELECT thread_id, thread_content 
        FROM conversations 
        WHERE thread_content IS NOT NULL
    """)
    
    result = conn.execute(query)
    documents = []
    
    for row in result:
        thread_id, content = row
        if content:
            # Create a Document with metadata for each conversation
            doc = Document(
                text=content,
                metadata={
                    "thread_id": thread_id,
                    "source": "slack_conversation"
                },
                id_=f"thread_{thread_id}"  # Deterministic ID for caching
            )
            documents.append(doc)
    
    conn.close()
    return documents

def setup_ingestion_pipeline():
    """Configure ingestion pipeline with Redis components and Azure OpenAI"""
    # Create ingestion pipeline with transformations
    pipeline = IngestionPipeline(
        transformations=[
            # Split conversations into token-sized chunks for better GPT-4 context
            TokenTextSplitter(chunk_size=1024, chunk_overlap=200),
            # Generate embeddings
            config.get_embedding_model(),
        ],
        # Store documents in Redis
        docstore=config.get_document_store(),
        # Store vectors in Redis
        vector_store=config.get_vector_store(),
        # Cache transformations in Redis
        cache=IngestionCache(
            cache=config.get_cache_store(),
            collection="slack_cache",
        ),
        # Handle document updates
        docstore_strategy=DocstoreStrategy.UPSERTS,
    )
    
    return pipeline

def main():
    """Main ingestion pipeline"""
    print("Starting ingestion pipeline...")
    
    # Set up ingestion pipeline
    pipeline = setup_ingestion_pipeline()
    
    # Fetch documents
    print("Fetching conversations from database...")
    documents = fetch_conversations()
    print(f"Found {len(documents)} conversations")
    
    # Run ingestion pipeline
    print("Running ingestion pipeline...")
    nodes = pipeline.run(documents=documents)
    print(f"Ingested {len(nodes)} nodes")
    
    print("Ingestion complete!")

if __name__ == "__main__":
    main()
