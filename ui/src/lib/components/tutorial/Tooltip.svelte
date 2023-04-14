<script lang="ts">
	import { Tooltip } from 'sveltestrap';
	import type { TooltipPlacement } from 'sveltestrap/src/Tooltip';
	export let target: string | HTMLElement;
	export let placement: TooltipPlacement;
	export let isOpen = false;
	import { showTutorial } from './store';
</script>

{#if $showTutorial}
	<Tooltip {isOpen} {target} {placement} container="body">
		<slot />
	</Tooltip>
{/if}
