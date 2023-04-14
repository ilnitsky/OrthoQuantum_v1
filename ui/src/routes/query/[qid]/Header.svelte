<script lang="ts">
	import TutorialToggleBtn from '$lib/components/tutorial/TutorialToggleBtn.svelte';
	import { Button, Col, Row } from 'sveltestrap';
</script>

<Row class="mt-4">
	<Col md="6">
		<h2>OrthoQuantum v2.0</h2>
	</Col>
	<Col md="6" class="d-none d-md-block">
		<hr />
	</Col>
</Row>
<Row>
	<Col md="6">
		<p>
			OrthoQuantum is a web-based tool for visualizing and studying phylogenetic presence/absence
			patterns of proteins and corresponding orthologous groups.
		</p>
		<p>
			OrthoQuantum allows the user to submit protein queries, inspect the output in graphic format
			and download the output in .csv format. The tool visualizes phylogenetic profiles utilizing a
			set of databases with orthology predictions.
		</p>
		<p>A BLAST search can be performed to complement the orthology data.</p>
		<div class="mb-3">
			<TutorialToggleBtn />
			<Button id="demo-btn" color="secondary">Load demo data</Button>
		</div>
	</Col>
	<Col md="6">
		<p>To perform a query:</p>
		<ol>
			<li>
				Select clades for which to display the correlation matrix and the phylogenetic profile.
				Choose organism scientific name or NCBI taxid.
			</li>
			<li>
				Input a list of query genes. Please use line breaks as a delimiter. OrthoQuantum accepts
				identifiers of proteins and genes, such as NCBI RefSeq, Genbank, UniProt ACs. InterPro,
				KEGG, OrthoDB orthogroup IDs also can be used.
			</li>
			<li>
				To perform BLAST search click on the ‘Enable BLAST’ button. The default parameters for
				BlastP search (E-value threshold, sequence identity, and query coverage) can be modified.
			</li>
		</ol>
		<p>Click "Submit" to see your results.</p>
	</Col>
</Row>

<style>
	hr {
		border-color: var(--bs-pink);
		border-width: 2px;
		margin-top: 2rem;
		margin-bottom: 0;
	}
	h2 {
		color: var(--bs-pink);
		white-space: nowrap;
	}
</style>
