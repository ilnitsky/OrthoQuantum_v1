<script lang="ts">
  import Tooltip from "./tutorial/Tooltip.svelte";
  import TitleEdit from "./TitleEdit.svelte";
    import { debug } from "svelte/internal";

  let title = "Loading...";
  let editing = false;

  function onKeyDown(event: KeyboardEvent) {
    switch (event.code) {
      case "Space":
        if (!editing) {
          editing = true;
          event.preventDefault();
        }
        break;
      case "Enter":
        editing = !editing;
        event.preventDefault();
        break;
    }
  }
  function toggle() {
    editing = !editing;
  }
</script>

{#if editing}
  <TitleEdit bind:value={title} on:blur={toggle} on:change={toggle} on:keydown={onKeyDown}/>
{:else}
  <h1
    id="request-title"
    class="text-center link-primary"
    role="button"
    tabindex="0"
    on:click|preventDefault={toggle}
    on:keydown={onKeyDown}
  >
    {title}
  </h1>
  <Tooltip target="request-title" placement="bottom">Click to edit</Tooltip>
{/if}
