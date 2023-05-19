<script lang="ts">
	import { Button, Col, Row, InputGroup, Label, Input, InputGroupText, Spinner } from 'sveltestrap';
	import Select from 'svelte-select';
	import Title from './Title.svelte';
	import Tooltip from '$lib/components/tutorial/Tooltip.svelte';
	import ProgressBar from '$lib/components/ProgressBar.svelte';
	import TaxidSelect from './TaxidSelect.svelte';
	import BlastOptions from './BlastOptions.svelte';
	import MultiOrthoTable from './MultiOrthoTable.svelte';
	import ProteinTable from './ProteinTable.svelte';
	import Heatmap from './Heatmap.svelte';
	import PhyloPlot from './PhyloPlot.svelte';
	import Header from './Header.svelte';

	import type { PageData } from './$types';
	import { page } from '$app/stores';
	import { storeKey } from './store';
	import type { Query, SubmitQuery, Taxon } from '$lib/dbTypes';
	import { onMount, setContext, tick } from 'svelte';
	import { afterNavigate, beforeNavigate } from '$app/navigation';
	import { browser, dev } from '$app/environment';
	import { serializeInput } from '$lib/serde/client';
	import { fetchHandle } from '$lib/fetchUtil';
	import { immerDeriveMap, immerStore, immerSubKey, type Patch } from '$lib/immerUtil';
	import UnknownProts from './UnknownProts.svelte';

	export let data: PageData;

	const store = (function () {
		const store = immerStore(data.query, true);
		setContext(storeKey, store);

		let pageReady = true;
		let sse: EventSource | null = null;
		let unsubTimer: ReturnType<typeof setTimeout> | undefined;

		function unsubscribe() {
			clearTimeout(unsubTimer);
			console.log('unsubscribe');
			if (sse) {
				sse.close();
				sse = null;
			}
		}

		function onMessage(ev: MessageEvent<string>) {
			console.log('onMessage');

			const update = JSON.parse(ev.data) as Patch[];
			store.applyPatches(update);
			console.log('onMessage', update, store);
			data.ts = ev.lastEventId;
		}
		function onFullData(ev: MessageEvent<string>) {
			console.log('onFullData');
			store.set(JSON.parse(ev.data) as Query);
			data.ts = ev.lastEventId;
		}
		function subscribe() {
			if (!browser || !pageReady || sse) {
				return;
			}
			const qid = $page.params.qid;
			if (!qid || qid === 'new') {
				return;
			}
			console.log('subscribe');
			const url = new URL($page.url);
			url.search = `?sse=${data.ts}`;
			sse = new EventSource(url, { withCredentials: true });
			sse.addEventListener('message', onMessage);
			sse.addEventListener('fullData', onFullData);
			sse.onopen = (e) => {
				console.log('SSE open', e);
			};
			sse.onerror = (e) => {
				console.log('SSE error', e);
			};
		}
		function onvisibilitychange() {
			clearTimeout(unsubTimer);
			switch (document.visibilityState) {
				case 'visible':
					subscribe();
					break;
				case 'hidden':
					// unsubscribe if the page is hidden for a bit, since SSE have strict limits on open connections
					if (sse) {
						unsubTimer = setTimeout(unsubscribe, 30 * 1000);
					}
					break;
			}
		}
		beforeNavigate((nav) => {
			console.log('beforeNavigate');
			const s_input = store.get().input;
			if (
				s_input.query !== query ||
				s_input.species !== species ||
				s_input.taxon_id !== taxon?.id ||
				multi_ortho_selection.size !== s_input.multi_ortho_selection.length ||
				!s_input.multi_ortho_selection.every(multi_ortho_selection.has.bind(multi_ortho_selection))
			) {
				console.log(s_input.query, query);
				console.log(s_input.species, species);
				console.log(s_input.taxon_id, taxon?.id);
				console.log(s_input.multi_ortho_selection, multi_ortho_selection);
				if (
					!dev &&
					!submitting &&
					!confirm(
						"Query wasn't submitted; you will loose all entered data if you leave the page. Proceed?"
					)
				) {
					nav.cancel();
					return;
				}
			}
			unsubscribe();
			pageReady = false;
		});
		afterNavigate(() => {
			console.log('afterNavigate');
			unsubscribe();
			// if this is called by server navigation - always apply diffs
			if (!(browser && pageReady)) {
				console.log(data.query);
				store.set(data.query);
				pageReady = true;
			}
			subscribe();
		});

		onMount(() => {
			document.addEventListener('visibilitychange', onvisibilitychange);
			return () => {
				document.removeEventListener('visibilitychange', onvisibilitychange);
			};
		});

		return store;
	})();

	let title: Query['title'];
	let query: Query['input']['query'];
	let species: Query['input']['species'];
	let max_prots: Query['input']['max_prots'];
	let blastEnabled: Query['input']['blast']['enabled'];
	let evalue: Query['input']['blast']['evalue'];
	let pident: Query['input']['blast']['pident'];
	let qcov: Query['input']['blast']['qcov'];
	let auto_select: Query['input']['auto_select'];
	let multi_ortho_selection: Set<string>;

	immerSubKey(
		store,
		(store) => store.title,
		(new_title) => {
			title = new_title;
		}
	);

	immerSubKey(
		store,
		(store) => store.input,
		(input) => {
			({
				query,
				blast: { enabled: blastEnabled, evalue, pident, qcov },
				max_prots,
				auto_select,
			} = input);
		}
	);

	immerSubKey(
		store,
		(store) => store.input.multi_ortho_selection,
		(sel) => {
			multi_ortho_selection = new Set(sel);
		}
	);

	//... rework
	let rid: string | undefined;

	immerSubKey(
		store,
		(store) => store.output,
		(output) => {
			rid = output.rid;
		}
	);

	let taxon: Taxon | undefined;
	immerSubKey(
		store,
		(store) => store.input.taxon_id,
		(tax) => {
			taxon = data.taxons.find((it) => it.id == tax);
		}
	);

	// less manual error handling requires significant rearchitecturing
	let submitting = false;
	let show_errors = false;
	$: taxon_invalid = typeof taxon == 'undefined';
	$: species_invalid = typeof species == 'undefined';

	function getCurrentInput(): SubmitQuery {
		return {
			title,
			input: {
				query,
				taxon_id: taxon?.id,
				species,
				blast: {
					enabled: blastEnabled,
					evalue,
					pident,
					qcov,
				},
				max_prots,
				auto_select,
				multi_ortho_selection: Array.from(multi_ortho_selection),
			},
		};
	}
	function submit() {
		if (taxon_invalid || species_invalid) {
			show_errors = true;
			tick().then(() => {
				document
					.querySelector('.invalid-feedback.d-block')
					?.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
			});
			return;
		}
		show_errors = false;
		submitting = true;
		fetchHandle('send data', $page.url, {
			method: 'POST',
			body: serializeInput(getCurrentInput()),
			headers: [['content-type', 'application/json']],
		}).finally(() => {
			submitting = false;
		});
	}
	let canceling = false;
	function cancel() {
		canceling = true;
		console.log('cancelled');
	}
	$: if (!rid) {
		canceling = false;
	}
