<script lang="ts">
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';

	export let title: string;
	let innerTitle: string;
	let editing = false;

	function serverTitleUpdate(newTitle: string) {
		if (!editing) {
			innerTitle = newTitle;
		}
	}
	$: serverTitleUpdate(title);

	let ref: HTMLInputElement;
	let height = 48;

	function commit() {
		if (!editing) {
			return;
		}
		editing = false;
		innerTitle = innerTitle.trim();
		if (!innerTitle) {
			innerTitle = title;
			return;
		}
		title = innerTitle;
		const qid = $page.params.qid;
		if (qid === 'new') {
			return;
		}
		fetch('/api/setTitle', {
			method: 'POST',
			headers: [['content-type', 'application/json']],
			body: JSON.stringify({
				title,
				qid,
			}),
		})
			.then((r) => r.json())
			.then((json) => {
				if (!json.ok) {
					throw json.message ?? 'Unknown error';
				}
			})
			.catch((err) => {
				console.error('Title update failed:', err);
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
			bind:value={innerTitle}
			on:blur={commit}
			on:change={commit}
			on:keydown={(e) => {
				if (e.code === 'Escape') {
					e.preventDefault();
					innerTitle = '';
					commit();
				}
			}}
			style:--title-height={`${height}px`}
		/>
	{:else}
		<div
			id="request-title"
			class="link-primary text-center w-100 m-0"
			role="button"
			tabindex="0"
			on:click={() => (editing = true)}
			on:keydown={(e) => {
				if (e.code === 'Space' || e.code === 'Enter') {
					e.preventDefault();
					editing = true;
				}
			}}
		>
			<h1 bind:clientHeight={height}>
				{title}
			</h1>
		</div>
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
