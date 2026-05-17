/**
 * env-doctor Secure Proxy & Repository Manager (Cloudflare Workers)
 * 
 * Handles:
 * 1. /compatibility: Proxy to Watsonx Orchestrate for AI analysis.
 * 2. /stable-stack: Direct update of GitHub stable_stacks.yaml.
 */

import yaml from 'js-yaml';

export interface Env {
	// Secret environment variables (Set via wrangler secret put)
	IBM_API_KEY: string;
	GITHUB_TOKEN: string;

	// Public environment variables (Set in wrangler.jsonc)
	INSTANCE_URL: string;
	AGENT_ID: string;
	GITHUB_REPOSITORY: string; // e.g., "snipeart007/env-doctor-db"
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
		const url = new URL(request.url);

		// 1. Pre-flight & Method Check
		if (request.method === "OPTIONS") {
			return new Response(null, {
				headers: {
					"Access-Control-Allow-Origin": "*",
					"Access-Control-Allow-Methods": "POST, OPTIONS",
					"Access-Control-Allow-Headers": "Content-Type",
				},
			});
		}

		if (request.method !== "POST") {
			return new Response("Method Not Allowed", { status: 405 });
		}

		try {
			// Route based on path
			if (url.pathname === "/compatibility") {
				return await handleCompatibility(request, env);
			} else if (url.pathname === "/stable-stack") {
				return await handleStableStack(request, env);
			} else {
				return new Response("Not Found", { status: 404 });
			}

		} catch (err: any) {
			return new Response(JSON.stringify({ error: err.message }), { 
				status: 500,
				headers: { 
					"Content-Type": "application/json",
					"Access-Control-Allow-Origin": "*"
				}
			});
		}
	},
};

/**
 * Handle compatibility report submissions (Watsonx Proxy)
 */
async function handleCompatibility(request: Request, env: Env): Promise<Response> {
	const payload = await request.json() as { markdown: string };
	const reportContent = payload.markdown;

	if (!reportContent) {
		return new Response(JSON.stringify({ error: "Missing 'markdown' content" }), { 
			status: 400,
			headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
		});
	}

	// Authenticate with IBM IAM
	const iamResponse = await fetch("https://iam.cloud.ibm.com/identity/token", {
		method: "POST",
		headers: {
			"Content-Type": "application/x-www-form-urlencoded",
			"Accept": "application/json",
		},
		body: new URLSearchParams({
			"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
			"apikey": env.IBM_API_KEY,
		}),
	});

	if (!iamResponse.ok) {
		const errorMsg = await iamResponse.text();
		return new Response(`IAM Auth Failed: ${errorMsg}`, { status: 401 });
	}

	const { access_token } = await iamResponse.json() as { access_token: string };

	// Forward to Watsonx Orchestrate
	const orchestrateUrl = `${env.INSTANCE_URL}/v1/orchestrate/runs?stream=true&stream_timeout=120000&multiple_content=true`;
	
	const orchestrateResponse = await fetch(orchestrateUrl, {
		method: "POST",
		headers: {
			"Authorization": `Bearer ${access_token}`,
			"IAM-API_KEY": env.IBM_API_KEY,
			"Accept": "application/json",
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			"message": {
				"role": "user",
				"content": reportContent,
			},
			"agent_id": env.AGENT_ID,
			}),
			});
	const responseHeaders = new Headers(orchestrateResponse.headers);
	responseHeaders.set("Access-Control-Allow-Origin", "*");

	return new Response(orchestrateResponse.body, {
		status: orchestrateResponse.status,
		headers: responseHeaders,
	});
}

/**
 * Handle stable stack registration (GitHub Update)
 */
async function handleStableStack(request: Request, env: Env): Promise<Response> {
	const stack = await request.json() as any;

	// Validation
	if (!stack.name || !stack.python_version || !stack.packages) {
		return new Response(JSON.stringify({ error: "Invalid stack object. Required: name, python_version, packages" }), {
			status: 400,
			headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
		});
	}

	const githubUrl = `https://api.github.com/repos/${env.GITHUB_REPOSITORY}/contents/stable_stacks.yaml`;
	const authHeader = `token ${env.GITHUB_TOKEN}`;
	const userAgent = "env-doctor-worker";

	// 1. Fetch current file from GitHub
	const getResponse = await fetch(githubUrl, {
		headers: {
			"Authorization": authHeader,
			"User-Agent": userAgent,
			"Accept": "application/vnd.github.v3+json"
		}
	});

	let currentContent = "";
	let sha = "";

	if (getResponse.status === 200) {
		const data = await getResponse.json() as any;
		currentContent = atob(data.content);
		sha = data.sha;
	} else if (getResponse.status !== 404) {
		return new Response(`GitHub Fetch Failed: ${await getResponse.text()}`, { status: getResponse.status });
	}

	// 2. Parse and Update
	let yamlData: any = { stacks: [] };
	if (currentContent) {
		try {
			yamlData = yaml.load(currentContent);
			if (!yamlData.stacks) yamlData.stacks = [];
		} catch (e) {
			return new Response("Failed to parse existing YAML from GitHub", { status: 500 });
		}
	}

	// Check if stack already exists (by name) and update or append
	const existingIndex = yamlData.stacks.findIndex((s: any) => s.name === stack.name);
	if (existingIndex >= 0) {
		yamlData.stacks[existingIndex] = stack;
	} else {
		yamlData.stacks.push(stack);
	}

	const newYamlContent = yaml.dump(yamlData, { indent: 2, lineWidth: -1 });

	// 3. Push back to GitHub
	const putResponse = await fetch(githubUrl, {
		method: "PUT",
		headers: {
			"Authorization": authHeader,
			"User-Agent": userAgent,
			"Content-Type": "application/json",
		},
		body: JSON.stringify({
			message: `Add stable stack: ${stack.name} via env-doctor API`,
			content: btoa(newYamlContent),
			sha: sha || undefined
		})
	});

	if (!putResponse.ok) {
		return new Response(`GitHub Update Failed: ${await putResponse.text()}`, { status: putResponse.status });
	}

	return new Response(JSON.stringify({ success: true, message: `Stack '${stack.name}' updated on GitHub` }), {
		status: 200,
		headers: { 
			"Content-Type": "application/json",
			"Access-Control-Allow-Origin": "*"
		}
	});
}
