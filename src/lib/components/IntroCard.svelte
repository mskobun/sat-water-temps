<script lang="ts">
	import { onMount } from 'svelte';
	import * as Card from '$lib/components/ui/card';
	import { Button } from '$lib/components/ui/button';
	import InfoIcon from '@lucide/svelte/icons/info';

	const STORAGE_KEY = 'sat-water-temps-intro-dismissed';

	let visible = $state(false);

	function dismiss() {
		visible = false;
	}

	function neverShowAgain() {
		localStorage.setItem(STORAGE_KEY, '1');
		visible = false;
	}

	onMount(() => {
		if (localStorage.getItem(STORAGE_KEY) !== '1') {
			visible = true;
		}
	});
</script>

{#if visible}
	<div
		class="fixed bottom-4 left-4 w-[min(400px)]"
		role="region"
		aria-label="About this project"
	>
		<Card.Root class="py-4 gap-4">
			<Card.Header class="flex flex-row items-start gap-2 pb-0">
				<div class="min-w-0 flex-1">
					<Card.Title class="text-lg">Satellite Water Temperature Monitoring</Card.Title>
					<Card.Description class="text-sm text-black mt-2">
						This map shows water bodies monitored with ECOSTRESS satellite data. Click a
						polygon to view temperature time series and thermal imagery. Data is updated
						periodically from NASA AppEEARS.
					</Card.Description>
				</div>
			</Card.Header>
			<Card.Footer class="flex flex-wrap gap-2">
				<Button size="sm" onclick={dismiss}>
					Dismiss
				</Button>
				<Button variant="outline" size="sm" onclick={neverShowAgain}>
					Don't show again
				</Button>
			</Card.Footer>
		</Card.Root>
	</div>
{/if}
