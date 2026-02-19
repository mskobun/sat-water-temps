<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Label } from '$lib/components/ui/label';
	import * as Select from '$lib/components/ui/select';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';
	import JobsTable from '$lib/components/admin/JobsTable.svelte';
	import type { Job } from '$lib/components/admin/JobsTable.svelte';

	const LIMIT = 50;
	const POLL_INTERVAL = 30_000;

	const filterOptions = [
		{ value: 'all', label: 'All Jobs' },
		{ value: 'success', label: 'Success' },
		{ value: 'failed', label: 'Failed' },
		{ value: 'started', label: 'In Progress' }
	];

	let jobs = $state<Job[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Jobs');
	let page = $state(1);
	let total = $state(0);
	let statusCounts = $state({ total: 0, success: 0, failed: 0, started: 0 });
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	const totalPages = $derived(Math.max(1, Math.ceil(total / LIMIT)));
	const rangeStart = $derived((page - 1) * LIMIT + 1);
	const rangeEnd = $derived(Math.min(page * LIMIT, total));

	async function fetchJobs() {
		try {
			const params = new URLSearchParams({ limit: String(LIMIT), page: String(page) });
			if (filter !== 'all') params.set('status', filter);
			const response = await fetch(`/api/admin/jobs?${params}`);
			const data = await response.json() as {
				jobs?: Job[];
				total?: number;
				status_counts?: typeof statusCounts;
				page?: number;
				limit?: number;
			};
			jobs = data.jobs || [];
			total = data.total ?? 0;
			if (data.status_counts) statusCounts = data.status_counts;
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch jobs';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function goToPage(p: number) {
		page = Math.max(1, Math.min(p, totalPages));
		fetchJobs();
	}

	$effect(() => {
		filter; // track filter changes only
		untrack(() => {
			page = 1;
			fetchJobs();
		});
	});

	onMount(() => {
		refreshInterval = setInterval(fetchJobs, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Job Status - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6">
			<h1 class="text-3xl font-bold mb-2">Processing Jobs</h1>
			<p class="text-muted-foreground">Monitor Lambda processing jobs and scraping tasks</p>
		</div>

		<!-- Lightweight filter toolbar (no Card wrapper) -->
		<div class="flex flex-wrap items-center justify-between gap-4 mb-6">
			<div class="flex items-center gap-4">
				<Label class="text-sm font-medium">Filter:</Label>
				<Select.Root type="single" bind:value={filter}>
					<Select.Trigger class="w-44">
						{#snippet children()}
							<span data-slot="select-value">{filterLabel}</span>
						{/snippet}
					</Select.Trigger>
					<Select.Content>
						{#each filterOptions as opt}
							<Select.Item value={opt.value} label={opt.label} />
						{/each}
					</Select.Content>
				</Select.Root>
			</div>
			<div class="flex items-center gap-3">
				{#if updatedAt}
					<span class="text-xs text-muted-foreground">Updated {updatedAt}</span>
				{/if}
				<Button variant="outline" size="sm" onclick={fetchJobs} disabled={loading}>
					↻ Refresh
				</Button>
			</div>
		</div>

		<!-- Stats cards — always global, never filtered -->
		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			{#each [
				{ label: 'Total', count: statusCounts.total },
				{ label: 'Success', count: statusCounts.success },
				{ label: 'Failed', count: statusCounts.failed },
				{ label: 'In Progress', count: statusCounts.started }
			] as stat}
				<Card.Card>
					<Card.Content class="pt-6">
						<div class="text-2xl font-bold">{stat.count}</div>
						<div class="text-sm text-muted-foreground">{stat.label}</div>
					</Card.Content>
				</Card.Card>
			{/each}
		</div>

		{#if loading && jobs.length === 0}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading jobs...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if jobs.length === 0}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No jobs found. Jobs will appear here once Lambda functions start running.
				</Card.Content>
			</Card.Card>
		{:else}
			<Card.Card>
				<JobsTable {jobs} showTaskId={true} />

				<!-- Pagination controls -->
				<div class="flex items-center justify-between px-4 py-3 border-t text-sm">
					<span class="text-muted-foreground">
						Showing {rangeStart}–{rangeEnd} of {total}
					</span>
					<div class="flex items-center gap-2">
						<Button
							variant="outline"
							size="sm"
							onclick={() => goToPage(page - 1)}
							disabled={page <= 1}
						>
							← Prev
						</Button>
						<span class="text-muted-foreground">Page {page} of {totalPages}</span>
						<Button
							variant="outline"
							size="sm"
							onclick={() => goToPage(page + 1)}
							disabled={page >= totalPages}
						>
							Next →
						</Button>
					</div>
				</div>
			</Card.Card>
		{/if}
	</div>
</div>
