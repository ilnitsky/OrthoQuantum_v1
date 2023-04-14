<script lang="ts">
	import { InputGroupText } from 'sveltestrap';
	export let id: string | null = null;
	let feedback: string | undefined;

	export let value = 0;
	let internalValue = 0;
	let valueInput = '0';

	function onValueChange() {
		if (value !== internalValue) {
			if (validateNum(value) !== null){
				internalValue = value;
			}
			valueInput = value.toString();
		}
	}
	$: value, onValueChange();

	function validateStr(str: string): number | null {
		str = str.trim();
		if (str.length === 0) {
			feedback = 'Must provide a value!';
			return null;
		}
		return validateNum(new Number(str).valueOf());
	}

	function validateNum(num: number): number | null {
		if (!Number.isFinite(num)) {
			feedback = 'Not a number!';
			return null;
		}
		if (num < 0 || num > 100) {
			feedback = 'Must be between 0 and 100%';
			return null;
		}
		feedback = undefined;
		return num;
	}

	function inputHandler(
		e: Event & {
			currentTarget: EventTarget & HTMLInputElement;
		}
	) {
		valueInput = e.currentTarget.value;

		const val = validateStr(valueInput);
		if (val !== null) {
			internalValue = val;
			if (e.type === 'change') {
				value = internalValue;
			}
		}
	}

	function rangeHandler(
		e: Event & {
			currentTarget: EventTarget & HTMLInputElement;
		}
	) {
		internalValue = e.currentTarget.valueAsNumber;
		valueInput = internalValue.toFixed(1);
		if (e.type === 'change') {
			value = internalValue;
		}
	}
</script>

<div {id} class="input-group has-validation">
	<input
		class="text-end form-control"
		type="text"
		value={valueInput}
		class:is-invalid={!!feedback}
		on:input={inputHandler}
		on:change={inputHandler}
	/>
	<InputGroupText>%</InputGroupText>
	<div class="invalid-feedback">
		{feedback}
	</div>
</div>
<input
	min="0"
	max="100"
	step="0.5"
	type="range"
	class="form-range"
	value={internalValue}
	on:input={rangeHandler}
	on:change={rangeHandler}
/>
