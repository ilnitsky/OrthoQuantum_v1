<script>
  import { Button } from "sveltestrap";
  import { showTutorial } from "../../stores.js";
  import Tooltip from "./Tooltip.svelte";
  // for updating tooltip over the toggle button immediatly,
  // (otherwise requires re-hovering over the button to trigger)
  let showTutorialTooltip = false;

  function toggleTutorial() {
    showTutorial.update((v) => {
      v = !v;
      showTutorialTooltip = v;
      return v;
    });
  }
</script>

<Button id="tutorial-check" color="primary" type="button" active={$showTutorial} on:click={toggleTutorial}>
  {#if $showTutorial}Hide{:else}Show{/if} descriptions
</Button>

<Tooltip target="tutorial-check" placement="bottom" isOpen={showTutorialTooltip}>
  Information would be displayed while hovering over an element
</Tooltip>
