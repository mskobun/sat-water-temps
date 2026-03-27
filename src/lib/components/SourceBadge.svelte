<script lang="ts">
	import { sourceLabel } from '$lib/date-utils';

	let { source, class: className = '' }: { source: string; class?: string } = $props();

	const colors = $derived(
		source === 'landsat'
			? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
			: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300'
	);
</script>

<span
	class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium {colors} {className}"
>
	{sourceLabel(source)}
</span>
