<script lang="ts">
	import { signOut } from '@auth/sveltekit/client';
	import { page } from '$app/stores';
	import { Button } from '$lib/components/ui/button';
	import * as Popover from '$lib/components/ui/popover';
	import { Separator } from '$lib/components/ui/separator';
	import UserIcon from '@lucide/svelte/icons/user';

	let session = $derived($page.data.session);

	function handleSignOut() {
		signOut({ callbackUrl: '/admin/login' });
	}
</script>

<div class="absolute top-4 right-4 z-40">
	<Popover.Root>
		<Popover.Trigger>
			{#snippet child({ props })}
				<Button variant="outline" size="icon" class="h-10 w-10 shadow-sm" {...props}>
					<UserIcon class="size-4" />
					<span class="sr-only">User menu</span>
				</Button>
			{/snippet}
		</Popover.Trigger>
		<Popover.Content class="w-52 p-2" align="end">
			{#if session?.user}
				<div class="px-2 py-1.5 text-xs text-muted-foreground truncate">
					{session.user.email}
				</div>
				<a
					href="/admin/requests"
					class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted"
				>
					Admin Panel
				</a>
				<button
					onclick={handleSignOut}
					class="w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted"
				>
					Sign Out
				</button>
				<Separator class="my-1" />
			{:else}
				<a
					href="/admin/login"
					class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted"
				>
					Log in
				</a>
				<Separator class="my-1" />
			{/if}
			<a
				href="https://github.com/mskobun/sat-water-temps"
				target="_blank"
				rel="noopener noreferrer"
				class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted"
			>
				Source Code
			</a>
			<span class="block w-full text-left text-sm py-1.5 px-2 rounded text-muted-foreground cursor-default">
				About (coming soon)
			</span>
		</Popover.Content>
	</Popover.Root>
</div>
