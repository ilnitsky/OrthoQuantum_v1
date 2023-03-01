<script lang="ts">
  import { Tooltip } from "sveltestrap";
  import type { TooltipPlacement } from "sveltestrap/src/Tooltip";
  export let target: string | HTMLElement;
  export let placement: TooltipPlacement;
  export let isOpen: boolean = false;
  import { showTutorial } from "../../stores.js";
</script>

{#if $showTutorial}
  <Tooltip {isOpen} {target} {placement} container="body">
    <slot />
  </Tooltip>
{/if}

<style>
  :global(.tooltip-inner) {
    max-width: 400px;
  }
</style>
