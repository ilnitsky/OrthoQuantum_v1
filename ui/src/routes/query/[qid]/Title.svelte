<script lang="ts">
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';
	import { getStore } from './store';

	export let title: string;
	const store = getStore();
	let editing = false;

	let ref: HTMLInputElement;
	let height = 48;

	function commit() {
		if (!editing) {
			return;
		}
		editing = false;
		title = title.trim();
		if (!title) {
			title = store.input.title;
			return;
		}
		store.input.title = title;
		if ($page.params.qid === 'new') {
			return;
		}
		fetch($page.url, {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({
				title
			})
		})
			.then((r) => {
				if (!r.ok) {
					throw new Error(`Request not ok: ${r.status} ${r.statusText}`);
				}
				return r.json();
			})
			.then((json) => {
				if (!json.ok) {
					throw new Error(`JSON not ok: ${json}`);
				}
			})
			.catch((err) => {
				console.error('Title update failed:', err);
				store.input.title = store.db_input.title;
			});
	}

	function focus(el: HTMLInputElement) {
		el.focus();
		el.select();
	}
</script>

<div class="mb-2">
	{#if editing}
		<input
			class="form-control text-center w-100 m-0"
			type="text"
			use:focus
			bind:this={ref}
			bind:value={title}
			on:blur={commit}
			on:change={commit}
			on:keydown={(e) => {
				if (e.code === 'Escape') {
					e.preventDefault();
					title = '';
					commit();
				}
			}}
			style:--title-height={`${height}px`}
		/>
	{:else}
		<h1
			id="request-title"
			class="link-primary text-center w-100 m-0"
			role="button"
			tabindex="0"
			on:click={() => (editing = true)}
			on:keydown={(e) => {
				if (e.code === 'Space') {
					e.preventDefault();
					editing = true;
				}
			}}
			bind:clientHeight={height}
		>
			{title}
		</h1>
		<Tooltip target="request-title" placement="bottom">Click to edit</Tooltip>
	{/if}
</div>

<style>
	h1 {
		word-wrap: break-word;
	}

	input {
		height: var(--title-height);
		font-size: 1.375rem; /* half of h1 fontsize */
		box-sizing: border-box;
	}
</style>
