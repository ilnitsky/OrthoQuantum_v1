<script lang="ts">
	import { Tooltip } from 'sveltestrap';
	import type { TooltipPlacement } from 'sveltestrap/src/Tooltip';
	import { showTutorial } from './TutorialToggleBtn.svelte';
	export let target: string | HTMLElement;
	export let placement: TooltipPlacement;
	export let isOpen = false;
</script>

{#if $showTutorial}
	<Tooltip {isOpen} {target} {placement} container="body">
		<slot />
	</Tooltip>
{/if}
