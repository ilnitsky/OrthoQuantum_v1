<script>
  import {
    Button,
    Col,
    Row,
    InputGroup,
    Label,
    Input,
    Progress,
    Collapse,
    Card,
    CardBody,
    Alert,
    InputGroupText,
  } from "sveltestrap";
  import Select from "svelte-select";

  import PageTitle from "./PageTitle.svelte";
  import Title from "./Title.svelte";
  import Tooltip from "./tutorial/Tooltip.svelte";
  import TutorialToggleBtn from "./tutorial/TutorialToggleBtn.svelte";
  import TaxidSelect from "./TaxidSelect.svelte";
  import BlastOptions from "./BlastOptions.svelte";
  import ProgressBar from "./components/ProgressBar.svelte";
  import MultiOrthoTable from "./MultiOrthoTable.svelte";
    import ProteinTable from "./ProteinTable.svelte";
    import Heatmap from "./Heatmap.svelte";
    import PhyloPlot from "./PhyloPlot.svelte";


  let collection = [
    { value: 1, label: "one" },
    { value: 2, label: "two" },
    { value: 3, label: "three" },
  ];

  let blastEnabled = false;
</script>

<!--
  <Store id="task_id" data="123"/>
  -->
<!--
  <Store id="connection_id"/>
  -->
<!--
  <Store id="force_update_until" data="0"/>
  -->
<!--
  <Store id="version"/>
  -->
<!--
  <Store id="data_submit_error" data="False"/>
  -->
<!--
  <Store id="trigger_csv_download" data="0"/>
  -->
<!--
  <Store id="trigger_csv_download_2" data="0"/>
  -->
<!--
  <Store id="trigger_csv_download_refresh" data="0"/>
  -->
<!-- <a
    id="csvdownload_done_link"
    href="/files/123/tree.csv"
    download="tree.csv"
    class="d-none"
  ></a> -->
<!--
  <Interval id="progress_updater" interval="500" disabled="True"/>
  -->
<PageTitle />

<Row class="justify-content-center">
  <Col md="5" lg="4">
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

    <TutorialToggleBtn />
    <Button id="demo-btn" color="secondary">Load demo data</Button>
  </Col>

  <Col md="5" lg="4">
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
  <Col md="10" lg="8" class=" mt-3">
    <Title />
    <Select
      id="tax-dropdown-container"
      items={collection}
      placeholder="Select a taxon (level of orthology)"
    />
    <Tooltip target="tax-dropdown-container" placement="bottom">
      Select level of orthology. Clustering of homologous sequences in OrthoDB occurs at the
      specified taxonomic level.
    </Tooltip>

    <TaxidSelect />

    <Input
      id="uniprotAC"
      placeholder="Input a list of query gene/protein/orthogroup IDs or keywords ..."
      value=""
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
          For orthogroups that have missing elements, an additional search for potential homologs
          will be conducted against the NCBI nr database using the blastp algorithm. Percent
          identity and query coverage parameters can be changed.
        </Tooltip>
      </Col>
      <Col class="col-auto">
        <InputGroup>
          <InputGroupText>Max proteins on the tree</InputGroupText>
          <Input value="600" id="max-proteins" min="5" type="number" style="width: 6rem;" />
        </InputGroup>
      </Col>
    </Row>
    <Collapse id="blast-options" isOpen={blastEnabled}>
      <BlastOptions />
    </Collapse>
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
    <Heatmap/>
    <PhyloPlot/>
  </Col>
</Row>

