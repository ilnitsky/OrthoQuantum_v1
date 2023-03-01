<script lang="ts">
  export let min = 0;
  export let max = 1;
  export let value: number;
  export let defaultValue = value;

  function formatNum(n: number): string {
    const res = n.toString();
    if (res.length < 3) {
      return n.toFixed(1);
    }
    return res;
  }
  function parseTextVal() {
    let v = Number.parseFloat(textVal);
    if (Number.isNaN(v)) {
      value = defaultValue;
    } else if (v < min) {
      value = min;
    } else if (v > max) {
      value = max;
    } else if (!Number.isFinite(v)) {
      value = defaultValue;
    } else {
      value = v;
    }
    textVal = formatNum(value);
  }

  $: textVal = formatNum(value);
</script>

<input
  type="number"
  on:change={parseTextVal}
  bind:value={textVal}
  {...$$restProps}
/>

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
