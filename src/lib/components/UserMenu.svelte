<script lang="ts">
	import { signOut } from '@auth/sveltekit/client';
	import { page } from '$app/stores';
	import { Button } from '$lib/components/ui/button';
	import * as Popover from '$lib/components/ui/popover';
	import * as Dialog from '$lib/components/ui/dialog';
	import { Separator } from '$lib/components/ui/separator';
	import UserIcon from '@lucide/svelte/icons/user';
	import TableIcon from '@lucide/svelte/icons/table';

	let { inline = false }: { inline?: boolean } = $props();

	let session = $derived($page.data.session);
	let aboutOpen = $state(false);
	let onDashboard = $derived($page.url.pathname.startsWith('/dashboard'));
	let onAdmin = $derived($page.url.pathname.startsWith('/admin'));
	let onMap = $derived(!onDashboard && !onAdmin && !$page.url.pathname.startsWith('/archive'));

	function handleSignOut() {
		signOut({ callbackUrl: '/admin/login' });
	}
</script>

{#snippet menu()}
	<Popover.Root>
		<Popover.Trigger>
			{#snippet child({ props })}
				<Button variant={inline ? 'ghost' : 'secondary'} size="icon" class={inline ? 'size-9' : 'size-9 shadow-sm'} {...props}>
					<UserIcon class="size-4" />
					<span class="sr-only">User menu</span>
				</Button>
			{/snippet}
		</Popover.Trigger>
		<Popover.Content class="w-52 p-2" align="end">
			{#if !onMap}
				<a href="/" class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
					Map
				</a>
			{/if}
			{#if !onDashboard}
				<a href="/dashboard" class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
					Dashboard
				</a>
			{/if}
			{#if session?.user}
				<div class="px-2 py-1.5 text-xs text-muted-foreground truncate">
					{session.user.email}
				</div>
				{#if !onAdmin}
					<a href="/admin/requests" class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
						Admin Panel
					</a>
				{/if}
				<button onclick={handleSignOut} class="w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
					Sign Out
				</button>
				<Separator class="my-1" />
			{:else}
				<a href="/admin/login" class="block w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
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
			<button onclick={() => (aboutOpen = true)} class="w-full text-left text-sm py-1.5 px-2 rounded hover:bg-muted">
				About
			</button>
		</Popover.Content>
	</Popover.Root>
{/snippet}

{#if inline}
	{@render menu()}
{:else}
	<div class="absolute top-4 right-4 z-40 flex items-center gap-2">
		{#if !onDashboard}
			<Button variant="secondary" size="icon" class="size-9 shadow-sm" href="/dashboard">
				<TableIcon class="size-4" />
				<span class="sr-only">List view</span>
			</Button>
		{/if}
		{@render menu()}
	</div>
{/if}

<Dialog.Root bind:open={aboutOpen}>
	<Dialog.Content class="sm:max-w-md">
		<Dialog.Header>
			<Dialog.Title>Satellite Water Temperature Monitoring</Dialog.Title>
			<Dialog.Description>
				This map shows water bodies monitored with ECOSTRESS and Landsat satellite data. Click a
				polygon to view temperature time series and thermal imagery. ECOSTRESS data is sourced
				from NASA AppEEARS; Landsat Collection 2 Level-2 Surface Temperature is sourced directly
				from USGS.
			</Dialog.Description>
		</Dialog.Header>
	</Dialog.Content>
</Dialog.Root>
