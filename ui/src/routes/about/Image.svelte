<script lang="ts">
	import { createEventDispatcher } from 'svelte';

	export let src: string;
	const dispatch = createEventDispatcher();

	function select() {
		dispatch('imageSelected', src);
	}
</script>

<img
	{src}
	class="mx-auto inline-image"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	on:click={select}
	on:keypress={select}
/>

<style>
	.inline-image {
		width: 100%;
		max-width: 1100px;
	}
</style>
