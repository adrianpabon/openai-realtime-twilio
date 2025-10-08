import redis 
from openai import OpenAI
import json
import numpy as np
from redis.commands.search.field import TextField, TagField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition
from redis.exceptions import ResponseError
from tqdm import tqdm
VSS_INDEX_TYPE = "FLAT"
VSS_DATA_TYPE = "FLOAT32"
VSS_DISTANCE= "COSINE"
VSS_DIMENSION = 500
VSS_MINIMUM_SCORE= 0.3
VSS_K = 5

r = redis.Redis(host='localhost', port=6379, db=0)

def create_idx():
    try:
        r.ft('lab_exam_idx').dropindex(True)
    except ResponseError:
        pass
    index_def = IndexDefinition(prefix=["lab:exams:"])
    schema = (  TextField("title", as_name="title"),
                TextField("content", as_name="content"),
                TagField("category", as_name="category"),
                VectorField("embedding", VSS_INDEX_TYPE, {"TYPE": VSS_DATA_TYPE, "DIM": VSS_DIMENSION, "DISTANCE_METRIC": VSS_DISTANCE}))
    r.ft('lab_exam_idx').create_index(schema, definition=index_def)
    print("Index created successfully")


def add_exams_to_hash(exams_array):
    index = 0
    for exam in tqdm(exams_array):
        embedding_list = json.loads(exam["embedding"])
        embedding = np.array(embedding_list, dtype=np.float32).tobytes()
        r.hset(
            f"lab:exams:{index}",
            mapping={
                "title": exam["nombre_examen"],
                "content": exam["contenido_detalle"],
                "category": exam["categoria"],
                "embedding": embedding
            }
        )
        index += 1


if __name__ == "__main__":
    client = OpenAI()
    with open("examenes_laboratorio_completo.json", "r", encoding="utf-8") as f:
        exams = json.load(f)
    print(f"Loaded {len(exams)} exams")
    create_idx()
    add_exams_to_hash(exams)
    print("All exams added to Redis")