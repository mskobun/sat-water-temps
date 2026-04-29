<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { Alert, AlertDescription } from '$lib/components/ui/alert';

	let dataDelayDays = $state('2');
	let catchupEnabled = $state(true);
	let catchupOverlapDays = $state('3');
	let catchupMaxDays = $state('21');
	let landsatWaterMask = $state<'native' | 'opera_dswx'>('native');
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
			if (settings.catchup_enabled !== undefined) {
				catchupEnabled = settings.catchup_enabled === 'true';
			}
			if (settings.catchup_overlap_days !== undefined) {
				catchupOverlapDays = settings.catchup_overlap_days;
			}
			if (settings.catchup_max_days !== undefined) {
				catchupMaxDays = settings.catchup_max_days;
			}
			if (settings.landsat_water_mask !== undefined) {
				landsatWaterMask = settings.landsat_water_mask;
			}
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load settings';
		} finally {
			loading = false;
		}
	});

	async function saveSetting(key: string, value: string) {
		const res = await fetch('/api/admin/settings', {
			method: 'PUT',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ key, value })
		});
		if (!res.ok) {
			const body = await res.json().catch(() => ({}));
			throw new Error(body.error || `Failed to save ${key}`);
		}
	}

	async function save() {
		error = '';
		success = '';
		const delayVal = parseInt(dataDelayDays);
		const overlapVal = parseInt(catchupOverlapDays);
		const maxVal = parseInt(catchupMaxDays);
		if (isNaN(delayVal) || delayVal < 0 || delayVal > 30) {
			error = 'Delay must be a number between 0 and 30';
			return;
		}
		if (isNaN(overlapVal) || overlapVal < 0 || overlapVal > 30) {
			error = 'Overlap must be a number between 0 and 30';
			return;
		}
		if (isNaN(maxVal) || maxVal < 1 || maxVal > 90) {
			error = 'Maximum catch-up window must be a number between 1 and 90';
			return;
		}
		saving = true;
		try {
			await Promise.all([
				saveSetting('data_delay_days', String(delayVal)),
				saveSetting('catchup_enabled', String(catchupEnabled)),
				saveSetting('catchup_overlap_days', String(overlapVal)),
				saveSetting('catchup_max_days', String(maxVal)),
				saveSetting('landsat_water_mask', landsatWaterMask)
			]);
			success = 'Settings saved';
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

	<Card.Root class="mb-6">
		<Card.Header>
			<Card.Title>Processing Settings</Card.Title>
			<Card.Description>
				Default settings applied to all scheduled processing runs. Individual manual triggers can
				override these per run.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if loading}
				<p class="text-sm text-muted-foreground">Loading...</p>
			{:else}
				<div class="space-y-4">
					<div class="space-y-2">
						<p class="text-sm font-medium">Landsat water mask</p>
						<div class="flex gap-1 rounded-md border p-1 w-fit">
							<button
								class="rounded px-3 py-1.5 text-sm font-medium transition-colors {landsatWaterMask === 'native' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
								onclick={() => { landsatWaterMask = 'native'; }}
							>Native (QA_PIXEL)</button>
							<button
								class="rounded px-3 py-1.5 text-sm font-medium transition-colors {landsatWaterMask === 'opera_dswx' ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'}"
								onclick={() => { landsatWaterMask = 'opera_dswx'; }}
							>OPERA DSWx-HLS</button>
						</div>
						<p class="text-sm text-muted-foreground">
							Native uses the QA_PIXEL bit 7 CFMask water flag co-derived with each scene.
							OPERA DSWx-HLS is a purpose-built 30m water classification from Harmonized Landsat
							Sentinel-2, which yields fewer but more confident water pixels.
						</p>
					</div>
				</div>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header>
			<Card.Title>Data Processing</Card.Title>
			<Card.Description>
				Configure how scheduled satellite ingestion catches up when source catalogs publish new data.
			</Card.Description>
		</Card.Header>
		<Card.Content>
			{#if loading}
				<p class="text-sm text-muted-foreground">Loading...</p>
			{:else}
				<div class="space-y-6">
					<div class="space-y-2">
						<div class="flex items-center gap-3">
							<input
								id="catchup-enabled"
								type="checkbox"
								bind:checked={catchupEnabled}
								class="size-4 rounded border-input"
							/>
							<Label for="catchup-enabled">Enable daily catch-up scans</Label>
						</div>
						<p class="text-sm text-muted-foreground">
							When enabled, ECOSTRESS and Landsat daily runs scan from recent processed data
							through the latest catalog date for monitored areas, then skip completed observations.
						</p>
					</div>

					<div class="space-y-2">
						<Label for="overlap">Catch-up Overlap (days)</Label>
						<Input
							id="overlap"
							type="number"
							min="0"
							max="30"
							bind:value={catchupOverlapDays}
							class="max-w-[120px]"
						/>
						<p class="text-sm text-muted-foreground">
							How many already-processed days to re-check so partial failures can be retried.
							Completed feature/day observations are skipped before SQS.
						</p>
					</div>

					<div class="space-y-2">
						<Label for="max-catchup">Maximum Automatic Catch-up Window (days)</Label>
						<Input
							id="max-catchup"
							type="number"
							min="1"
							max="90"
							bind:value={catchupMaxDays}
							class="max-w-[120px]"
						/>
						<p class="text-sm text-muted-foreground">
							Limits how many catalog days one scheduled run scans. Larger backlogs continue on
							later runs or can be handled with manual backfill.
						</p>
					</div>

					<div class="space-y-2 border-t pt-6">
						<Label for="delay">Legacy Data Delay (days)</Label>
						<Input
							id="delay"
							type="number"
							min="0"
							max="30"
							bind:value={dataDelayDays}
							class="max-w-[120px]"
						/>
						<p class="text-sm text-muted-foreground">
							Used only as a fallback when catch-up is disabled or the source catalog latest date
							cannot be resolved.
						</p>
					</div>
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
