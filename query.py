from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex

from src.config.llm_config import LLMConfig

load_dotenv()

llm_config = LLMConfig()


def main():
    index = VectorStoreIndex.from_vector_store(
        llm_config.get_vector_store()
    )
    print(
        index.as_query_engine(similarity_top_k=10).query(
            "What documents do you see?"
        )
    )


if __name__ == "__main__":
    main()
