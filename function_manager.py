from functions import available_functions
import json
import asyncio
from typing import Any, Dict

class FunctionManager:
    def __init__(self):
        self.functions = available_functions

    async def execute_function(self, function_name: str, arguments: str) -> Dict[str, Any]:
        """
        Ejecuta una función por nombre con argumentos en formato JSON string

        Args:
            function_name: Nombre de la función a ejecutar
            arguments: Argumentos en formato JSON string

        Returns:
            Resultado de la función ejecutada
        """
        if function_name not in self.functions:
            raise ValueError(f"Function '{function_name}' not found.")

        # Parse argumentos JSON
        try:
            kwargs = json.loads(arguments)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON arguments: {e}")

        # Ejecutar función (sync o async)
        func = self.functions[function_name]

        # Ejecutar en thread pool si es función síncrona
        if asyncio.iscoroutinefunction(func):
            result = await func(**kwargs)
        else:
            result = await asyncio.to_thread(func, **kwargs)

        return result