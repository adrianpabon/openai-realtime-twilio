"""
Script temporal para limpiar el caché de conversaciones en Redis
"""
from conversation_cache import conversation_cache

if conversation_cache.redis_client:
    # Obtener todas las claves de conversaciones
    keys = conversation_cache.redis_client.keys("wpp_conversation:*")

    if keys:
        print(f"🗑️ Eliminando {len(keys)} conversaciones del caché...")
        for key in keys:
            conversation_cache.redis_client.delete(key)
            print(f"   ✓ Eliminada: {key}")
        print(f"✅ Caché limpiado exitosamente")
    else:
        print("📭 No hay conversaciones en caché")
else:
    print("⚠️ No hay conexión a Redis")
