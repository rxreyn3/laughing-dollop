from typing import List
from llama_index.core import VectorStoreIndex, Settings
import llama_config as config

def setup_llamaindex():
    """Configure LlamaIndex with Azure OpenAI and Redis"""
    # Initialize models
    embed_model = config.get_embedding_model()
    llm = config.get_llm_model()
    
    # Set up stores
    vector_store = config.get_vector_store()
    docstore = config.get_document_store()
    
    # Configure global settings
    Settings.embed_model = embed_model
    Settings.llm = llm
    
    # Create index from existing vector store
    index = VectorStoreIndex.from_vector_store(
        vector_store,
        docstore=docstore,
    )
    
    return index

def semantic_search(index: VectorStoreIndex, query: str, top_k: int = 3) -> List[str]:
    """Perform semantic search on conversations"""
    # Create retriever from index
    retriever = index.as_retriever(similarity_top_k=top_k)
    
    # Retrieve similar nodes
    nodes = retriever.retrieve(query)
    
    # Return the text content and metadata of each node
    results = []
    for node in nodes:
        thread_ts = node.metadata.get("thread_ts", "Unknown")
        channel_id = node.metadata.get("channel_id", "Unknown")
        participant_count = node.metadata.get("participant_count", 0)
        
        metadata_info = (
            f"Thread: {thread_ts}\n"
            f"Channel: {channel_id}\n"
            f"Participants: {participant_count}\n"
            "---\n"
        )
        results.append(f"{metadata_info}{node.text}\n")
    
    return results

def ask_question(index: VectorStoreIndex, question: str) -> str:
    """Ask a question and get an answer based on the conversation context"""
    # Create query engine with response synthesis
    query_engine = index.as_query_engine(
        response_mode="compact",
        streaming=True,
    )
    
    # Get response
    response = query_engine.query(question)
    
    return str(response)

def generate_howto(index: VectorStoreIndex, topic: str) -> str:
    """Generate a how-to document based on conversation context"""
    # Create query engine with structured output
    query_engine = index.as_query_engine(
        response_mode="tree_summarize",
        streaming=True,
        similarity_top_k=20,
    )
    
    # Construct a prompt that generates a structured how-to document
    prompt = f"""Generate a comprehensive how-to guide for: {topic}

Based on the conversation history, create a detailed document with the following sections:
1. Problem Description
2. Prerequisites (if any)
3. Step-by-Step Solution
4. Common Issues and Troubleshooting
5. Additional Tips and Best Practices

Format the response in Markdown with clear headings, bullet points, and code blocks where appropriate.
Include specific examples and solutions mentioned in the conversations.
"""
    
    # Get response
    response = query_engine.query(prompt)
    return str(response)

def main():
    """Main query interface"""
    print("Setting up LlamaIndex...")
    index = setup_llamaindex()
    
    while True:
        print("\nWhat would you like to do?")
        print("1. Semantic Search")
        print("2. Ask a Question")
        print("3. Generate How-To Document")
        print("4. Exit")
        
        choice = input("Enter your choice (1-4): ")
        
        if choice == "4":
            break
        
        if choice == "1":
            query = input("\nEnter your search query: ")
            results = semantic_search(index, query)
            print("\nRelevant conversations:")
            for i, result in enumerate(results, 1):
                print(f"\n--- Result {i} ---")
                print(result)
        
        elif choice == "2":
            question = input("\nEnter your question: ")
            answer = ask_question(index, question)
            print("\nAnswer:", answer)
        
        elif choice == "3":
            topic = input("\nWhat topic would you like a how-to guide for? ")
            print("\nGenerating how-to document...")
            howto = generate_howto(index, topic)
            print("\nHow-To Guide:")
            print(howto)
        
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
