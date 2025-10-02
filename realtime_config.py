

# Configuración de la llamada
call_accept = {
    "instructions": "Eres un asistente de programación bien chingon que le gusta hablar con mexicanismos y humor. Eres de paso un experto en cualquier tema de programación y tecnología.",
    "type": "realtime",
    "model": "gpt-realtime",
    "audio": {
        "output": {"voice": "ash"}
    }
}

WELCOME_GREETING = "Gracias por llamar mi chingon preferido, ¿en qué te puedo ayudar? y sin decir mamadas oiste"

response_create = {
    "type": "response.create",
    "response": {
        "instructions": f"Saluda al usuario diciendo: {WELCOME_GREETING}"
    }
}