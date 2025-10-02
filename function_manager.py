

class FunctionManager:
    def __init__(self):
        self.functions = {}

    def execute_function(self, function_name, *args, **kwargs):
        if function_name in self.functions:
            return self.functions[function_name](*args, **kwargs)
        else:
            raise ValueError(f"Function '{function_name}' not found.")