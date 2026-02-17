// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
import type { Session } from '@auth/core/types';

declare global {
	namespace App {
		// interface Error {}
		interface Locals {
			auth(): Promise<Session | null>;
		}
		// interface PageData {}
		interface Platform {
			env: {
				R2_DATA: import('@cloudflare/workers-types').R2Bucket;
				DB: import('@cloudflare/workers-types').D1Database;
				// Cognito authentication configuration (used by Auth.js)
				COGNITO_USER_POOL_ID: string;
				COGNITO_CLIENT_ID: string;
				COGNITO_CLIENT_SECRET: string;
				COGNITO_REGION: string;
				SESSION_SECRET: string;
				AUTH_SECRET: string;
				// AWS Lambda invocation (manual triggers from admin UI)
				AWS_ACCESS_KEY_ID: string;
				AWS_SECRET_ACCESS_KEY: string;
				LAMBDA_INITIATOR_URL: string;
				AWS_LAMBDA_REGION: string;
				STEP_FUNCTION_ARN: string;
			};
			context: {
				waitUntil(promise: Promise<any>): void;
			};
			caches: CacheStorage & { default: Cache };
		}
	}
}

export {};

