"""
MCP Server for env-doctor.

Provides tools for Watsonx Orchestrate to update the compatibility database on GitHub.
"""

import os
import json
import time
import base64
import asyncio
from typing import Any, Dict, Optional

import httpx
import yaml
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("env-doctor-server")

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY")
GITHUB_TOKEN = os.getenv("GITHUB_API_KEY") or os.getenv("GITHUB_TOKEN")


@mcp.tool()
async def update_compatibility_database(
    package: str,
    package_version_range: str,
    dependency: str,
    dependency_version_range: str,
    rule_type: str,
    severity: int,
    description: str,
    fix_suggestion: str,
    cuda_version: Optional[str] = None,
    env_system: Optional[str] = None
) -> str:
    """
    Add a new compatibility rule to the GitHub repository.
    Appends to the existing YAML file if it exists, otherwise creates a new one.
    
    Args:
        package: The name of the main package (e.g., 'torch').
        package_version_range: Version range of the main package (e.g., '>=2.4.0').
        dependency: The name of the conflicting dependency (e.g., 'cuda').
        dependency_version_range: Version range of the dependency (e.g., '<12.1').
        rule_type: Type of rule ('incompatible', 'runtime-risk', 'partial', 'compatible').
        severity: Severity score from 0 to 100.
        description: Detailed description of the incompatibility.
        fix_suggestion: Suggested resolution or fix.
        cuda_version: Optional CUDA version or range (e.g., '12.1', '<12.4').
        env_system: Optional environment/platform info (e.g., 'linux', 'win32').
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_API_KEY or GITHUB_TOKEN environment variable not set."

    try:
        # 1. Prepare the new rule data
        new_rule = {
            "package": package,
            "version_range": package_version_range,
            "dependency": dependency,
            "dependency_range": dependency_version_range,
            "cuda_version": cuda_version,
            "env_system": env_system,
            "type": rule_type,
            "confidence": "community-tested",
            "severity": severity,
            "description": description,
            "workaround": fix_suggestion
        }
        
        # 2. Determine file path (grouped by package)
        safe_package_name = package.lower().replace(" ", "_").replace("-", "_")
        file_path = f"compatibility/{safe_package_name}.yaml"
        
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        async with httpx.AsyncClient() as client:
            # 3. Check if file exists
            response = await client.get(url, headers=headers)
            
            existing_sha = None
            rules_list = []
            
            if response.status_code == 200:
                # File exists, fetch content and sha
                data = response.json()
                existing_sha = data.get("sha")
                content = base64.b64decode(data.get("content", "")).decode("utf-8")
                
                try:
                    existing_data = yaml.safe_load(content) or {}
                    rules_list = existing_data.get("rules", [])
                except Exception:
                    # If YAML is malformed, start fresh or handle error
                    rules_list = []
            
            # 4. Append new rule
            rules_list.append(new_rule)
            
            # 5. Prepare updated YAML content
            yaml_payload = {"rules": rules_list}
            yaml_content = yaml.dump(yaml_payload, sort_keys=False)
            
            # 6. Push update to GitHub
            payload = {
                "message": f"Add compatibility rule for {package} vs {dependency}",
                "content": base64.b64encode(yaml_content.encode()).decode(),
                "branch": "main"
            }
            if existing_sha:
                payload["sha"] = existing_sha
                
            put_response = await client.put(url, headers=headers, json=payload)
            
            if put_response.status_code in [200, 201]:
                action = "Updated" if existing_sha else "Created"
                return f"Successfully {action} {file_path}. PR URL: {put_response.json().get('content', {}).get('html_url')}"
            else:
                return f"Failed to update GitHub: {put_response.status_code} - {put_response.text}"
                
    except Exception as e:
        return f"An error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run()
