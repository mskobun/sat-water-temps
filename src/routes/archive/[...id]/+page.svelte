<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Spinner } from '$lib/components/ui/spinner';

	const featureId = $page.params.id;
	let dates: string[] = [];
	let loading = true;

	function formatDateTime(date: string): string {
		const year = date.substring(0, 4);
		const doy = parseInt(date.substring(4, 7), 10);
		const hours = date.substring(7, 9);
		const minutes = date.substring(9, 11);
		const seconds = date.substring(11, 13);
		const dateObj = new Date(parseInt(year), 0);
		dateObj.setDate(doy);
		const day = String(dateObj.getDate()).padStart(2, '0');
		const month = String(dateObj.getMonth() + 1).padStart(2, '0');
		return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
	}

	onMount(async () => {
		try {
			const response = await fetch(`/api/feature/${featureId}/get_dates`);
			dates = await response.json();
		} catch (err) {
			console.error('Error loading archive:', err);
		} finally {
			loading = false;
		}
	});
</script>

<svelte:head>
	<title>{featureId} Archive</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<header class="border-b px-6 py-5">
		<h1 class="text-2xl font-bold uppercase">{featureId} Archive</h1>
	</header>

	<div class="w-[90%] mx-auto py-5">
		<div class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4">
			{#if loading}
				<div class="col-span-full flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-8" />
					<p class="text-muted-foreground">Loading archive data...</p>
				</div>
			{:else if dates.length === 0}
				<div class="col-span-full py-12 text-center text-muted-foreground">
					No data available for this feature
				</div>
			{:else}
				{#each dates as date}
					<Card.Card class="overflow-hidden transition-transform hover:scale-[1.02]">
						<Card.Content class="p-0">
							<div class="aspect-square bg-muted flex items-center justify-center overflow-hidden">
								<img
									src={`/api/feature/${featureId}/tif/${date}/relative`}
									alt={`${featureId} - ${formatDateTime(date)}`}
									class="max-w-full max-h-full object-contain"
								/>
							</div>
							<div class="p-3 space-y-2">
								<div
									class="text-sm font-medium truncate"
									title={date}
								>
									{formatDateTime(date)}
								</div>
								<div class="flex flex-col gap-1">
									<Button
										variant="link"
										size="sm"
										class="h-auto p-0 justify-start font-semibold"
										href={`/api/feature/${featureId}/tif/${date}/file`}
										download
									>
										Download TIF
									</Button>
									<Button
										variant="link"
										size="sm"
										class="h-auto p-0 justify-start font-semibold"
										href={`/api/download_csv/${featureId}/${date}`}
										download
									>
										Download CSV
									</Button>
								</div>
							</div>
						</Card.Content>
					</Card.Card>
				{/each}
			{/if}
		</div>
	</div>
</div>
