<script lang="ts">
  import { Alert, Card, CardBody, Collapse } from "sveltestrap";
  import Paginator from "./components/Paginator.svelte";
  import Tooltip from "./tutorial/Tooltip.svelte";

  let table = [
    {
      selected: true,
      query: "SMPDL3A1",
      orthodb_id: "1574805at7742",
      gene_name: "SMPDL3A",
      description: "sphingomyelin phosphodiesterase acid like 3A",
      gene_count: "474",
      species_count: "462",
    },
    {
      selected: false,
      query: "SMPDL3A2",
      orthodb_id: "1574805at7742",
      gene_name: "SMPDL3A",
      description: "sphingomyelin phosphodiesterase acid like 3A",
      gene_count: "474",
      species_count: "462",
    },
  ];
  $: {
    console.debug(table);
  }

  let pageSize = 1; // TODO: 40
  let page = 1;
  $: maxPage = Math.ceil(table.length / pageSize);
  $: tableSlice = table.slice((page - 1) * pageSize, Math.min(table.length, page * pageSize));
</script>

<div id="prot_table_container" class="table-responsive">
  <table class="table table-bordered table-sm">
    <thead>
      <tr>
        <th scope="col">OG label</th>
        <th scope="col">Gene Names</th>
        <th scope="col">Description</th>
        <th scope="col">Level</th>
        <th scope="col">Evolution Rate</th>
        <th scope="col">Total Genes Count</th>
        <th scope="col">Multi Copy Count</th>
        <th scope="col">Single Copy Count</th>
        <th scope="col">Present in #&nbsp;species</th>
        <th scope="col">Median Protein Length</th>
        <th scope="col">Stddev Protein Length</th>
      </tr>
    </thead>
    <tbody>
      {#each tableSlice as row}
        <tr>
          <td>{row.query}</td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <td></td>
          <!-- <td>{row.query}</td>
          <td>
            <a
              href="https://data.orthodb.org/v11/fasta?id={row.orthodb_id}"
              target="_blank"
              rel="noopener noreferrer"
              >{row.orthodb_id}
            </a>
          </td>
          <td>{row.gene_name}</td>
          <td>{row.description}</td>
          <td>{row.gene_count}</td>
          <td>{row.species_count}</td> -->
        </tr>
      {/each}
    </tbody>
  </table>

  {#if maxPage > 1}
    <div class="d-flex w-100 justify-content-center">
      <Paginator bind:page {maxPage} />
    </div>
  {/if}
</div>

<Tooltip target="prot_table_container" placement="top">
  Orthogroups information. To see the PANTHER subfamily annotation click on the name of
  protein/orthogroup.
</Tooltip>