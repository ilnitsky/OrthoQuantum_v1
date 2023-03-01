<script lang="ts">
  import {
    Button,
    Card,
    CardBody,
    Col,
    Collapse,
    Input,
    InputGroup,
    InputGroupText,
    Row,
  } from "sveltestrap";
  import ConstrainedNum from "./components/ConstrainedNum.svelte";
  import Paginator from "./components/Paginator.svelte";
  import ProgressBar from "./components/ProgressBar.svelte";
  import Tooltip from "./tutorial/Tooltip.svelte";
  import image from "../assets/Correlation_preview.png";

  // TODO: tmp
  let isProgress = true;
  let isData = true;
  let optionsOpen = false;

  let quantileMin = 0;
  let quantileMax = 1;
  let correlationMin = -1;
  let correlationMax = 1;
  let pageSize = 1;

  let table = [1, 2, 3, 4];
  let page = 1;
  $: maxPage = Math.ceil(table.length / pageSize);
  $: tableSlice = table.slice((page - 1) * pageSize, Math.min(table.length, page * pageSize));

  function reset() {
    quantileMin = 0;
    quantileMax = 1;
    correlationMin = -1;
    correlationMax = 1;
    pageSize = 20;
  }
</script>

{#if isProgress || isData}
  <h3 id="corr_matrix_title" class="text-center">Correlation matrix</h3>
  <Tooltip target="corr_matrix_title" placement="bottom">
    The colors on the correlation matrix reflect the values of the Pearson correlation coefficient,
    on both axes a color bar is added corresponding to the percentage of homologs presence in
    species: a high percentage corresponds to black, a low one is colored bright red. The table
    contains sorted pairwise correlations.
  </Tooltip>
  <ProgressBar />
{/if}

{#if isData}
  <Row id="heatmap_container" class="mx-0">
    <Col lg="6" class="text-center px-0 pe-lg-2 mb-3 ">
      <a
        target="_blank"
        rel="noopener noreferrer"
        id="heatmap_link"
        class="mx-auto"
        href="#"
      >
        <!-- href="https://cataas.com/cat" -->
        <img
          id="heatmap_img"
          style:max-width="1100px"
          class="mx-auto w-100"
          alt="heatmap"
          src={image}
        />
      </a>
    </Col>
    <Col lg="6" class="px-0 ps-lg-2">
      <div class="d-flex flex-row justify-content-between mb-2">
        <!-- invisible button mirroring the options button for alignment -->
        <Button class="invisible" size="sm">Options</Button>
        <Paginator bind:page {maxPage} />
        <Button
          id="corr_table_options_show"
          class="float-end"
          size="sm"
          active={optionsOpen}
          on:click={() => {
            optionsOpen = !optionsOpen;
          }}
        >
          Options
        </Button>
      </div>
      <Collapse id="corr_table_options_collapse" isOpen={optionsOpen}>
        <Card class="mb-2">
          <CardBody class="p-2">
            <Row>
              <div class="d-flex flex-row justify-content-start flex-wrap">
                <div class="d-block m-1">
                  <InputGroup>
                    <ConstrainedNum
                      min={0}
                      max={1}
                      bind:value={quantileMin}
                      style="width: 7ch;"
                      class="form-control"
                    />
                    <InputGroupText>≤&nbsp;quantile&nbsp;≤</InputGroupText>
                    <ConstrainedNum
                      min={0}
                      max={1}
                      bind:value={quantileMax}
                      style="width: 7ch;"
                      class="form-control"
                    />
                  </InputGroup>
                </div>
                <div class="d-block m-1">
                  <InputGroup>
                    <ConstrainedNum
                      min={-1}
                      max={1}
                      bind:value={correlationMin}
                      style="width: 7ch;"
                      class="form-control"
                    />
                    <InputGroupText>≤&nbsp;correlation&nbsp;≤</InputGroupText>
                    <ConstrainedNum
                      min={-1}
                      max={1}
                      bind:value={correlationMax}
                      style="width: 7ch;"
                      class="form-control"
                    />
                  </InputGroup>
                </div>
                <div class="d-block m-1">
                  <InputGroup style="width: 11em;" class="mb-2">
                    <InputGroupText>Page size</InputGroupText>
                    <Input type="number" bind:value={pageSize} min={1} id="page_size" />
                  </InputGroup>
                </div>
              </div>
              <Col>
                <Button
                  id="reset_corr_settings"
                  color="danger"
                  outline
                  class="float-end"
                  on:click={reset}
                >
                  Reset
                </Button>
              </Col>
            </Row>
          </CardBody>
        </Card>
      </Collapse>
      <Row class="">
        <Col>
          <div class="table-responsive">
            <table class="table table-bordered table-responsive table-sm">
              <thead>
                <tr>
                  <th scope="col">Prot A</th>
                  <th scope="col">Prot B</th>
                  <th scope="col">Corr</th>
                  <th scope="col">Quantile</th>
                </tr>
              </thead>
              <tbody>
                {#each tableSlice as row}
                  <tr>
                    <td>{row}</td>
                    <td>{row}</td>
                    <td>{row}</td>
                    <td>{row}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        </Col>
      </Row>
    </Col>
  </Row>
{/if}
