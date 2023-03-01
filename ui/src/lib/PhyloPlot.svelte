<script lang="ts">
    import { tick } from "svelte";
  import { Button, Input, Label, Nav, NavItem, NavLink } from "sveltestrap";
  import ProgressBar from "./components/ProgressBar.svelte";

  const height = 2000;

  let isInteractive = true;

  let showGroups = false;
  let showSpecies = true;
  let dynamicHide = false;

  let phyd3_rendered = false;
  let svg_rendered = false;

  let rawZoom = 100;

  function transformZoom(val: number): number {
    if (val > 100) {
      val = val * 2 - 100;
    }
    return val / 100;
  }
  $: zoom = transformZoom(rawZoom);

  // taskid_for_links: this.props.taskid_for_links,
  function updateOpts(taskid:string, leafCount:number, doShowGroups:boolean, doShowSpecies:boolean, doDynamicHide:boolean) {
    const scaleX = 0.4;
    const scaleY = 0.01183 * leafCount;
    let showNodesType: string;
    if (doShowGroups && doShowSpecies) {
      showNodesType = "all";
    } else if (doShowGroups) {
      showNodesType = "only inner";
    } else {
      showNodesType = "only leaf";
    }
    const showNodeNames = doShowGroups || doShowSpecies;
    const opts = {
      // editable
      origScaleX: scaleX,
      scaleX,
      origScaleY: scaleY,
      scaleY,
      height,
      showNodesType,
      showNodeNames,
      dynamicHide: doDynamicHide,
      taskid_for_links: taskid,
      // defaults
      invertColors: false,
      lineupNodes: true,
      showDomains: false,
      showDomainNames: false,
      showDomainColors: true,
      showGraphs: true,
      showGraphLegend: true,
      showLength: false,
      nodeHeight: 10,
      scaleStep: 0.23,
      margin: 100,
      showPhylogram: true,
      showTaxonomy: false,
      showFullTaxonomy: false,
      showSequences: false,
      showLabels: false,
      showTaxonomyColors: false,
      backgroundColor: "#f5f5f5",
      foregroundColor: "#000000",
      nanColor: "#f5f5f5",
    };
    phyd3_rendered = false;
    return opts
  }
  $: opts = updateOpts("", 123, showGroups, showSpecies, dynamicHide);

  function focus_and_redraw_phyd3() {
    isInteractive = true;
    if (!phyd3_rendered){
      tick().then(()=>{
        // d3.xml(`${this.props.url}?version=${this.props.version}`, (err, xml) => {
        //   if (err != null) {
        //     d3.select(this.ref.current).text("Error");
        //   } else {
        //     let tree = phyd3.phyloxml.parse(xml);
        //     d3.select(this.ref.current).html("Loading");
        //     phyd3.phylogram.build(phyd3_ref, tree, opts);
        //   }
        // });
        phyd3_rendered = true;
      })
    }
  }

  let phyd3_ref;
  let svg_ref;

</script>

<h3 id="tree_title" class="mt-3 text-center">Phylogenetic profile plot</h3>
<!-- tree_progress_bar -->
<ProgressBar />
<div class="my-2">
  <p>
    The columns show the orthogroups, with the same name as the query proteins. Rows of the heatmap
    show the eukaryotic genomes, major taxa on the species tree are labeled with different colors.
  </p>
  <p>
    To scale the graph use a mouse wheel while holding Alt to scale x axis and/or Ctrl to scale y
    axis.
  </p>
  <p>Legend:</p>
  <ul>
    <li>
      <span style:background-color="#170a1c" class="tree-legend" />
      <span>No findings</span>
    </li>
    <li>
      <span style:background-color="#666666" class="tree-legend" />
      <span>Scheduled to be BLAST'ed</span>
    </li>
    <li>
      <span style:background-color="#f72585" class="tree-legend" />
      <span>Found via BLAST</span>
    </li>
    <li>
      <span style:background-color="#228cdb" class="tree-legend" />
      <span>Found in OrthoDB</span>
    </li>
  </ul>
