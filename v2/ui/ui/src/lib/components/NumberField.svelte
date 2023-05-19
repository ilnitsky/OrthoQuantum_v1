<script lang="ts">
	import { Input } from 'sveltestrap';

	export let value = '';
	export let errorDelay = 700;

	let timer: ReturnType<typeof setTimeout> | null;
	let feedback: string | undefined = undefined;

	function validateNumber(value: string): number | string {
		if (value.trim().length === 0) {
			return 'Must provide a value!';
		}
		const num = new Number(value).valueOf();
		if (!Number.isFinite(num)) {
			return 'Not a number!';
		}
		return num;
	}

	function validateImmediatly() {
		if (timer !== null) {
			clearTimeout(timer);
			timer = null;
		}
		const num = validateNumber(value);
		feedback = typeof num === 'string' ? num : undefined;
	}

	function validateValue(val: string) {
		if (timer !== null) {
			clearTimeout(timer);
			timer = null;
		}
		const num = validateNumber(val);
		if (typeof num === 'string') {
			if (errorDelay <= 0 || !Number.isFinite(errorDelay) || feedback !== null) {
				// no delay
				feedback = num;
			} else {
				// delay error popup after delay (gives time to fix the error without annoying the user)
				timer = setTimeout(validateImmediatly, errorDelay);
			}
		} else {
			// valid number, remove error immediatly
			feedback = undefined;
		}
	}

	$: {
		validateValue(value);
	}
</script>

<Input
	type="text"
	class="text-end"
	bind:value
	on:blur={validateImmediatly}
	on:change={validateImmediatly}
	invalid={feedback !== undefined}
	{feedback}
	{...$$restProps}
/>
