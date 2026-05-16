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

GITHUB_REPO = os.getenv("GITHUB_REPOSITORY", "env-doctor/env-doctor-db")
GITHUB_TOKEN = os.getenv("GITHUB_API_KEY") or os.getenv("GITHUB_TOKEN")


@mcp.tool()
async def update_compatibility_database(compatibility_rules: Dict[str, Any]) -> str:
    """
    Add a new compatibility rule to the GitHub repository.
    
    Args:
        compatibility_rules: A dictionary following the compatibility YAML schema.
                             Must include 'incompatibility' details.
    """
    if not GITHUB_TOKEN:
        return "Error: GITHUB_API_KEY or GITHUB_TOKEN environment variable not set."

    try:
        # 1. Prepare YAML content
        yaml_content = yaml.dump(compatibility_rules, sort_keys=False)
        
        # 2. Determine file path
        # Extract error type for filename
        error_info = compatibility_rules.get("incompatibility", {})
        error_type = error_info.get("error_type", "unknown_error").lower().replace(" ", "_")
        timestamp = int(time.time())
        file_path = f"compatibility/{error_type}_{timestamp}.yaml"
        
        # 3. GitHub API Call
        url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{file_path}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        
        payload = {
            "message": f"Add compatibility rule for {error_type}",
            "content": base64.b64encode(yaml_content.encode()).decode(),
            "branch": "main" # Or a config base branch
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=payload)
            
            if response.status_code == 201:
                data = response.json()
                return f"Successfully created {file_path}. PR URL: {data.get('content', {}).get('html_url')}"
            else:
                return f"Failed to update GitHub: {response.status_code} - {response.text}"
                
    except Exception as e:
        return f"An error occurred: {str(e)}"


if __name__ == "__main__":
    mcp.run()
