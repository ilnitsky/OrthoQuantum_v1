<script lang="ts">
	import { Button, Col, Row, InputGroup, Label, Input, Alert, InputGroupText } from 'sveltestrap';
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
	import { setStore } from './store';
	import { keyToStore, toStore } from '$lib/sseStore';
	import { onMount } from 'svelte';
	import { addAlert, updateAlert } from "$lib/components/Alerts.svelte";


	export let data: PageData;
	const isNew = $page.params.qid === "new";
	const store = setStore(data, $page.url, isNew);

	let collection = [
		{ value: "1", label: 'one' },
		{ value: "2", label: 'two' },
		{ value: "3", label: 'three' }
	];

	let title: typeof store.input.title;
	let query: typeof store.input.query;
	let blastEnabled: typeof store.input.blast.enabled;
	let max_prots: typeof store.input.max_prots;
	toStore(store.input).subscribe((input) => {
		({
			title,
			query,
			blast: {enabled: blastEnabled},
			max_prots
		} = input)
	});

	let taxon_id: (typeof collection[number]) | undefined;
	keyToStore(store.input, 'taxon_id').subscribe((v)=>{
		taxon_id = collection.find((it)=>it.value == v);
	});

	// function beforeunload(e:BeforeUnloadEvent) {
	// 	if (isNew){
	// 		e.preventDefault();
	// 		// no string on modern browsers
	// 		return (e.returnValue = "The request wasn't submitted; you'll loose all entered data if you leave the page");
	// 	}
	// }
</script>

<!-- <svelte:window on:beforeunload={beforeunload}/> -->

<Header />
<Title bind:title />
<Select
	id="tax-dropdown-container"
	items={collection}
	bind:value={taxon_id}
	placeholder="Select a taxon (level of orthology)"
	class="mt-2 form-control"
	--border-hover="1px solid #ced4da"
	--border-focused="1px solid #f4aa90"
	--border-radius="0.375rem"
	--item-hover-bg="#fcf2ed"
	--item-is-active-bg="#fcd1bb"
	--item-is-active-color="#333"
/>

<Tooltip target="tax-dropdown-container" placement="bottom">
	Select level of orthology. Clustering of homologous sequences in OrthoDB occurs at the specified
	taxonomic level.
</Tooltip>

<TaxidSelect />

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

<BlastOptions bind:blastEnabled />
<Alert id="missing_prot_alert" class="alert-warning">Unknown proteins: qwe</Alert>

<MultiOrthoTable />

<!-- table -->
<ProgressBar />

<div class="d-flex align-items-center mb-3">
	<Button id="submit-button" color="primary" class="d-block">Submit</Button>
	<div class="d-flex ms-4 align-items-center">
		<Input type="checkbox" id="extra_auto_select" class="d-block" />
		<Label for="extra_auto_select" class="d-block mb-0">
			Automatically select<br />the most relevant orthogroup
		</Label>
	</div>
	<Button id="cancel-button" color="danger" outline class="ms-auto">Cancel</Button>
</div>
<ProteinTable />

<Alert id="missing_uniprot_alert" class="alert-warning mt-3">TODO: some uniprot are missing</Alert>
<!-- vis_progress_bar -->
<ProgressBar />
<Heatmap />
<PhyloPlot url="/tree.xml" taskid="" leafCound={239} />

<style>
	:global(.svelte-select.focused){
		box-shadow: 0 0 0 0.25rem rgb(233 84 32 / 25%);
	}
</style>