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
from typing import Any, Dict, Optional, List

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
        - source_code: str
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
            "duration": 0.0,
            "source_code": ""
        }
    
    try:
        source_code = script_path.read_text(encoding='utf-8')
    except Exception as e:
        source_code = f"Error reading source: {e}"
    
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
            "duration": duration,
            "source_code": source_code
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
            "duration": duration,
            "source_code": source_code
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
            "duration": duration,
            "source_code": source_code
        }


def execute_notebook(path: str, timeout: int = 300) -> Dict[str, Any]:
    """
    Execute a Jupyter notebook and capture output cell-by-cell.
    
    Args:
        path: Path to Jupyter notebook (.ipynb)
        timeout: Execution timeout in seconds
        
    Returns:
        Dictionary with execution results:
        - success: bool
        - cells: List[Dict[str, Any]]
        - error: Optional[str]
        - duration: float
    """
    notebook_path = Path(path)
    
    if not notebook_path.exists():
        return {
            "success": False,
            "cells": [],
            "error": f"Notebook not found: {path}",
            "duration": 0.0
        }
    
    import time
    start_time = time.time()
    
    try:
        import nbformat
        from nbclient import NotebookClient
        
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = nbformat.read(f, as_version=4)
        
        client = NotebookClient(nb, timeout=timeout, kernel_name='python3')
        
        # We execute manually to capture results even if it fails
        client.create_kernel_manager()
        client.start_new_kernel()
        client.start_new_kernel_client()
        
        executed_cells = []
        success = True
        error_msg = None
        
        try:
            for idx, cell in enumerate(nb.cells):
                if cell.cell_type == 'code':
                    try:
                        client.execute_cell(cell, idx)
                        
                        outputs = []
                        for output in cell.outputs:
                            if output.output_type == 'stream':
                                outputs.append(output.text)
                            elif output.output_type == 'error':
                                outputs.append(f"{output.ename}: {output.evalue}\n" + "".join(output.traceback))
                                success = False
                                error_msg = f"{output.ename}: {output.evalue}"
                            elif output.output_type in ['execute_result', 'display_data']:
                                if 'text/plain' in output.data:
                                    outputs.append(output.data['text/plain'])
                        
                        executed_cells.append({
                            "index": idx + 1,
                            "source": cell.source,
                            "output": "".join(outputs)
                        })
                        
                        if not success:
                            break
                            
                    except Exception as e:
                        success = False
                        error_msg = str(e)
                        executed_cells.append({
                            "index": idx + 1,
                            "source": cell.source,
                            "output": f"Execution Error: {e}"
                        })
                        break
                else:
                    # Skip markdown cells for report or include them?
                    # User asked for ## Cell 1 \n code here... so we focus on code cells
                    pass
        finally:
            client.stop_kernel()
            
        return {
            "success": success,
            "cells": executed_cells,
            "error": error_msg,
            "duration": time.time() - start_time
        }
                
    except Exception as e:
        return {
            "success": False,
            "cells": [],
            "error": str(e),
            "duration": time.time() - start_time
        }


def generate_markdown_report(path: str, result: Dict[str, Any]) -> str:
    """
    Generate Markdown report from execution results.
    """
    path_obj = Path(path)
    md = []
    
    if path_obj.suffix == '.ipynb':
        # Jupyter Notebook format
        for cell in result.get('cells', []):
            md.append(f"## Cell {cell['index']}")
            md.append(cell['source'])
            md.append("## Output")
            md.append(cell['output'] or "(No output)")
            md.append("")
    else:
        # Python script format
        md.append("## Python Code")
        md.append(result.get('source_code', ''))
        md.append("## Output")
        
        stdout = result.get('stdout', '')
        stderr = result.get('stderr', '')
        
        output = []
        if stdout:
            output.append(stdout)
        if stderr:
            output.append(stderr)
            
        md.append("\n".join(output) or "(No output)")
        md.append("")
    
    # Append Environment Info
    md.append("## Environment Info")
    env_info = get_full_environment_info()
    md.append("```json")
    md.append(json.dumps(env_info, indent=2))
    md.append("```")
    
    return "\n".join(md)


def parse_error_traceback(traceback_str: str) -> Dict[str, Any]:
    """
    Parse error traceback to extract structured information.
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
    """
    report: Dict[str, Any] = {
        "script_path": script_path,
        "execution": execution_result
    }
    
    # Generate markdown report
    report["markdown"] = generate_markdown_report(script_path, execution_result)
    
    # Parse traceback if available
    if execution_result.get("traceback"):
        report["parsed_error"] = parse_error_traceback(execution_result["traceback"])
    elif execution_result.get("error") and not execution_result.get("traceback"):
        # For notebook errors captured without full traceback
        report["parsed_error"] = {
            "error_type": execution_result["error"].split(":")[0] if ":" in execution_result["error"] else "Unknown",
            "error_message": execution_result["error"],
            "file": script_path,
            "line": None,
            "function": None
        }
    
    # Include environment info if requested
    if include_environment:
        report["environment"] = get_full_environment_info()
    
    return report
