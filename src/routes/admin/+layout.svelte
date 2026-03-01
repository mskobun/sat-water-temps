<script lang="ts">
	import { page } from '$app/stores';
	import { signOut } from '@auth/sveltekit/client';
	import { Button } from '$lib/components/ui/button';
	import type { LayoutData } from './$types';

	export let data: LayoutData;

	function handleSignOut() {
		signOut({ callbackUrl: '/admin/login' });
	}
</script>

<div class="min-h-screen bg-background">
	{#if data.session?.user}
		<header class="border-b bg-card">
			<div class="container mx-auto px-6 py-4 flex justify-between items-center max-w-7xl">
				<div class="flex items-center gap-6">
					<a href="/admin/requests" class="font-semibold text-foreground hover:text-primary">
						Admin Dashboard
					</a>
					<nav class="flex items-center gap-1">
						<a
							href="/admin/requests"
							class="px-3 py-1.5 text-sm rounded-md transition-colors {$page.url.pathname.startsWith('/admin/requests') ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
						>
							Requests
						</a>
						<a
							href="/admin/jobs"
							class="px-3 py-1.5 text-sm rounded-md transition-colors {$page.url.pathname === '/admin/jobs' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
						>
							Jobs
						</a>
						<a
							href="/admin/settings"
							class="px-3 py-1.5 text-sm rounded-md transition-colors {$page.url.pathname === '/admin/settings' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:text-foreground hover:bg-muted'}"
						>
							Settings
						</a>
					</nav>
				</div>
				<div class="flex items-center gap-4">
					{#if data.session.user.email}
						<span class="text-sm text-muted-foreground">{data.session.user.email}</span>
					{/if}
					<Button variant="outline" size="sm" onclick={handleSignOut}>Sign Out</Button>
				</div>
			</div>
		</header>
	{/if}

	<slot />
</div>
