"""
Módulo para gestionar el caché de conversaciones de WhatsApp en Redis
"""
import redis
import json
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

class ConversationCache:
    """Gestiona el caché de conversaciones en Redis con TTL de 1 hora"""

    def __init__(self, redis_url: Optional[str] = None, ttl_seconds: int = 3600):
        """
        Inicializa la conexión a Redis

        Args:
            redis_url: URL de conexión a Redis (por defecto usa variable de entorno)
            ttl_seconds: Tiempo de vida del caché en segundos (por defecto 1 hora)
        """
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.ttl_seconds = ttl_seconds

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            print(f"✅ Conectado a Redis exitosamente")
        except Exception as e:
            print(f"⚠️ Error conectando a Redis: {e}")
            print(f"⚠️ Se continuará sin caché de conversaciones")
            self.redis_client = None

    def _get_key(self, remote_jid: str) -> str:
        """Genera la clave Redis para un chat específico"""
        return f"wpp_conversation:{remote_jid}"

    def get_conversation(self, remote_jid: str) -> Optional[List[Dict]]:
        """
        Obtiene la conversación almacenada en Redis para un chat

        Args:
            remote_jid: ID del chat de WhatsApp

        Returns:
            Lista de mensajes de la conversación o None si no existe
        """
        if not self.redis_client:
            return None

        try:
            key = self._get_key(remote_jid)
            conversation_json = self.redis_client.get(key)

            if conversation_json:
                conversation = json.loads(conversation_json)
                print(f"📥 Conversación recuperada de Redis: {len(conversation)} mensajes")
                return conversation
            else:
                print(f"📭 No hay conversación en caché para {remote_jid}")
                return None

        except Exception as e:
            print(f"⚠️ Error obteniendo conversación de Redis: {e}")
            return None

    def save_conversation(self, remote_jid: str, conversation: List[Dict]) -> bool:
        """
        Guarda la conversación en Redis con TTL

        Args:
            remote_jid: ID del chat de WhatsApp
            conversation: Lista de mensajes de la conversación

        Returns:
            True si se guardó exitosamente, False en caso contrario
        """
        if not self.redis_client:
            return False

        try:
            key = self._get_key(remote_jid)
            conversation_json = json.dumps(conversation, ensure_ascii=False)

            # Guardar con TTL de 1 hora
            self.redis_client.setex(
                key,
                self.ttl_seconds,
                conversation_json
            )

            print(f"💾 Conversación guardada en Redis: {len(conversation)} mensajes (TTL: {self.ttl_seconds}s)")
            return True

        except Exception as e:
            print(f"⚠️ Error guardando conversación en Redis: {e}")
            return False

    def append_message(self, remote_jid: str, role: str, content: str,
                      function_call: Optional[Dict] = None,
                      function_result: Optional[str] = None) -> bool:
        """
        Agrega un mensaje a la conversación existente

        Args:
            remote_jid: ID del chat de WhatsApp
            role: Rol del mensaje ("user", "assistant", "tool")
            content: Contenido del mensaje
            function_call: Información de la llamada a función (opcional)
            function_result: Resultado de la función (opcional)

        Returns:
            True si se agregó exitosamente, False en caso contrario
        """
        if not self.redis_client:
            return False

        try:
            # Obtener conversación actual
            conversation = self.get_conversation(remote_jid) or []

            # Crear nuevo mensaje
            new_message = {"role": role, "content": content}

            # Agregar información de función si existe
            if function_call:
                new_message["function_call"] = function_call
            if function_result:
                new_message["function_result"] = function_result

            # Agregar mensaje
            conversation.append(new_message)

            # Guardar conversación actualizada
            return self.save_conversation(remote_jid, conversation)

        except Exception as e:
            print(f"⚠️ Error agregando mensaje a conversación: {e}")
            return False

    def delete_conversation(self, remote_jid: str) -> bool:
        """
        Elimina una conversación del caché

        Args:
            remote_jid: ID del chat de WhatsApp

        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        if not self.redis_client:
            return False

        try:
            key = self._get_key(remote_jid)
            self.redis_client.delete(key)
            print(f"🗑️ Conversación eliminada de Redis")
            return True

        except Exception as e:
            print(f"⚠️ Error eliminando conversación de Redis: {e}")
            return False

    def get_ttl(self, remote_jid: str) -> Optional[int]:
        """
        Obtiene el tiempo de vida restante de una conversación

        Args:
            remote_jid: ID del chat de WhatsApp

        Returns:
            Segundos restantes o None si no existe o error
        """
        if not self.redis_client:
            return None

        try:
            key = self._get_key(remote_jid)
            ttl = self.redis_client.ttl(key)

            if ttl > 0:
                return ttl
            else:
                return None

        except Exception as e:
            print(f"⚠️ Error obteniendo TTL: {e}")
            return None


# Instancia global del caché
conversation_cache = ConversationCache()
