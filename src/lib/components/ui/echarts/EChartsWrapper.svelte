<script lang="ts">
	import { onMount } from 'svelte';
	import * as echarts from 'echarts/core';
	import { LineChart } from 'echarts/charts';
	import { GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent } from 'echarts/components';
	import { SVGRenderer } from 'echarts/renderers';
	import type { ECharts } from 'echarts/core';
	import type { EChartsOption } from 'echarts';

	echarts.use([LineChart, GridComponent, TooltipComponent, DataZoomComponent, MarkLineComponent, SVGRenderer]);

	let {
		option,
		class: className = '',
		onInit
	}: {
		option: EChartsOption;
		class?: string;
		onInit?: (instance: ECharts) => void;
	} = $props();

	let container: HTMLDivElement;
	let chart: ECharts | undefined;

	onMount(() => {
		chart = echarts.init(container, undefined, { renderer: 'svg' });
		onInit?.(chart);

		const ro = new ResizeObserver(() => chart?.resize());
		ro.observe(container);

		return () => {
			ro.disconnect();
			chart?.dispose();
		};
	});

	$effect(() => {
		chart?.setOption(option, { notMerge: false });
	});
</script>

<div bind:this={container} class={className}></div>
