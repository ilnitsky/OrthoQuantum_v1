<script lang="ts">
  import Select from "svelte-select";
  let tax_id = [
    { value: 1, label: "one111" },
    { value: 2, label: "two" },
    { value: 3, label: "three" },
  ];
  let filterText = "";
  let items = tax_id;

  function parseNum(value: string): null|number {
    if (!(/^\s*\d+\s*$/.test(value))){
      return null;
    }
    const num = parseInt(value, 10);
    if (!Number.isInteger(num)){
      return null;
    }
    return num;
  }

  // if filterText is a number - generate a matching entry
  function handleFilter(e: any) {
    const num = parseNum(filterText);
    if (num === null) {
      if (items !== tax_id){
        items = tax_id;
      }
      return;
    }
    if (items === tax_id){
      items = [...tax_id, { value: num, label: filterText }];
    } else {
      const lastIdx = items.length - 1;
      if (items[lastIdx].label === filterText) {
        return;
      }
      items[lastIdx].value = num;
      items[lastIdx].label = filterText;
      items = items;
    }
  }
</script>

<Select
  id="taxid-input"
  class="mt-2"
  on:filter={handleFilter}
  bind:filterText
  {items}
  placeholder="Select species/enter taxid"
/>
