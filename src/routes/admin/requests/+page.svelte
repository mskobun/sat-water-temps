<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { CalendarDate, today, getLocalTimeZone } from '@internationalized/date';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as Table from '$lib/components/ui/table';
	import * as Select from '$lib/components/ui/select';
	import * as Popover from '$lib/components/ui/popover';
	import { Calendar } from '$lib/components/ui/calendar';
	import { Badge } from '$lib/components/ui/badge';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';
	import { Spinner } from '$lib/components/ui/spinner';

	interface EcostressRequest {
		id: number;
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
		{ value: 'failed', label: 'Failed' }
	];

	let requests = $state<EcostressRequest[]>([]);
	let loading = $state(true);
	let error = $state('');
	let filter = $state('all');
	let filterLabel = $derived(filterOptions.find((o) => o.value === filter)?.label ?? 'All Requests');
	let autoRefresh = $state(false);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	// Trigger form state
	let showTriggerForm = $state(false);
	let triggerDateValue = $state<CalendarDate | undefined>(undefined);
	let triggerDescription = $state('');
	let triggerLoading = $state(false);
	let triggerError = $state('');
	let triggerSuccess = $state('');
	let calendarOpen = $state(false);

	const triggerDateFormatted = $derived(
		triggerDateValue
			? `${triggerDateValue.year}-${String(triggerDateValue.month).padStart(2, '0')}-${String(triggerDateValue.day).padStart(2, '0')}`
			: ''
	);

	async function fetchRequests() {
		try {
			const statusParam = filter !== 'all' ? `?status=${filter}` : '';
			const response = await fetch(`/api/admin/requests${statusParam}`);
			const data = (await response.json()) as { requests?: EcostressRequest[] };
			requests = data.requests || [];
			error = '';
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

	function getStatusVariant(status: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (status) {
			case 'submitted':
			case 'processing':
				return 'default';
			case 'failed':
				return 'destructive';
			case 'pending':
				return 'outline';
			default:
				return 'secondary';
		}
	}

	function getTriggerVariant(type: string): 'default' | 'secondary' | 'destructive' | 'outline' {
		switch (type) {
			case 'manual':
				return 'secondary';
			case 'reprocess':
				return 'outline';
			default:
				return 'default';
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) {
			refreshInterval = setInterval(fetchRequests, 5000);
		} else if (refreshInterval) {
			clearInterval(refreshInterval);
			refreshInterval = null;
		}
	}

	async function handleTrigger() {
		if (!triggerDateFormatted) return;

		triggerLoading = true;
		triggerError = '';
		triggerSuccess = '';

		try {
			const response = await fetch('/api/admin/trigger', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					date: triggerDateFormatted,
					description: triggerDescription || undefined
				})
			});

			const data = await response.json() as { id?: number; error?: string; warning?: string; message?: string };

			if (!response.ok) {
				triggerError = data.error || `Request failed with status ${response.status}`;
			} else if (data.warning) {
				triggerSuccess = data.warning;
			} else {
				triggerSuccess = data.message || 'Processing triggered successfully';
				triggerDateValue = undefined;
				triggerDescription = '';
				showTriggerForm = false;
				fetchRequests();
			}
		} catch (e) {
			triggerError = 'Failed to trigger processing';
			console.error(e);
		} finally {
			triggerLoading = false;
		}
	}

	$effect(() => {
		if (filter) {
			fetchRequests();
		}
	});

	onMount(() => {
		fetchRequests();
		return () => {
			if (refreshInterval) clearInterval(refreshInterval);
		};
	});
</script>

<svelte:head>
	<title>ECOSTRESS Requests - Admin</title>
</svelte:head>

