<script lang="ts">
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
				<div class="flex items-center gap-4">
					<a href="/admin/jobs" class="font-semibold text-foreground hover:text-primary">
						Admin Dashboard
					</a>
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
