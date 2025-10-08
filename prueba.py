from rag_functions import search_general_exam_info, search_info_about_the_lab


query = "¿Qué es un hemograma y para qué sirve?"
result = search_general_exam_info(query, num_results=3)
print(result)

query2 = "¿Dónde se encuentra el laboratorio clínico?"
result2 = search_info_about_the_lab(query2, num_results=3)
print(result2)