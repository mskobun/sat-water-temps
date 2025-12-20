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
	<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet" />
</svelte:head>

<header>
	<span>{featureId} Archive</span>
	<button id="back-btn" on:click={() => window.history.back()}>Back</button>
</header>

<div class="container">
	<div class="grid-container">
		{#if loading}
			<div class="loading">Loading archive data...</div>
		{:else if dates.length === 0}
			<div class="loading">No data available for this feature</div>
		{:else}
			{#each dates as date}
				<div class="grid-item">
					<img 
						src={`/api/feature/${featureId}/tif/${date}/relative`}
						alt={`${featureId} - ${formatDateTime(date)}`}
					/>
					<div class="caption" title={date}>
						{formatDateTime(date)}
					</div>
					<a 
						class="download-link"
						href={`/api/download_tif/${featureId}/${date}_filter_relative.tif`}
						download
					>
						Download TIF
					</a>
					<a 
						class="download-link"
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

<style>
	.container {
		text-align: center;
	}
	
	header {
		background: linear-gradient(135deg, #0b3d91, #48c6ef);
		padding: 20px;
		font-size: 24px;
		font-weight: bold;
		text-transform: uppercase;
		position: relative;
	}
	
	.container {
		width: 90%;
		margin: auto;
		padding: 20px;
	}
	
	.grid-container {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: 15px;
		padding-top: 10px;
	}
	
	.grid-item {
		background: #1e1e1e;
		border-radius: 8px;
		padding: 10px;
		box-shadow: 0px 4px 8px rgba(0, 0, 0, 0.2);
		transition: transform 0.3s ease;
	}
	
	.grid-item:hover {
		transform: scale(1.05);
	}
	
	img {
		width: 100%;
		border-radius: 5px;
	}
	
	.caption {
		margin-top: 8px;
		font-size: 14px;
		font-weight: bold;
		color: #ddd;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
	}
	
	.download-link {
		display: block;
		margin-top: 5px;
		font-size: 14px;
		color: #48c6ef;
		text-decoration: none;
		font-weight: 600;
	}
	
	.download-link:hover {
		text-decoration: underline;
	}
	
	#back-btn {
		position: absolute;
		top: 50%;
		left: 20px;
		transform: translateY(-50%);
		background-color: #007BFF;
		color: #fff;
		padding: 12px 25px;
		border: none;
		border-radius: 10px;
		cursor: pointer;
		font-size: 16px;
		font-weight: bold;
		transition: background-color 0.3s;
	}
	
	#back-btn:hover {
		background-color: #0056b3;
	}
	
	.loading {
		color: #48c6ef;
		font-size: 18px;
		padding: 20px;
	}
</style>
