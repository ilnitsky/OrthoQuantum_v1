<script lang="ts" context="module">
	import { writable } from 'svelte/store';

	export const showTutorial = writable(false);
</script>

<script lang="ts">
	import { Button } from 'sveltestrap';
	// import { showTutorial } from './store';
	import Tooltip from './Tooltip.svelte';
	import { page } from '$app/stores';

	const initVal = $page.data['showTutorial'];
	showTutorial.set(typeof initVal === 'boolean' && initVal);

	// for updating tooltip over the toggle button immediatly,
	// (otherwise requires re-hovering over the button to trigger)
	let explicitShow = false;

	function toggleTutorial() {
		showTutorial.update((val) => {
			val = !val;
			explicitShow = val;
			fetch('/api/setTutorial', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				body: JSON.stringify({
					showTutorial: val
				})
			}).catch((e) => {
				console.log('Failed to set showTutorial on server:', e);
			});
			return val;
		});
	}
</script>

<Button
	id="showTutorialBtn"
	color="primary"
	type="button"
	active={$showTutorial}
	on:click={toggleTutorial}
>
	{#if $showTutorial}Hide{:else}Show{/if} descriptions
</Button>

<Tooltip target="showTutorialBtn" placement="bottom" isOpen={explicitShow}>
	Information would be displayed while hovering over an element
</Tooltip>
