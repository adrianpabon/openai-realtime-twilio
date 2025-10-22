import sys
import logging
import warnings
from llama_index.core.settings import Settings
warnings.filterwarnings("ignore")

# Uncomment to see debug logs
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from llama_index.vector_stores.redis import RedisVectorStore
import redis
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import StorageContext
from redisvl.schema import IndexSchema
from dotenv import load_dotenv
load_dotenv()


def main():

    r = redis.Redis(host='localhost', port=6379, db=0)
    embedded_model = OpenAIEmbedding(model="text-embedding-3-small", dimensions=1536)
    Settings.embed_model = embedded_model


    documents = SimpleDirectoryReader('pasteur_info').load_data()




    custom_schema = IndexSchema.from_dict(
        {
            # customize basic index specs
            "index": {
                "name": "lab",
                "prefix": "lab:doc",
                "key_separator": ":",
            },
            # customize fields that are indexed
            "fields": [
                # required fields for llamaindex
                {"type": "tag", "name": "id"},
                {"type": "tag", "name": "doc_id"},
                {"type": "text", "name": "text"},
                # custom metadata fields
                {"type": "tag", "name": "file_name"},
                # custom vector field definition for cohere embeddings
                {
                    "type": "vector",
                    "name": "vector",
                    "attrs": {
                        "dims": 1536,
                        "algorithm": "hnsw",
                        "distance_metric": "cosine",
                    },
                },
            ],
        }
    )


    vector_store = RedisVectorStore(
        redis_client=r, 
        overwrite=True,
        schema=custom_schema
    )


    # Crear el contexto de almacenamiento
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # Construir el índice
    index = VectorStoreIndex.from_documents(
        documents, storage_context=storage_context
    )

    custom_schema.to_yaml("lab_schema.yaml")

    print("Index creado exitosamente")


if __name__ == "__main__":
    main()