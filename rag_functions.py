from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.redis import RedisVectorStore
import redis
import numpy as np
from redis.exceptions import ResponseError
from openai import OpenAI
import numpy as np
from redis.commands.search.query import Query
from redis.exceptions import ResponseError
from dotenv import load_dotenv
import os
from scripts.load_exams import VSS_DIMENSION
from llama_index.vector_stores.redis import RedisVectorStore
import redis
from redisvl.schema import IndexSchema
from llama_index.core.settings import Settings
from llama_index.embeddings.openai import OpenAIEmbedding
load_dotenv()

embedded_model = OpenAIEmbedding(model="text-embedding-3-small", dimensions=1536)
Settings.embed_model = embedded_model

r = redis.Redis(host='localhost', port=6379, db=0)

def search_general_exam_info(query, num_results):
    try:
        api_key = os.environ["OPENAI_API_KEY"]
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            input=query,
            model="text-embedding-3-large",
            dimensions=VSS_DIMENSION
        )
        embedding = response.data[0].embedding

        def make_search_with_knn(input_embedding):
            q = Query(f"*=>[KNN {num_results} @embedding $vec AS score]").sort_by("score").return_fields("title", "content", "category", "score").dialect(2)
            res = r.ft('lab_exam_idx').search(q, query_params={"vec": input_embedding})
            return res
        
        input_embedding = np.array(embedding, dtype=np.float32).tobytes()
        res= make_search_with_knn(input_embedding)

        result_string = ""

        if res and res.total > 0:
            result_string += f"Se encontraron {res.total} para responder la pregunta:\n"
            
            for i, doc in enumerate(res.docs):
                result_string += f"\n--- Resultado {i+1} ---"
                result_string += f"\nTítulo: {doc.title}"
                result_string += f"\nContenido: {doc.content}"
                result_string += f"\nCategoría: {doc.category}"
                result_string += f"\nScore: {doc.score}\n"
        else:
            result_string += "No se encontraron resultados"

        return result_string

    except ResponseError as e:
        return f"Error en la búsqueda: {str(e)}"
    

def search_info_about_the_lab(query, num_results):
    try:
        vector_store = RedisVectorStore(
            schema=IndexSchema.from_yaml("scripts/lab_schema.yaml"),
            redis_client=r,
        )
        search_index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

        retriever = search_index.as_retriever(
            similarity_top_k=num_results
        )

        result_nodes = retriever.retrieve(query)
        results_string = "Resultados para responder pregunta: \n\n"

        for node in result_nodes:
            results_string += f"Texto: {node.text}\nNombre de archivo: {node.metadata.get('file_name')}\nScore: {node.score}\n{'-' * 20}\n"
            results_string += "-"*20

        return results_string
    
    except Exception as e:
        return F"Error en la búsqueda: {str(e)}"
                
