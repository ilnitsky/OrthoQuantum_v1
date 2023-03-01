<script lang="ts">
  import { Input, InputGroupText } from "sveltestrap";

  export let value = 0;

  export let id: string | null = null;
  let feedback: string | null = null;

  function validateNumber(value: string): number | string {
    if (value.trim().length === 0) {
      return "Must provide a value!";
    }
    const num = new Number(value).valueOf();
    if (!Number.isFinite(num)) {
      return "Not a number!";
    }
    if (num < 0 || num > 100) {
      return "Must be between 0 and 100%";
    }
    return num;
  }

  function validateStr(val: string) {
    const num = validateNumber(val);
    if (typeof num === "string") {
      feedback = num;
    } else {
      feedback = null;
      value = num;
    }
  }

  $: valueStr = value.toFixed(1)
  $: { validateStr(valueStr) }
</script>

<div {id} class="input-group has-validation">
  <Input
    type="text"
    class="text-end"
    bind:value={valueStr}
    invalid={feedback !== null}
  />
  <InputGroupText>%</InputGroupText>
  <div class="invalid-feedback">
    {feedback}
  </div>
</div>
<Input min="0" max="100" step="0.5" type="range" bind:value />




