<script lang="ts">
	import { onMount } from 'svelte';

	interface Job {
		id: number;
		job_type: string;
		task_id: string | null;
		feature_id: string | null;
		date: string | null;
		status: string;
		started_at: number;
		completed_at: number | null;
		duration_ms: number | null;
		error_message: string | null;
		metadata: string | null;
	}

	let jobs: Job[] = [];
	let loading = true;
	let error = '';
	let filter = 'all';
	let autoRefresh = false;
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	async function fetchJobs() {
		try {
			const statusParam = filter !== 'all' ? `?status=${filter}` : '';
			const response = await fetch(`/api/admin/jobs${statusParam}`);
			const data = await response.json();
			jobs = data.jobs || [];
			error = '';
		} catch (e) {
			error = 'Failed to fetch jobs';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function formatDate(timestamp: number) {
		return new Date(timestamp).toLocaleString();
	}

	function formatDuration(ms: number | null) {
		if (!ms) return '-';
		if (ms < 1000) return `${ms}ms`;
		return `${(ms / 1000).toFixed(1)}s`;
	}

	function getStatusColor(status: string) {
		switch (status) {
			case 'success':
				return 'bg-green-100 text-green-800';
			case 'failed':
				return 'bg-red-100 text-red-800';
			case 'started':
				return 'bg-yellow-100 text-yellow-800';
			default:
				return 'bg-gray-100 text-gray-800';
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			refreshInterval = setInterval(fetchJobs, 5000); // Refresh every 5s
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	$: if (filter) {
		fetchJobs();
	}

	onMount(() => {
		fetchJobs();
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Job Status - Admin</title>
	<script src="https://cdn.tailwindcss.com"></script>
</svelte:head>

<div class="container mx-auto p-6 max-w-7xl">
	<div class="mb-6">
		<h1 class="text-3xl font-bold text-gray-900 mb-2">Processing Jobs</h1>
		<p class="text-gray-600">Monitor Lambda processing jobs and scraping tasks</p>
	</div>

	<!-- Filters and Actions -->
	<div class="bg-white rounded-lg shadow p-4 mb-6 flex items-center justify-between">
		<div class="flex items-center gap-4">
			<label class="text-sm font-medium text-gray-700">Filter:</label>
			<select
				bind:value={filter}
				class="border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
			>
				<option value="all">All Jobs</option>
				<option value="success">Success</option>
				<option value="failed">Failed</option>
				<option value="started">In Progress</option>
			</select>
		</div>

		<div class="flex items-center gap-3">
			<button
				on:click={toggleAutoRefresh}
				class="px-4 py-2 text-sm font-medium rounded-md transition-colors {autoRefresh
					? 'bg-blue-600 text-white hover:bg-blue-700'
					: 'bg-gray-200 text-gray-700 hover:bg-gray-300'}"
			>
				{autoRefresh ? '⏸ Pause' : '▶ Auto-refresh'}
			</button>

			<button
				on:click={fetchJobs}
				disabled={loading}
				class="px-4 py-2 text-sm font-medium bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
			>
				🔄 Refresh
			</button>
		</div>
	</div>

	<!-- Stats -->
	<div class="grid grid-cols-4 gap-4 mb-6">
		{#each [
			{ label: 'Total', count: jobs.length, color: 'bg-blue-50' },
			{
				label: 'Success',
				count: jobs.filter((j) => j.status === 'success').length,
				color: 'bg-green-50'
			},
			{
				label: 'Failed',
				count: jobs.filter((j) => j.status === 'failed').length,
				color: 'bg-red-50'
			},
			{
				label: 'In Progress',
				count: jobs.filter((j) => j.status === 'started').length,
				color: 'bg-yellow-50'
			}
		] as stat}
			<div class="rounded-lg shadow p-4 {stat.color}">
				<div class="text-2xl font-bold">{stat.count}</div>
				<div class="text-sm text-gray-600">{stat.label}</div>
			</div>
		{/each}
	</div>

	<!-- Jobs Table -->
	{#if loading}
		<div class="bg-white rounded-lg shadow p-12 text-center">
			<div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
			<p class="text-gray-600">Loading jobs...</p>
		</div>
	{:else if error}
		<div class="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
			{error}
		</div>
	{:else if jobs.length === 0}
		<div class="bg-white rounded-lg shadow p-12 text-center text-gray-500">
			No jobs found. Jobs will appear here once Lambda functions start running.
		</div>
	{:else}
		<div class="bg-white rounded-lg shadow overflow-hidden">
			<table class="min-w-full divide-y divide-gray-200">
				<thead class="bg-gray-50">
					<tr>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Status
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Type
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Feature / Date
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Task ID
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Started
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Duration
						</th>
						<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
							Error
						</th>
					</tr>
				</thead>
				<tbody class="bg-white divide-y divide-gray-200">
					{#each jobs as job}
						<tr class="hover:bg-gray-50">
							<td class="px-6 py-4 whitespace-nowrap">
								<span
									class="px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full {getStatusColor(
										job.status
									)}"
								>
									{job.status}
								</span>
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{job.job_type}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{#if job.feature_id}
									<div class="font-medium">{job.feature_id}</div>
									{#if job.date}
										<div class="text-xs text-gray-500">{job.date}</div>
									{/if}
								{:else}
									-
								{/if}
							</td>
							<td class="px-6 py-4 text-sm text-gray-500 font-mono">
								{#if job.task_id}
									<span class="text-xs">{job.task_id.slice(0, 12)}...</span>
								{:else}
									-
								{/if}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
								{formatDate(job.started_at)}
							</td>
							<td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
								{formatDuration(job.duration_ms)}
							</td>
							<td class="px-6 py-4 text-sm text-red-600 max-w-xs truncate">
								{job.error_message || '-'}
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	{/if}
</div>

