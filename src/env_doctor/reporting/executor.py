"""
Script and notebook executor for error reporting.

Executes Python scripts and Jupyter notebooks to capture errors and environment info.
"""

import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from env_doctor.scanner.environment import get_full_environment_info


def execute_script(path: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Execute a Python script and capture output.
    
    Args:
        path: Path to Python script
        timeout: Execution timeout in seconds
        
    Returns:
        Dictionary with execution results:
        - success: bool
        - exit_code: int
        - stdout: str
        - stderr: str
        - error: Optional[str]
        - traceback: Optional[str]
        - duration: float (seconds)
        
    Example:
        >>> result = execute_script("test.py", timeout=60)
        >>> if not result["success"]:
        ...     print(result["error"])
    """
    script_path = Path(path)
    
    if not script_path.exists():
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Script not found: {path}",
            "traceback": None,
            "duration": 0.0
        }
    
    import time
    start_time = time.time()
    
    try:
        # Execute script in subprocess
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=script_path.parent
        )
        
        duration = time.time() - start_time
        
        # Parse stderr for traceback
        error_msg = None
        traceback_str = None
        
        if result.returncode != 0:
            stderr_lines = result.stderr.strip().split('\n')
            
            # Extract error message (usually last line)
            if stderr_lines:
                error_msg = stderr_lines[-1]
            
            # Full stderr is the traceback
            traceback_str = result.stderr
        
        return {
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "error": error_msg,
            "traceback": traceback_str,
            "duration": duration
        }
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Script execution timed out after {timeout} seconds",
            "traceback": None,
            "duration": duration
        }
        
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "duration": duration
        }


def execute_notebook(path: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Execute a Jupyter notebook and capture output.
    
    Args:
        path: Path to Jupyter notebook (.ipynb)
        timeout: Execution timeout in seconds
        
    Returns:
        Dictionary with execution results (same format as execute_script)
        
    Note:
        Requires nbconvert and jupyter to be installed.
        Converts notebook to Python script and executes it.
    """
    notebook_path = Path(path)
    
    if not notebook_path.exists():
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Notebook not found: {path}",
            "traceback": None,
            "duration": 0.0
        }
    
    if not notebook_path.suffix == ".ipynb":
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Not a Jupyter notebook: {path}",
            "traceback": None,
            "duration": 0.0
        }
    
    import time
    start_time = time.time()
    
    try:
        # Check if nbconvert is available
        try:
            import nbconvert
        except ImportError:
            return {
                "success": False,
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "error": "nbconvert not installed. Install with: pip install nbconvert",
                "traceback": None,
                "duration": 0.0
            }
        
        # Convert notebook to Python script
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.py',
            delete=False,
            encoding='utf-8'
        ) as tmp_script:
            tmp_script_path = tmp_script.name
        
        try:
            # Use nbconvert to convert notebook to script
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "jupyter",
                    "nbconvert",
                    "--to",
                    "script",
                    "--output",
                    tmp_script_path,
                    str(notebook_path)
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "error": "Failed to convert notebook to script",
                    "traceback": result.stderr,
                    "duration": time.time() - start_time
                }
            
            # Execute the converted script
            exec_result = execute_script(tmp_script_path, timeout=timeout)
            exec_result["duration"] = time.time() - start_time
            
            return exec_result
            
        finally:
            # Clean up temporary script
            try:
                Path(tmp_script_path).unlink()
            except Exception:
                pass
                
    except Exception as e:
        duration = time.time() - start_time
        return {
            "success": False,
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "duration": duration
        }


def parse_error_traceback(traceback_str: str) -> Dict[str, Any]:
    """
    Parse error traceback to extract structured information.
    
    Args:
        traceback_str: Full traceback string
        
    Returns:
        Dictionary with parsed error information:
        - error_type: str
        - error_message: str
        - file: Optional[str]
        - line: Optional[int]
        - function: Optional[str]
        
    Example:
        >>> tb = "Traceback...\\nImportError: No module named 'torch'"
        >>> info = parse_error_traceback(tb)
        >>> print(info["error_type"])
        'ImportError'
    """
    if not traceback_str:
        return {
            "error_type": "Unknown",
            "error_message": "",
            "file": None,
            "line": None,
            "function": None
        }
    
    lines = traceback_str.strip().split('\n')
    
    # Last line usually contains error type and message
    error_type = "Unknown"
    error_message = ""
    
    if lines:
        last_line = lines[-1]
        if ':' in last_line:
            parts = last_line.split(':', 1)
            error_type = parts[0].strip()
            error_message = parts[1].strip() if len(parts) > 1 else ""
        else:
            error_message = last_line
    
    # Try to find file, line, and function from traceback
    file_path = None
    line_num = None
    function_name = None
    
    for line in lines:
        # Look for lines like: File "/path/to/file.py", line 42, in function_name
        if line.strip().startswith('File "'):
            try:
                # Extract file path
                file_start = line.index('File "') + 6
                file_end = line.index('"', file_start)
                file_path = line[file_start:file_end]
                
                # Extract line number
                if ', line ' in line:
                    line_start = line.index(', line ') + 7
                    line_part = line[line_start:].split(',')[0].strip()
                    line_num = int(line_part)
                
                # Extract function name
                if ', in ' in line:
                    func_start = line.index(', in ') + 5
                    function_name = line[func_start:].strip()
                    
            except (ValueError, IndexError):
                pass
    
    return {
        "error_type": error_type,
        "error_message": error_message,
        "file": file_path,
        "line": line_num,
        "function": function_name
    }


def create_error_report(
    script_path: str,
    execution_result: Dict[str, Any],
    include_environment: bool = True
) -> Dict[str, Any]:
    """
    Create comprehensive error report.
    
    Args:
        script_path: Path to executed script
        execution_result: Result from execute_script or execute_notebook
        include_environment: Whether to include environment info
        
    Returns:
        Complete error report dictionary
    """
    report: Dict[str, Any] = {
        "script_path": script_path,
        "execution": execution_result
    }
    
    # Parse traceback if available
    if execution_result.get("traceback"):
        report["parsed_error"] = parse_error_traceback(execution_result["traceback"])
    
    # Include environment info if requested
    if include_environment:
        report["environment"] = get_full_environment_info()
    
    return report


# Made with Bob