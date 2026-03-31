<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { today, getLocalTimeZone } from '@internationalized/date';
	import type { DateRange } from 'bits-ui';
	import * as Card from '$lib/components/ui/card';
	import StatBar from '$lib/components/admin/StatBar.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Table from '$lib/components/ui/table';
	import * as Select from '$lib/components/ui/select';
	import * as Popover from '$lib/components/ui/popover';
	import * as Dialog from '$lib/components/ui/dialog';
	import { RangeCalendar } from '$lib/components/ui/range-calendar';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

	const POLL_INTERVAL = 30_000;

	type Source = 'ecostress' | 'landsat';

	interface DataRequest {
		id: number;
		source: string;
		task_id: string | null;
		trigger_type: string;
		triggered_by: string | null;
		description: string | null;
		start_date: string;
		end_date: string;
		status: string;
		scenes_count: number | null;
		created_at: number;
		updated_at: number | null;
		error_message: string | null;
		total_jobs: number;
		success_jobs: number;
		failed_jobs: number;
		running_jobs: number;
	}

	const filterOptions = [
		{ value: 'all', label: 'All Requests' },
		{ value: 'pending', label: 'Pending' },
		{ value: 'submitted', label: 'Submitted' },
		{ value: 'processing', label: 'Processing' },
		{ value: 'completed', label: 'Completed' },
		{ value: 'completed_with_errors', label: 'Completed w/ Errors' },
		{ value: 'failed', label: 'Failed' }
	];

	let source = $state<Source>('ecostress');
	let requests = $state<DataRequest[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Requests');
	let updatedAt = $state('');
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	// Trigger dialog state — triggerSource syncs with active tab when dialog opens
	let dialogOpen = $state(false);
	let triggerSource = $state<Source>('ecostress');

	$effect(() => {
		if (dialogOpen) {
			triggerSource = source;
		}
	});
	let triggerDateRange = $state<DateRange>({ start: undefined, end: undefined });
	let triggerDescription = $state('');
	let triggerLoading = $state(false);
	let triggerError = $state('');
	let triggerSuccess = $state('');
	let calendarOpen = $state(false);

	const dayCount = $derived(() => {
		const { start, end } = triggerDateRange;
		if (!start || !end) return 0;
		const tz = getLocalTimeZone();
		return Math.round((end.toDate(tz).getTime() - start.toDate(tz).getTime()) / 86400000) + 1;
	});

	async function fetchRequests() {
		try {
			const params = new URLSearchParams();
			if (filter !== 'all') params.set('status', filter);
			params.set('source', source);
			const qs = params.toString();
			const response = await fetch(`/api/admin/requests?${qs}`);
			const data = (await response.json()) as { requests?: DataRequest[] };
			requests = data.requests || [];
			error = '';
			updatedAt = new Date().toLocaleTimeString();
		} catch (e) {
			error = 'Failed to fetch requests';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function formatDate(timestamp: number) {
		return new Date(timestamp).toLocaleString();
	}

	function formatStatus(status: string): string {
		const labels: Record<string, string> = {
			pending: 'Pending',
			submitted: 'Submitted',
			processing: 'Processing',
			completed: 'Completed',
			completed_with_errors: 'Completed with Errors',
			failed: 'Failed'
		};
		return labels[status] ?? status;
	}

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'processing': return 'default';
			case 'completed': return 'secondary';
			case 'completed_with_errors': return 'destructive';
			case 'failed': return 'destructive';
			case 'pending': return 'outline';
			default: return 'secondary';
		}
	}

	function getTriggerVariant(type: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (type) {
			case 'manual': return 'secondary';
			case 'reprocess': return 'outline';
			default: return 'default';
		}
	}

	async function handleTrigger() {
		if (!triggerDateRange.start || !triggerDateRange.end) return;

		triggerLoading = true;
		triggerError = '';
		triggerSuccess = '';

		try {
			const response = await fetch('/api/admin/trigger', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					startDate: triggerDateRange.start!.toString(),
					endDate: triggerDateRange.end!.toString(),
					description: triggerDescription || undefined,
					source: triggerSource
				})
			});

			const data = await response.json() as { count?: number; error?: string; warning?: string; message?: string };

			if (!response.ok) {
				triggerError = data.error || `Request failed with status ${response.status}`;
			} else if (data.warning) {
				triggerSuccess = `${data.count} request(s) recorded. ${data.warning}`;
			} else {
				triggerSuccess = data.message || `Created ${data.count} request(s)`;
				triggerDateRange = { start: undefined, end: undefined };
				triggerDescription = '';
				fetchRequests();
				setTimeout(() => { dialogOpen = false; triggerSuccess = ''; }, 2000);
			}
		} catch (e) {
			triggerError = 'Failed to trigger processing';
			console.error(e);
		} finally {
			triggerLoading = false;
		}
	}

	function switchSource(newSource: Source) {
		source = newSource;
		filter = 'all';
		loading = true;
		requests = [];
	}

	$effect(() => {
		if (source || filter) fetchRequests();
	});

	onMount(() => {
		refreshInterval = setInterval(fetchRequests, POLL_INTERVAL);
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>Processing Requests - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-3xl font-bold mb-2">Processing Requests</h1>
				<p class="text-muted-foreground">
					{#if source === 'ecostress'}
						Track ECOSTRESS scan requests and their processing results
					{:else}
						Track Landsat scene scanning and processing runs
					{/if}
				</p>
			</div>

			<!-- Trigger Processing Dialog -->
			<Dialog.Root bind:open={dialogOpen}>
				<Dialog.Trigger>
					{#snippet children()}
						<Button>Trigger Processing</Button>
					{/snippet}
				</Dialog.Trigger>
				<Dialog.Content class="sm:max-w-md">
					<Dialog.Header>
						<Dialog.Title>Manual Processing Trigger</Dialog.Title>
						<Dialog.Description>
							{#if triggerSource === 'ecostress'}
								Run one ECOSTRESS scan for the selected date range and queue matching granules for processing.
							{:else}
								Scan for Landsat scenes in the selected date range and queue them for processing.
							{/if}
						</Dialog.Description>
					</Dialog.Header>
					<div class="flex flex-col gap-4 py-2">
						<div class="flex flex-col gap-1.5">
							<Label>Source</Label>
							<div class="flex gap-1 rounded-md border p-1">
								<button
									class="flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors {triggerSource === 'ecostress' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
									onclick={() => { triggerSource = 'ecostress'; }}
								>ECOSTRESS</button>
								<button
									class="flex-1 rounded px-3 py-1.5 text-sm font-medium transition-colors {triggerSource === 'landsat' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
									onclick={() => { triggerSource = 'landsat'; }}
								>Landsat</button>
							</div>
						</div>
						<div class="flex flex-col gap-1.5">
							<Label>Date Range</Label>
							<Popover.Root bind:open={calendarOpen}>
								<Popover.Trigger>
									{#snippet children()}
										<Button variant="outline" class="w-full justify-start text-left font-normal">
											{#if triggerDateRange.start && triggerDateRange.end}
												{triggerDateRange.start} – {triggerDateRange.end}
											{:else if triggerDateRange.start}
												{triggerDateRange.start} – …
											{:else}
												<span class="text-muted-foreground">Select date range</span>
											{/if}
										</Button>
									{/snippet}
								</Popover.Trigger>
								<Popover.Content class="w-auto p-0" align="start">
									<RangeCalendar
										bind:value={triggerDateRange}
										maxValue={today(getLocalTimeZone())}
										captionLayout="dropdown"
										onValueChange={(v) => {
											if (v.start && v.end) {
												calendarOpen = false;
											}
										}}
									/>
								</Popover.Content>
							</Popover.Root>
						</div>
						{#if triggerDateRange.start && triggerDateRange.end}
							<p class="text-sm text-muted-foreground">
								{#if triggerSource === 'ecostress'}
									1 ECOSTRESS scan will be created for {dayCount()} day(s)
								{:else}
									1 Landsat scan will be created for {dayCount()} day(s)
								{/if}
							</p>
						{/if}
						<div class="flex flex-col gap-1.5">
							<Label for="trigger-desc">Description (optional)</Label>
							<Input
								id="trigger-desc"
								type="text"
								placeholder="e.g. Re-process after cloud clearing"
								bind:value={triggerDescription}
							/>
						</div>
						{#if triggerError}
							<Alert variant="destructive">
								<AlertDescription>{triggerError}</AlertDescription>
							</Alert>
						{/if}
						{#if triggerSuccess}
							<Alert>
								<AlertDescription>{triggerSuccess}</AlertDescription>
							</Alert>
						{/if}
					</div>
					<Dialog.Footer>
						<Button variant="outline" onclick={() => { dialogOpen = false; }}>Cancel</Button>
						<Button onclick={handleTrigger} disabled={triggerLoading || !triggerDateRange.start || !triggerDateRange.end}>
							{#if triggerLoading}
								<Spinner class="size-4 mr-2" />
							{/if}
							Submit
						</Button>
					</Dialog.Footer>
				</Dialog.Content>
			</Dialog.Root>
		</div>

		<!-- Source tabs -->
		<div class="flex gap-1 rounded-md border p-1 w-fit mb-6">
			<button
				class="rounded px-4 py-1.5 text-sm font-medium transition-colors {source === 'ecostress' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
				onclick={() => switchSource('ecostress')}
			>ECOSTRESS</button>
			<button
				class="rounded px-4 py-1.5 text-sm font-medium transition-colors {source === 'landsat' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
				onclick={() => switchSource('landsat')}
			>Landsat</button>
		</div>

		<!-- Lightweight filter toolbar -->
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
				<Button variant="outline" size="sm" onclick={fetchRequests} disabled={loading}>
					↻ Refresh
				</Button>
			</div>
		</div>

		<div class="mb-6">
			<StatBar stats={[
				{ label: 'Total', count: requests.length },
				{ label: 'Pending', count: requests.filter((r) => r.status === 'pending').length },
				{ label: 'Processing', count: requests.filter((r) => r.status === 'processing').length },
				{ label: 'Completed', count: requests.filter((r) => r.status === 'completed').length },
				{ label: 'Failed', count: requests.filter((r) => r.status === 'failed' || r.status === 'completed_with_errors').length }
			]} />
		</div>

		{#if loading && requests.length === 0}
			<Card.Card>
				<Card.Content class="flex flex-col items-center justify-center py-12 gap-4">
					<Spinner class="size-12" />
					<p class="text-muted-foreground">Loading requests...</p>
				</Card.Content>
			</Card.Card>
		{:else if error}
			<Alert variant="destructive">
				<AlertDescription>{error}</AlertDescription>
			</Alert>
		{:else if requests.length === 0}
			<Card.Card>
				<Card.Content class="py-12 text-center text-muted-foreground">
					No requests found. Requests will appear here once the pipeline runs or you trigger one manually.
				</Card.Content>
			</Card.Card>
		{:else}
			<div class="overflow-x-auto rounded-md border">
				<Table.Root>
						<Table.Header>
							<Table.Row>
								<Table.Head>Trigger</Table.Head>
								<Table.Head>Status</Table.Head>
								<Table.Head>Date Range</Table.Head>
								<Table.Head>Description</Table.Head>
								<Table.Head>Scenes</Table.Head>
								<Table.Head>Processing</Table.Head>
								<Table.Head>Created</Table.Head>
							</Table.Row>
						</Table.Header>
						<Table.Body>
							{#each requests as r}
								<Table.Row
									class="cursor-pointer hover:bg-muted/50"
									onclick={() => goto(`/admin/requests/${r.id}?source=${source}`)}
								>
									<Table.Cell>
										<Badge variant={getTriggerVariant(r.trigger_type)}>{r.trigger_type}</Badge>
									</Table.Cell>
									<Table.Cell>
										<Badge variant={getStatusVariant(r.status)}>{formatStatus(r.status)}</Badge>
									</Table.Cell>
									<Table.Cell class="text-sm">
										<div>{r.start_date}</div>
										{#if r.start_date !== r.end_date}
											<div class="text-xs text-muted-foreground">to {r.end_date}</div>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm max-w-xs truncate">
										{r.description || '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{r.scenes_count ?? '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{#if r.total_jobs > 0}
											<div>
												<span class="text-green-600 font-medium">{r.success_jobs}</span>
												<span class="text-muted-foreground"> / {r.total_jobs}</span>
											</div>
											{#if r.failed_jobs > 0}
												<div class="text-xs text-destructive">{r.failed_jobs} failed</div>
											{/if}
											{#if r.running_jobs > 0}
												<div class="text-xs text-blue-600">{r.running_jobs} running</div>
											{/if}
										{:else}
											<span class="text-muted-foreground">-</span>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatDate(r.created_at)}
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>
				</div>
		{/if}
	</div>
</div>
