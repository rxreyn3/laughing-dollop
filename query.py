from typing import List

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import QueryBundle
from llama_index.postprocessor.flag_embedding_reranker import (
    FlagEmbeddingReranker,
)

import llama_config as config
from log_config import setup_logger
from dataclasses import dataclass
from typing import Any, Optional

# Set up logger
logger = setup_logger(__name__)


def setup_llamaindex():
    """Configure LlamaIndex with Azure OpenAI and Redis"""
    # Initialize models
    logger.info("Initializing LlamaIndex components...")
    embed_model = config.get_embedding_model()
    llm = config.get_llm_model()

    # Set up stores
    vector_store = config.get_vector_store()
    docstore = config.get_document_store()

    # Configure global settings
    Settings.embed_model = embed_model
    Settings.llm = llm

    # Create index from existing vector store
    logger.info("Creating index from vector store...")
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        docstore=docstore,
    )

    return index


def semantic_search(index: VectorStoreIndex, query: str, top_k: int = 3) -> List[str]:
    """
    Perform semantic search on conversations with reranking.
    
    Args:
        index: The vector store index
        query: Search query
        top_k: Number of results to return
        
    Returns:
        List of relevant conversation snippets
    """
    logger.info(f"Performing semantic search for: {query}")
    
    # Create retriever from index with higher initial top_k
    retriever = index.as_retriever(
        similarity_top_k=top_k * 3
    )  # Get more candidates for reranking

    # Create reranker
    reranker = FlagEmbeddingReranker(
        top_n=top_k,  # Final number of results
        model="BAAI/bge-reranker-large",
    )

    # Create query bundle and retrieve nodes
    query_bundle = QueryBundle(query_str=query)
    nodes = retriever.retrieve(query)
    
    logger.info(f"Retrieved {len(nodes)} initial candidates")
    reranked_nodes = reranker.postprocess_nodes(nodes, query_bundle)
    logger.info(f"Reranked to top {len(reranked_nodes)} results")

    # Return the text content and metadata of each reranked node
    results = []
    for node in reranked_nodes:
        thread_ts = node.metadata.get("thread_ts", "Unknown")
        channel_id = node.metadata.get("channel_id", "Unknown")
        participant_count = node.metadata.get("participant_count", 0)
        score = node.score if hasattr(node, "score") else "N/A"
        # Add relevance interpretation
        if score != "N/A":
            if score > 5:
                relevance = "Very High Relevance"
            elif score > 1:
                relevance = "High Relevance"
            elif score > 0:
                relevance = "Moderate Relevance"
            elif score > -1:
                relevance = "Low Relevance"
            else:
                relevance = "Not Relevant"
            score_info = f"Relevance Score: {score:.2f} ({relevance})"
        else:
            score_info = "Relevance Score: N/A"

        metadata_info = (
            f"Thread: {thread_ts}\n"
            f"Channel: {channel_id}\n"
            f"Participants: {participant_count}\n"
            f"{score_info}\n"
            "---\n"
        )
        results.append(f"{metadata_info}{node.text}\n")

    return results


@dataclass
class QueryResponse:
    """Response from the query engine with source information."""
    response: str
    source_nodes: List[Any]
    error: Optional[str] = None


def ask_question(index: VectorStoreIndex, question: str) -> QueryResponse:
    """
    Ask a question and get an answer based on the conversation context.
    
    Args:
        index: The vector store index
        question: The question to answer
        
    Returns:
        QueryResponse object containing the answer and source nodes
    """
    try:
        logger.info(f"Processing question: {question}")
        
        # Create reranker
        logger.debug("Initializing reranker...")
        reranker = FlagEmbeddingReranker(
            top_n=5,  # Keep top 5 most relevant chunks for context
            model="BAAI/bge-reranker-large",
        )

        # Create query engine with reranked nodes
        logger.debug("Setting up query engine...")
        query_engine = index.as_query_engine(
            node_postprocessors=[reranker],
            response_mode="compact",
            streaming=True,
            similarity_top_k=20,  # Get more candidates for reranking
        )

        # Get response
        logger.debug("Executing query...")
        response = query_engine.query(question)
        
        # Get source nodes from the response
        source_nodes = getattr(response, 'source_nodes', [])
        logger.info(f"Query complete. Found {len(source_nodes)} relevant sources.")
        
        return QueryResponse(
            response=str(response),
            source_nodes=source_nodes
        )

    except Exception as e:
        logger.error(f"Error in ask_question: {str(e)}", exc_info=True)
        return QueryResponse(
            response="I encountered an error while processing your question. Please try again later.",
            source_nodes=[],
            error=str(e)
        )


