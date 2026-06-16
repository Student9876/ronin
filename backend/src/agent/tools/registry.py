import inspect
import time
from typing import Callable, Dict, Any, List, Tuple

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, description: str):
        def decorator(func: Callable):
            self._tools[name] = {
                "name": name,
                "description": description,
                "func": func
            }
            return func
        return decorator

    def get_tool(self, name: str) -> Dict[str, Any]:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered.")
        return self._tools[name]

    def list_tools(self) -> List[Dict[str, str]]:
        return [
            {"name": t["name"], "description": t["description"]}
            for t in self._tools.values()
        ]

tool_registry = ToolRegistry()

async def execute_tool(tool_name: str, *args, **kwargs) -> Tuple[Any, Dict[str, Any]]:
    """
    Executes a registered tool and returns a tuple: (result, telemetry_dict).
    """
    tool = tool_registry.get_tool(tool_name)
    func = tool["func"]
    
    input_display = kwargs.copy()
    if args:
        input_display["args"] = list(args)
        
    start_time = time.time()
    status = "completed"
    error_msg = None
    output_display = ""
    result = None
    
    try:
        if inspect.iscoroutinefunction(func):
            result = await func(*args, **kwargs)
        else:
            result = func(*args, **kwargs)
            
        if isinstance(result, str):
            output_display = result[:500] + ("..." if len(result) > 500 else "")
        elif isinstance(result, list):
            output_display = f"Successfully returned list with {len(result)} items."
        elif isinstance(result, dict):
            output_display = f"Successfully returned dictionary with {len(result.keys())} keys."
        else:
            output_display = str(result)[:500]
    except Exception as e:
        status = "failed"
        error_msg = str(e)
        output_display = f"Execution failed: {error_msg}"
        raise e
    finally:
        telemetry = {
            "name": tool_name,
            "status": status,
            "input": input_display,
            "output": output_display,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
        
    return result, telemetry