</script>

<Header />

<Title bind:title />
<Select
	id="tax-dropdown-container"
	items={data.taxons}
	itemId="id"
	label="name"
	bind:value={taxon}
	placeholder="Select a taxon (level of orthology)"
	class="mt-2 form-control"
	--border-hover="1px solid #ced4da"
	--border-focused="1px solid #f4aa90"
	--border-radius="0.375rem"
	--item-hover-bg="#fcf2ed"
	--item-is-active-bg="#fcd1bb"
	--item-is-active-color="#333"
/>
<div class="invalid-feedback" class:d-block={show_errors && taxon_invalid}>
	Please choose the level of orthology
</div>
<Tooltip target="tax-dropdown-container" placement="bottom">
	Select level of orthology. Clustering of homologous sequences in OrthoDB occurs at the specified
	taxonomic level.
</Tooltip>

<TaxidSelect {taxon} bind:species initSpecies={data.species} />
<div class="invalid-feedback" class:d-block={show_errors && species_invalid}>
	Please choose the species
</div>

<Input
	id="uniprotAC"
	placeholder="Input a list of query gene/protein/orthogroup IDs or keywords ..."
	bind:value={query}
	class="mt-2"
	rows={10}
	style="width: 100%;"
	type="textarea"
/>

<Row class="my-3 justify-content-between">
	<Col class="col-auto">
		<Button
			id="blast-button"
			color="success"
			tabindex={0}
			outline={!blastEnabled}
			class="shadow-none"
			on:click={() => {
				blastEnabled = !blastEnabled;
			}}
		>
			{#if blastEnabled}Disable{:else}Enable{/if} BLAST
		</Button>
		<Tooltip target="blast-button" placement="right">
			For orthogroups that have missing elements, an additional search for potential homologs will
			be conducted against the NCBI nr database using the blastp algorithm. Percent identity and
			query coverage parameters can be changed.
		</Tooltip>
	</Col>
	<Col class="col-auto">
		<InputGroup>
			<InputGroupText>Max proteins on the tree</InputGroupText>
			<Input bind:value={max_prots} id="max-proteins" min={5} type="number" style="width: 9ch;" />
		</InputGroup>
	</Col>
</Row>

<BlastOptions bind:blastEnabled bind:evalue bind:pident bind:qcov />
<UnknownProts
	prompt="Unknown proteins: "
	data={immerDeriveMap(
		store,
		(s) => s.output.unknown_proteins,
		(v) => v ?? []
	)}
/>
<MultiOrthoTable bind:selection={multi_ortho_selection} />

<!-- table -->
<ProgressBar />

<div class="d-flex align-items-center mb-3">
	<Button
		id="submit-button"
		color="primary"
		class="d-block"
		disabled={submitting}
		on:click={submit}
	>
		{#if submitting}
			<Spinner size="sm" /> Submitting
		{:else}
			Submit
		{/if}
	</Button>
	<div class="d-flex ms-4 align-items-center">
		<Input type="checkbox" id="extra_auto_select" class="d-block" bind:checked={auto_select} />
		<Label for="extra_auto_select" class="d-block mb-0">
			Automatically select<br />the most relevant orthogroup
		</Label>
	</div>
	{#if rid}
		<Button
			id="cancel-button"
			color="danger"
			outline
			class="ms-auto"
			on:click={cancel}
			disabled={canceling}
		>
			{#if canceling}
				<Spinner size="sm" /> Cancelling
			{:else}
				Cancel
			{/if}
		</Button>
	{/if}
</div>

<ProteinTable />
<!-- mt-3 -->
<UnknownProts
	prompt="Uniprot ACs not found for: "
	data={immerDeriveMap(
		store,
		(store) => store.output.missing_uniprot,
		(v) => v ?? []
	)}
/>

<!-- vis_progress_bar -->
<ProgressBar />
<Heatmap />
<PhyloPlot url="/tree.xml" taskid="" leafCount={239} />

<style>
	:global(.svelte-select.focused) {
		box-shadow: 0 0 0 0.25rem rgb(233 84 32 / 25%);
	}
</style>
