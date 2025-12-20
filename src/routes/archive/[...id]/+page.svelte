<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	
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

<div class="min-h-screen bg-dark-bg font-poppins text-white">
	<!-- Header -->
	<header class="bg-gradient-to-r from-[#0b3d91] to-cyan py-5 px-6 text-2xl font-bold uppercase flex items-center gap-4">
		<button 
			class="bg-blue-600 hover:bg-blue-800 text-white px-6 py-3 rounded-xl border-none cursor-pointer text-base font-bold transition-colors duration-300 shrink-0"
			onclick={() => window.history.back()}
		>
			Back
		</button>
		<span>{featureId} Archive</span>
	</header>

	<!-- Content -->
	<div class="w-[90%] mx-auto py-5 text-center">
		<div class="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-4 pt-2.5">
			{#if loading}
				<div class="text-cyan text-lg p-5 col-span-full">Loading archive data...</div>
			{:else if dates.length === 0}
				<div class="text-cyan text-lg p-5 col-span-full">No data available for this feature</div>
			{:else}
				{#each dates as date}
					<div class="bg-dark-surface rounded-lg p-2.5 shadow-lg hover:scale-105 transition-transform duration-300">
						<img 
							src={`/api/feature/${featureId}/tif/${date}/relative`}
							alt={`${featureId} - ${formatDateTime(date)}`}
							class="w-full rounded-md"
						/>
						<div class="mt-2 text-sm font-bold text-gray-300 whitespace-nowrap overflow-hidden text-ellipsis" title={date}>
							{formatDateTime(date)}
						</div>
						<a 
							class="block mt-1 text-sm text-cyan hover:underline font-semibold no-underline"
							href={`/api/download_tif/${featureId}/${date}_filter_relative.tif`}
							download
						>
							Download TIF
						</a>
						<a 
							class="block mt-1 text-sm text-cyan hover:underline font-semibold no-underline"
							href={`/api/download_csv/${featureId}/${date}_filter_relative.csv`}
							download
						>
							Download CSV
						</a>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</div>
