# Secure Proxy & Stack Submission Guide (Cloudflare Workers)

This guide explains how to set up the Cloudflare Worker that acts as a secure proxy for Watsonx Orchestrate and manages automated stack registrations in the GitHub repository.

## 1. Overview
The `env-doctor` CLI uses a serverless worker to:
1.  **Proxy /compatibility**: Securely forward error reports to Watsonx without exposing IBM Cloud API keys.
2.  **Proxy /stable-stack**: Automatically update `stable_stacks.yaml` in your GitHub repository when a verified configuration is submitted.

## 2. Worker Deployment

### Prerequisites
- [Cloudflare Account](https://dash.cloudflare.com/)
- [Wrangler CLI](https://developers.cloudflare.com/workers/wrangler/install-and-setup/) installed and authenticated.

### Installation
1.  Navigate to the worker directory:
    ```bash
    cd workers/env-doctor-incompatibility-repeater
    ```
2.  Install dependencies:
    ```bash
    npm install
    ```

### Configuration
Update `wrangler.jsonc` with your specific values:
- `INSTANCE_URL`: Your Watsonx instance URL.
- `AGENT_ID`: Your Watsonx agent ID.
- `GITHUB_REPOSITORY`: Your intelligence repository (e.g., `snipeart007/env-doctor-db`).

### Security (Secrets)
Set your sensitive tokens as Cloudflare Secrets:
```bash
# GitHub Token (needs 'repo' or 'contents:write' scope)
npx wrangler secret put GITHUB_TOKEN

# IBM Cloud API Key
npx wrangler secret put IBM_API_KEY
```

### Deployment
```bash
npm run deploy
```

## 3. Connecting the CLI

### Worker URL Discovery
The CLI automatically discovers the worker URL if it is stored in your intelligence repository.
1.  Create a file named `worker.txt` in the root of your GitHub repo (e.g., `snipeart007/env-doctor-db`).
2.  Paste your Worker URL (e.g., `https://env-doctor-proxy.subdomain.workers.dev`) into the file.
3.  Commit and push to GitHub.

Now, whenever a user runs `env-doctor update-db`, the CLI will fetch and use this URL.

### Manual Override
You can override the discovered URL using an environment variable:
```bash
# Windows
$env:ENV_DOCTOR_PROXY_URL = "https://your-worker.workers.dev"

# Linux/macOS
export ENV_DOCTOR_PROXY_URL="https://your-worker.workers.dev"
```

## 4. Registering Stable Stacks
Authorized users can submit their current verified environment as a new stable stack:

```bash
env-doctor submit-stack my-optimized-stack --desc "High-performance Llama-3 setup"
```

This command will:
1.  Detect your system's CUDA, Python, and OS.
2.  Capture all installed packages and versions.
3.  Submit the object to the Worker.
4.  The Worker will automatically commit the new stack to your GitHub repository's `stable_stacks.yaml`.
