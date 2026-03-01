<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';

	let dataDelayDays = $state('2');
	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let success = $state('');

	onMount(async () => {
		try {
			const res = await fetch('/api/admin/settings');
			if (!res.ok) throw new Error('Failed to load settings');
			const settings = await res.json();
			if (settings.data_delay_days !== undefined) {
				dataDelayDays = settings.data_delay_days;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load settings';
		} finally {
			loading = false;
		}
	});

	async function save() {
		error = '';
		success = '';
		const val = parseInt(dataDelayDays);
		if (isNaN(val) || val < 0 || val > 30) {
			error = 'Delay must be a number between 0 and 30';
			return;
		}
		saving = true;
		try {
			const res = await fetch('/api/admin/settings', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ key: 'data_delay_days', value: String(val) })
			});
			if (!res.ok) throw new Error('Failed to save');
			success = 'Setting saved';
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save';
		} finally {
			saving = false;
		}
	}
</script>

<div class="container mx-auto px-6 py-8 max-w-2xl">
	<h1 class="text-2xl font-semibold mb-6">Settings</h1>

	{#if error}
		<Alert variant="destructive" class="mb-4">
			<AlertDescription>{error}</AlertDescription>
		</Alert>
	{/if}

	{#if success}
		<Alert class="mb-4">
			<AlertDescription>{success}</AlertDescription>
		</Alert>
	{/if}

	<Card.Root>
		<Card.Header>
			<Card.Title>Data Processing</Card.Title>
			<Card.Description>
				Configure how the daily ECOSTRESS data pipeline runs.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if loading}
				<p class="text-sm text-muted-foreground">Loading...</p>
			{:else}
				<div class="space-y-2">
					<Label for="delay">Data Delay (days)</Label>
					<Input
						id="delay"
						type="number"
						min="0"
						max="30"
						bind:value={dataDelayDays}
						class="max-w-[120px]"
					/>
					<p class="text-sm text-muted-foreground">
						How many days behind "today" the daily scheduled request targets.
						ECOSTRESS L2 LST data typically has ~1-2 days of processing latency,
						so a value of 2 avoids requesting data that hasn't been published yet.
					</p>
				</div>
			{/if}
		</Card.Content>
		<Card.Footer>
			<Button onclick={save} disabled={saving || loading}>
				{saving ? 'Saving...' : 'Save'}
			</Button>
		</Card.Footer>
	</Card.Root>
</div>
