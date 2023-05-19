<script lang="ts">
	import { Card, CardBody } from 'sveltestrap';
	import screenshot1 from './screenshots/1.png';
	import screenshot2 from './screenshots/2.png';
	import screenshot3 from './screenshots/3.png';
	import screenshot4 from './screenshots/4.png';
	import screenshot5 from './screenshots/5.png';
	import screenshot6 from './screenshots/6.png';
	import screenshot7 from './screenshots/7.png';
	import screenshot8 from './screenshots/8.png';
	import screenshot9 from './screenshots/9.png';
	import screenshot10 from './screenshots/10.png';
	import { modal } from '$lib/components/ImageModal.svelte';
</script>

<h2 class="text-center mt-5 mb-5">OrthoQuantum v2.0</h2>
<Card class="mb-4 d-inline-block">
	<CardBody>
		<ul id="table-of-contents">
			<li>
				<a href="#item-1">About</a>
			</li>
			<li>
				<a href="#item-2">Quick Links to Databases</a>
			</li>
			<li>
				<a href="#item-3">Input query details</a>
			</li>
			<li>
				<a href="#item-4">Results</a>
			</li>
			<ul>
				<li>
					<a href="#item-5">Orthogroups table</a>
				</li>
				<li>
					<a href="#item-6">Correlation matrix</a>
				</li>
				<li>
					<a href="#item-7">Phylogenetic Profiles Visualization</a>
				</li>
				<li>
					<a href="#item-8">PantherDB Family/Subfamily Classification Phyloprofile</a>
				</li>
			</ul>
		</ul>
	</CardBody>
</Card>
<h3 id="item-1" class="mb-3">About</h3>
<p>
	<em>OrthoQuantum</em> is a web-based tool for visualizing and studying phylogenetic presence/absence
	patterns of proteins and corresponding orthologous groups.
</p>
<p>
	OrthoQuantum allows the user to submit protein queries, inspect the output in graphic format and
	download the output in .csv format. The tool visualizes phylogenetic profiles utilizing a set of
	databases with orthology predictions. The webserver mainly relies on orthology predictions from
	the OrthoDB database, which is leading in coverage of eukaryotic species, with 1,300 species that
	have a complete or nearly complete genome assembly and 37 million genes/proteins in the most
	recent update. Clustering of homologous sequences in OrthoDB occurs at the specified taxonomic
	level.
</p>
<p>
	A BLAST search can be performed to complement the orthology data. The user can submit the query in
	the front page by listing the UniProt identifiers or gene IDs in the input field.
</p>
<p>
	This website is free and open to all users and there is no login requirement. Multiple researchers
	can easily access the tool, which can display data from the set of over 1000 fully sequenced
	eukaryotic genomes and predicted orthologs at any given time.
</p>
<p>For brief descriptions, you can hover your mouse on fields to see the tooltip info messages.</p>
<img
	src={screenshot1}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	use:modal
/>
<h3 id="item-2" class="mb-3">Quick Links to Databases</h3>
<ul>
	<li>
		<a href="https://www.orthodb.org" target="_blank" rel="noreferrer">OrthoDB</a>
	</li>
	<li>
		<a href="http://www.pantherdb.org" target="_blank" rel="noreferrer">PANTHER</a>
	</li>
	<li>
		<a href="https://www.ncbi.nlm.nih.gov" target="_blank" rel="noreferrer">NCBI</a>
	</li>
</ul>
<h3 id="item-3" class="mb-3">Input query details</h3>
<p>
	Available eukaryotic species are divided into taxonomic categories based on “levels of orthology”
	in OrthoDB: Eukaryota, Metazoa, Viridiplantae, Vertebrata, Aves, Actinopterygii, Fungi, Protista.
	Users can select sets of target species by using the series of presented drop down menus. For the
	Eukaryota level there is an option to continue with a compact set of species with a good quality
	of genome assembly, or with a full set of species that may provide better resolution for
	conservation patterns ( ‘Eukaryota (compact)’ - 120 species, ‘Eukaryota (all species)’ - 1200
	species). Once the source species have been selected, the user can input the sequence IDs in the
	textbox. Queries can be formulated using synonymous gene/protein names, identifiers, keywords.
	KEGG Pathway and GO annotations are also available.
</p>
<img
	src={screenshot2}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	use:modal
