import type { Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import { sequence } from '@sveltejs/kit/hooks';
import { handle as authHandle } from './auth';

// Route protection for admin pages
const protectAdminRoutes: Handle = async ({ event, resolve }) => {
	const { url } = event;

	// Determine if this is a protected route
	const isAdminRoute = url.pathname.startsWith('/admin');
	const isAdminApi = url.pathname.startsWith('/api/admin');
	const isAuthRoute = url.pathname.startsWith('/auth');
	const isLoginPage = url.pathname === '/admin/login';

	// Skip protection for non-admin routes, auth routes, and login page
	if ((!isAdminRoute && !isAdminApi) || isAuthRoute || isLoginPage) {
		return resolve(event);
	}

	// Check session using Auth.js
	const session = await event.locals.auth();

	if (!session?.user) {
		if (isAdminApi) {
			return new Response(JSON.stringify({ error: 'Unauthorized' }), {
				status: 401,
				headers: { 'Content-Type': 'application/json' }
			});
		}
		// Redirect to login page
		throw redirect(303, '/admin/login');
	}

	return resolve(event);
};

// Combine Auth.js handle with route protection
export const handle = sequence(authHandle, protectAdminRoutes);
