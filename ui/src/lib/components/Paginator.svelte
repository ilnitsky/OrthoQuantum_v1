<script lang="ts">
  import { Button, InputGroup } from "sveltestrap";

  export let page = 1;
  export let maxPage: number;
  export let singlePageHide: boolean = false;

  if (!(page && Number.isInteger(page))){
    page = 1;
  }

  function constrainPageNumber() {
    const num = pageNumber;
    if (num === null || Number.isNaN(num)) {
      page = 1;
    } else {
      page = Math.min(Math.max(num, 1), maxPage);
    }
    pageNumber = page;
  }

  $: width = maxPage.toString().length + 3;
  $: pageNumber = page;
  $: maxPage, constrainPageNumber();
</script>

{#if !singlePageHide || maxPage > 1}
  <div class="d-block">
    <InputGroup class="input-group-sm">
      <Button
        on:click={() => {
          page = Math.max(page - 1, 1);
        }}
        disabled={page <= 1}
      >
        &lt;
      </Button>
      <input
        type="number"
        class="form-control"
        min=1
        on:change={() => {
          constrainPageNumber();
        }}
        bind:value={pageNumber}
        style:width={`${width}ch`}
      />
      <span class="input-group-text" style:width={`${width}ch`}>/{maxPage}</span>
      <Button
        on:click={() => {
          page = Math.min(page + 1, maxPage);
        }}
        disabled={page >= maxPage}
      >
        &gt;
      </Button>
    </InputGroup>
  </div>
{/if}

<style>
  input[type="number"]::-webkit-outer-spin-button,
  input[type="number"]::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }

  input[type="number"] {
    -moz-appearance: textfield;
    appearance: textfield;
    text-align: center;
  }
</style>