/>
<p>
	For orthogroups that have missing elements, a search for potential homologs can be conducted
	against the NCBI non-redundant protein sequence database (nr) using the BlastP algorithm to
	complement the data from OrthoDB. In this step, users can choose three parameters: E-value
	threshold, Sequence Identity and Query coverage. Note that OrthoQuantum web-server does not
	attempt to properly delineate orthologous relationships with BlastP searches, it aims to fill gaps
	in phylogenetic profiles and demonstrate distribution of homologs of input proteins.
</p>
<img
	src={screenshot3}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<p>
	If a certain entry yields multiple matching orthogroups the user is presented with a table that
	contains selectable rows with orthogroups. By clicking the 'Submit' button on the bottom of the
	page, users then proceed to the visualization section. The query can be canceled with ‘Cancel’
	button.
</p>
<img
	src={screenshot4}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<p>
	Execute the query by clicking the 'Search' button. The query can be cancelled by clicking
	’Cancel’.
</p>
<h3 id="item-4" class="mb-3">Results</h3>
<h5 id="item-5">Orthogroups table</h5>
<p>
	A table of information related to each orthogroup is loaded that links query names with OrthoDB
	orthogroup identifiers and contains some other useful information about the orthogroups.
	Genes/proteins that appear in the same group are separated by commas. To see the FASTA-formatted
	amino acid sequences present in the orthogroup click on the OG label (for example, ‘215502at2759’
	for the PIWI proteins orthogroup). ‘EvolRate’ stands for ‘Evolutionary rate’ annotation from
	OrthoDB. It reflects relative sequence conservation among orthologous genes. The numerical data in
	the columns has filtering capabilities with operators such as &gt;, &lt;, =.
</p>
<img
	src={screenshot5}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<h5 id="item-6" class="mb-3 mt-5">Correlation matrix</h5>
<p>
	The table contains ranked correlations between each pair of proteins with their percentile. The
	graphic representation of the results is a correlation matrix. The colors on the matrix reflect
	the values of the Pearson correlation coefficient. On both axes, a color bar is added
	corresponding to the percentage of homologs present in species: black corresponds to a high
	percentage and bright red corresponds to a low percentage.
</p>
<img
	src={screenshot6}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<h5 id="item-7">Phylogenetic Profiles Visualization</h5>
<p>
	On the bottom of the page a phylogenetic profile heatmap is constructed. The columns show the
	orthogroups, with the same name as the query protein name. The order of query sequences is defined
	by the hierarchical clustering. Rows of the heatmap show the eukaryotic genomes, major taxa on the
	species tree are labeled with different colors. Mousing over an individual tile in the heatmap
	reveals the query species, gene names of both the query and orthologous genes. Clicking on it pins
	the tooltip and reveals detailed information, including the link to FASTA formatted sequences.
</p>
<img
	src={screenshot7}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<h5 id="item-8">PantherDB Family/Subfamily Classification Phyloprofile</h5>
<p>
	Clicking on the Gene Names generates a phylogenetic profile of subfamilies of homologous proteins
	in the new browser tab. For example, PIWIL1 gene belongs to PIWI/Aubergine family and has more
	than 30 related homologous subfamilies. This graph helps to analyze profiles of orthologous groups
	that contain multiple paralogous genes.
</p>
<img
	src={screenshot8}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<p>
	BlastP hits are visualized on the same phyloprofile plot with OrthoDB orthologs to indicate
	possible presence of proteins for each orthogroup that has missing elements. BLAST findings are
	shown in purple, OrthoDB orthology assignments are shown in blue. We use E-value as the criteria
	to save the identifiers of best scoring hit. The IDs of findings can be downloaded in .csv format
	by clicking ‘Download csv’ button in the top right corner of phyloprofile plot. The heatmap figure
	can be downloaded as a PNG file by selecting the 'Download Image' button.
</p>
<img
	src={screenshot9}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>
<p>
	Phyloprofile charts are rendered using SVG model in PhyD3, which is easy to use, but has limited
	performance. In our tests browsers can typically handle around 1000 orthogroup entries. The user
	can change the number of displayed proteins to improve performance. In this case, the proteins
	with the highest absolute values of correlation coefficient will be displayed.
</p>
<img
	src={screenshot10}
	class="mx-auto inline-image cursor-pointer"
	alt="Interface screenshot"
	loading="lazy"
	decoding="async"
	use:modal
/>

<style>
	h2,
	h3,
	h5 {
		color: var(--bs-pink);
		white-space: nowrap;
		/* Height of the navbar */
		scroll-margin-top: 3.5rem;
	}
	#table-of-contents {
		padding-left: 1rem;
	}
	img {
		width: 100%;
		max-width: 1100px;
	}
</style>
