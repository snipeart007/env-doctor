/**
 * env-doctor Secure Proxy Worker (Cloudflare Workers)
 * 
 * Proxies incompatibility reports to Watsonx Orchestrate without
 * exposing IBM Cloud API keys to end-users.
 */

export interface Env {
	// Secret environment variables (Set via wrangler secret put)
	IBM_API_KEY: string;

	// Public environment variables (Set in wrangler.jsonc)
	INSTANCE_URL: string;
	AGENT_ID: string;
}

export default {
	async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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
			// 2. Parse User Payload
			const payload = await request.json() as { markdown: string };
			const reportContent = payload.markdown;

			if (!reportContent) {
				return new Response(JSON.stringify({ error: "Missing 'markdown' content" }), { 
					status: 400,
					headers: { "Content-Type": "application/json" }
				});
			}

			// 3. Authenticate with IBM IAM
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

			// 4. Forward to Watsonx Orchestrate
			// We use a blank thread_id to ensure every submission starts a fresh analysis thread
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
					"thread_id": "",
				}),
			});

			// 5. Stream response back to client
			const responseHeaders = new Headers(orchestrateResponse.headers);
			responseHeaders.set("Access-Control-Allow-Origin", "*");

			return new Response(orchestrateResponse.body, {
				status: orchestrateResponse.status,
				headers: responseHeaders,
			});

		} catch (err: any) {
			return new Response(JSON.stringify({ error: err.message }), { 
				status: 500,
				headers: { "Content-Type": "application/json" }
			});
		}
	},
};