<div class="min-h-screen bg-background text-foreground">
	<div class="container mx-auto p-6 max-w-7xl">
		<div class="mb-6 flex items-start justify-between">
			<div>
				<h1 class="text-3xl font-bold mb-2">ECOSTRESS Requests</h1>
				<p class="text-muted-foreground">Track AppEEARS task submissions and their processing results</p>
			</div>
			<Button onclick={() => (showTriggerForm = !showTriggerForm)}>
				{showTriggerForm ? 'Cancel' : 'Trigger Processing'}
			</Button>
		</div>

		{#if showTriggerForm}
			<Card.Card class="mb-6">
				<Card.Header>
					<Card.Title>Manual Processing Trigger</Card.Title>
				</Card.Header>
				<Card.Content>
					<div class="flex flex-wrap items-end gap-4">
						<div class="flex flex-col gap-1.5">
							<Label>Date</Label>
							<Popover.Root bind:open={calendarOpen}>
								<Popover.Trigger>
									{#snippet children()}
										<Button variant="outline" class="w-56 justify-start text-left font-normal">
											{#if triggerDateValue}
												{triggerDateFormatted}
											{:else}
												<span class="text-muted-foreground">Pick a date</span>
											{/if}
										</Button>
									{/snippet}
								</Popover.Trigger>
								<Popover.Content class="w-auto p-0" align="start">
									<Calendar
										type="single"
										bind:value={triggerDateValue}
										maxValue={today(getLocalTimeZone())}
										onValueChange={() => { calendarOpen = false; }}
									/>
								</Popover.Content>
							</Popover.Root>
						</div>
						<div class="flex flex-col gap-1.5 flex-1 min-w-48">
							<Label for="trigger-desc">Description (optional)</Label>
							<Input
								id="trigger-desc"
								type="text"
								placeholder="e.g. Re-process after cloud clearing"
								bind:value={triggerDescription}
							/>
						</div>
						<Button onclick={handleTrigger} disabled={triggerLoading || !triggerDateValue}>
							{#if triggerLoading}
								<Spinner class="size-4 mr-2" />
							{/if}
							Submit
						</Button>
					</div>
					{#if triggerError}
						<Alert variant="destructive" class="mt-4">
							<AlertDescription>{triggerError}</AlertDescription>
						</Alert>
					{/if}
					{#if triggerSuccess}
						<Alert class="mt-4">
							<AlertDescription>{triggerSuccess}</AlertDescription>
						</Alert>
					{/if}
				</Card.Content>
			</Card.Card>
		{/if}

		<Card.Card class="mb-6">
			<Card.Content class="pt-6">
				<div class="flex flex-wrap items-center justify-between gap-4">
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
						<Button variant={autoRefresh ? 'default' : 'secondary'} size="sm" onclick={toggleAutoRefresh}>
							{autoRefresh ? 'Pause' : 'Auto-refresh'}
						</Button>
						<Button variant="outline" size="sm" onclick={fetchRequests} disabled={loading}>
							Refresh
						</Button>
					</div>
				</div>
			</Card.Content>
		</Card.Card>

		<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
			{#each [
				{ label: 'Total', count: requests.length },
				{ label: 'Pending/Submitted', count: requests.filter((r) => r.status === 'pending' || r.status === 'submitted').length },
				{ label: 'Processing', count: requests.filter((r) => r.status === 'processing').length },
				{ label: 'Failed', count: requests.filter((r) => r.status === 'failed').length }
			] as stat}
				<Card.Card>
					<Card.Content class="pt-6">
						<div class="text-2xl font-bold">{stat.count}</div>
						<div class="text-sm text-muted-foreground">{stat.label}</div>
					</Card.Content>
				</Card.Card>
			{/each}
		</div>

		{#if loading}
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
			<Card.Card>
				<div class="overflow-x-auto">
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
							{#each requests as req}
								<Table.Row
									class="cursor-pointer hover:bg-muted/50"
									onclick={() => goto(`/admin/requests/${req.id}`)}
								>
									<Table.Cell>
										<Badge variant={getTriggerVariant(req.trigger_type)}>{req.trigger_type}</Badge>
									</Table.Cell>
									<Table.Cell>
										<Badge variant={getStatusVariant(req.status)}>{req.status}</Badge>
									</Table.Cell>
									<Table.Cell class="text-sm">
										<div>{req.start_date}</div>
										{#if req.start_date !== req.end_date}
											<div class="text-xs text-muted-foreground">to {req.end_date}</div>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm max-w-xs truncate">
										{req.description || '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{req.scenes_count ?? '-'}
									</Table.Cell>
									<Table.Cell class="text-sm">
										{#if req.total_jobs > 0}
											<div class="flex items-center gap-1.5">
												{#if req.success_jobs > 0}
													<span class="text-green-600">{req.success_jobs}ok</span>
												{/if}
												{#if req.failed_jobs > 0}
													<span class="text-destructive">{req.failed_jobs}err</span>
												{/if}
												{#if req.running_jobs > 0}
													<span class="text-blue-600">{req.running_jobs}run</span>
												{/if}
											</div>
										{:else}
											<span class="text-muted-foreground">-</span>
										{/if}
									</Table.Cell>
									<Table.Cell class="text-sm text-muted-foreground">
										{formatDate(req.created_at)}
									</Table.Cell>
								</Table.Row>
							{/each}
						</Table.Body>
					</Table.Root>
				</div>
			</Card.Card>
		{/if}
	</div>
</div>
