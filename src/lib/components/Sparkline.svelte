<script lang="ts">
	import { LineChart } from 'layerchart';

	type Props = {
		values: number[];
		width?: number;
		height?: number;
		class?: string;
	};

	let { values, width = 80, height = 20, class: className = '' }: Props = $props();

	const data = $derived(values.map((v, i) => ({ i, v })));
	const hasSeries = $derived(values.length >= 2);
</script>

{#if hasSeries}
	<div class={`inline-block text-muted-foreground ${className}`} style:width="{width}px" style:height="{height}px">
		<LineChart
			{data}
			x="i"
			y="v"
			axis={false}
			grid={false}
			legend={false}
			tooltip={false}
			padding={{ top: 2, right: 2, bottom: 2, left: 2 }}
			points={false}
			series={[{ key: 'v', color: 'currentColor' }]}
			props={{ spline: { strokeWidth: 1.5 } }}
		/>
	</div>
{:else}
	<span
		class={`inline-flex items-center justify-center text-muted-foreground/50 text-xs ${className}`}
		style:width="{width}px"
		style:height="{height}px"
		aria-label="Not enough data for trend"
	>
		—
	</span>
{/if}
