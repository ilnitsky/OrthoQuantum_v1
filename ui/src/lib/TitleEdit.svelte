<script lang="ts">
  import { onMount } from "svelte";

  export let value;
  let ref;

  onMount(()=>{
    ref.focus();
    ref.select();
  });

</script>

<input class="form-control form-control-lg mb-2 text-center" type="text"
  bind:this={ref} bind:value on:blur on:change on:keydown {...$$restProps}
>