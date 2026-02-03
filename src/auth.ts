import { SvelteKitAuth } from '@auth/sveltekit';
import Cognito from '@auth/core/providers/cognito';

// Auth.js configuration for AWS Cognito
export const { handle } = SvelteKitAuth(async (event) => {
	const env = event.platform?.env;

	// For local development without bindings
	if (!env?.COGNITO_CLIENT_ID) {
		console.warn('Cognito env vars not configured - using placeholder config');
		return {
			providers: [],
			secret: 'dev-secret-not-for-production',
			trustHost: true
		};
	}

	return {
		providers: [
			Cognito({
				clientId: env.COGNITO_CLIENT_ID,
				clientSecret: env.COGNITO_CLIENT_SECRET,
				issuer: `https://cognito-idp.${env.COGNITO_REGION}.amazonaws.com/${env.COGNITO_USER_POOL_ID}`
			})
		],
		secret: env.SESSION_SECRET,
		trustHost: true,
		callbacks: {
			// Include user info in the session
			session: ({ session, token }) => {
				if (token?.sub) {
					session.user.id = token.sub;
				}
				return session;
			}
		}
	};
});