</div>
<!-- TODO: replace NavLinks with similar items without href inside -->
<Nav tabs>
  <NavItem>
    <NavLink active={isInteractive} on:click={focus_and_redraw_phyd3}>
      Interactive graph
    </NavLink>
  </NavItem>
  <NavItem>
    <NavLink active={!isInteractive} on:click={() => {
      if (!isInteractive && svg_rendered){
        return;
      }
      isInteractive = false;
      svg_rendered = false;
      tick().then(()=>{  // show "rendering"
        // phyd3.phylogram.renderSVG(svg_ref);
        svg_rendered = true;
      });
    }}>
      <!-- correct: disabled={isInteractive && !phyd3_rendered} -->
      Static image
    </NavLink>
  </NavItem>
  <NavItem class="ms-auto">
    <NavLink on:click={()=>{
      focus_and_redraw_phyd3();
      // phyd3.phylogram.renderPNG();
    }}>
      Download image
    </NavLink>
  </NavItem>
  <NavItem>
    <NavLink target="_blank" rel="noopener noreferrer" href="/download_table">Download csv</NavLink>
  </NavItem>
</Nav>
<div style:height="56px" class="mt-2 d-flex align-items-start" class:flex-column={!isInteractive}>
  {#if isInteractive}
    <div class="d-inline-block">
      <Input type="checkbox" label="Show group names" bind:checked={showGroups} />
      <Input type="checkbox" label="Show species names" bind:checked={showSpecies} />
    </div>
    <Input type="checkbox" label="Dynamic hide" class="ms-3" bind:checked={dynamicHide} />
    <!-- TODO: id's used in phyd3, rewrite to expose functions -->
    <Button id="resetZoom" class="ms-3">Reset Zoom</Button>
    <Button id="resetPos" class="ms-1">Reset Position</Button>
    <Button id="fitTree" class="ms-1">Fit Tree To View</Button>
  {:else}
    <Input type="range" min="1" max="200" step="1" bind:value={rawZoom} />
    <span class="align-self-center">{zoom.toFixed(2)}x</span>
  {/if}
</div>
<div style:height={`${height}px`}>
  {#if isInteractive && !phyd3_rendered || !isInteractive && !svg_rendered}
    <div class="text-center">Rendering...</div>
  {/if}
  <!-- phyd3 -->
  <div bind:this={phyd3_ref} class:invisible={!isInteractive || !phyd3_rendered} />
  <!-- svg -->
  <div class:invisible={isInteractive || !svg_rendered} class="overflow-scroll position-relative w-100 h-100">
    <div bind:this={svg_ref} id="phyd3svg" style:transform={`scale(${zoom})`} />
  </div>
</div>

<!-- <Nav tabs>
  <NavItem>
    <NavLink
      className={this.state.activeTab === 'tree' ? "active" : ""}
      onClick={() => { this.toggle('tree'); }}
    >
      Interactive graph
    </NavLink>
  </NavItem>
  <NavItem>
    <NavLink
      className={this.state.activeTab === 'svg' ? "active" : ""}
      onClick={() => { this.toggle('svg'); }}
    >
      Static image
    </NavLink>
  </NavItem>
  <NavItem className="ml-auto">
    <NavLink
      disabled={this.state.activeTab !== 'tree'}
      onClick={() => { phyd3.phylogram.renderPNG(); }}
    >
      Download image
    </NavLink>
  </NavItem>
  {
    this.props.show_download_csv &&
    <NavItem>
      <NavLink onClick={() => {
        this.props.setProps({csv_render_n: this.props.csv_render_n+1});
      }}>
        Download csv
      </NavLink>
    </NavItem>
  }

</Nav>
<div className="tab-content">

  <div
    ref={this.ref}
    id="phyd3"
    className={"tab-pane fade" + (this.state.activeTab === "tree" ? "show active" : "")}></div>
  <div
    className={"tab-pane fade" + (this.state.activeTab === "svg" ? "show active" : "")}
    style={{
      paddingTop: this.props.height,
      overflow: "scroll",
      position: "relative",
    }}
  >
    <div
      ref={this.svg_ref}
      id="phyd3svg"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        transformOrigin: "0 0",
        transform: myScale,
      }}
    ></div>
  </div>
</div> -->

<!-- <PhydthreeComponent
  id="tree_component"
  url="/files/123/tree.xml"
  height="2000"
  taskid_for_links="123"

/> -->
<style>
  span.tree-legend {
    width: 20px;
    height: 20px;
    border: 1px solid black;
    display: inline-block;
    margin-right: 5px;
    vertical-align: text-bottom;
  }
  #phyd3svg {
    position: absolute;
    top: 0;
    left: 0;
    transform-origin: 0 0;
  }
</style>