def generate_howto(index: VectorStoreIndex, topic: str) -> str:
    """
    Generate a how-to document based on conversation context.
    
    Args:
        index: The vector store index
        topic: The topic to generate a how-to for
        
    Returns:
        Generated how-to document
    """
    logger.info(f"Generating how-to document for: {topic}")
    
    # Create retriever with higher initial top_k for reranking
    retriever = index.as_retriever(
        similarity_top_k=30
    )  # Get more candidates for reranking

    # Create reranker
    reranker = FlagEmbeddingReranker(
        top_n=10,  # Keep top 10 most relevant chunks for comprehensive how-to
        model="BAAI/bge-reranker-large",
    )

    # Create query engine with structured output and reranking
    query_engine = index.as_query_engine(
        node_postprocessors=[reranker],
        response_mode="tree_summarize",
        streaming=True,
        similarity_top_k=30,  # Match the retriever's top_k
    )

    # Construct a prompt that generates a structured how-to document
    prompt = f"""Generate a concise how-to guide for: {topic}

Based on the conversation history, create a concise document with the following sections:
1. Common Issues and Troubleshooting
2. Additional Tips and Best Practices

Format the response in Markdown with clear headings, bullet points, and code blocks where appropriate.
Include specific examples, links and solutions mentioned in the conversations.
"""

    # Get response
    response = query_engine.query(prompt)

    # Add source information with relevance scores
    query_bundle = QueryBundle(query_str=topic)
    nodes = retriever.retrieve(topic)
    reranked_nodes = reranker.postprocess_nodes(nodes, query_bundle)

    source_info = "\n\n## Source Conversations\nThe following conversations were used as references (with relevance scores):\n"
    for node in reranked_nodes:
        score = node.score if hasattr(node, "score") else "N/A"
        if score != "N/A":
            if score > 5:
                relevance = "Very High Relevance"
            elif score > 1:
                relevance = "High Relevance"
            elif score > 0:
                relevance = "Moderate Relevance"
            elif score > -1:
                relevance = "Low Relevance"
            else:
                relevance = "Not Relevant"
            source_info += f"\n- Thread {node.metadata.get('thread_ts', 'Unknown')}: Score {score:.2f} ({relevance})"
            if node.metadata.get("date"):
                source_info += f" - Date: {node.metadata.get('date')}"
        else:
            source_info += (
                f"\n- Thread {node.metadata.get('thread_ts', 'Unknown')}: Score N/A"
            )

    return str(response) + source_info


def main():
    """Main query interface"""
    logger.info("Setting up LlamaIndex...")
    index = setup_llamaindex()

    while True:
        logger.info("\nWhat would you like to do?")
        logger.info("1. Semantic Search")
        logger.info("2. Ask a Question")
        logger.info("3. Generate How-To Document")
        logger.info("4. Exit")

        choice = input("\nEnter your choice (1-4): ")

        if choice == "4":
            logger.info("Goodbye!")
            break

        if choice == "1":
            query = input("\nEnter your search query: ")
            results = semantic_search(index, query)
            logger.info("\nRelevant conversations:")
            for i, result in enumerate(results, 1):
                logger.info(f"\n--- Result {i} ---")
                logger.info(result)

        elif choice == "2":
            question = input("\nEnter your question: ")
            answer = ask_question(index, question)
            logger.info("\nAnswer:")
            logger.info(answer.response)
            logger.info("\nSource nodes:")
            for i, node in enumerate(answer.source_nodes, 1):
                logger.info(f"\n--- Source {i} ---")
                logger.info(node.text)

        elif choice == "3":
            topic = input("\nWhat topic would you like a how-to guide for? ")
            logger.info("\nGenerating how-to document...")
            howto = generate_howto(index, topic)
            logger.info("\nHow-To Guide:")
            logger.info(howto)

        else:
            logger.warning("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
