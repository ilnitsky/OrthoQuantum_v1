<script lang="ts" context="module">
  type MyAlert = {
		text: string;
		color: Color;
		dismissible: boolean | number;
		title?: string;
		isOpen: boolean;
		isPersistant: boolean;
	};
  // TODO: undo module-context, switch to standard context for publishing alerts

  let alertCounter = 0;
  const dismissDur = 3000;
  const alerts = new Map<number, MyAlert>();
  let publish: undefined | Subscriber<typeof alerts>;
  function updateAlerts(){
    publish?.(alerts);
  }

  let alertsStore = readable(alerts, (set)=>{
    publish = set;
    return ()=>{
      publish = undefined;
    }
  });
  export function updateAlert(id: number, updator: (alert: MyAlert)=>void){
    const alert = alerts.get(id);
    if (!alert){
      return false;
    }
    updator(alert);
    if (!alert.isOpen && !alert.isPersistant){
      alerts.delete(id);
    }
    updateAlerts();
    return true;
  }

  export function addAlert(
		text: string,
		title?: string,
		color: Color = 'info',
		dismissible: boolean | number = dismissDur,
		isPersistant = false
	): number {
		alertCounter++;
		const id = alertCounter;
		alerts.set(id, { text, color, dismissible, title, isOpen: true, isPersistant });
		updateAlerts();
		if (typeof dismissible === 'number') {
			setTimeout(() => {
				const alert = alerts.get(id);
				if (!alert) {
          return;
				}
        if (alert.isPersistant) {
          alert.isOpen = false;
        } else {
          alerts.delete(id);
        }
        updateAlerts();
			}, dismissible);
		}
		return id;
	}
</script>

<script lang="ts">
	import type { Color } from 'sveltestrap/src/shared';
	import { flip } from 'svelte/animate';
	import { fly } from 'svelte/transition';
	import { readable, type Subscriber } from 'svelte/store';

	/** read-only */
	export let hasAlerts: boolean;
	export let showAlerts = true;

	let visibleAlerts: [number, MyAlert][] = [];
	let scrollFix: ReturnType<typeof setTimeout> | undefined;
	const animDuration = 500;

	function scrollFixOff() {
		filler?.style.removeProperty('height');
		scrollFix = undefined;
	}
	function filterAlerts() {
		visibleAlerts.length = 0;
		alerts.forEach((v, k) => {
			if (v.isOpen) {
				visibleAlerts.push([k, v]);
			}
		});
		visibleAlerts.sort((a, b) => a[0] - b[0]);
		visibleAlerts = visibleAlerts;

		clearTimeout(scrollFix);
		filler?.style.setProperty('height', '100%');
		scrollFix = setTimeout(scrollFixOff, animDuration * 1.5);
	}
	$: $alertsStore, filterAlerts();
	$: hasAlerts = visibleAlerts.length !== 0;

	let filler: HTMLDivElement | undefined;

	function closeAlert(
		e: MouseEvent & {
			currentTarget: EventTarget & HTMLButtonElement;
		}
	) {
		const id = parseInt(e.currentTarget.parentElement?.dataset?.alertid || '0');
		const alert = alerts.get(id);
		if (!alert) {
			return;
		}
		if (alert.isPersistant) {
			alert.isOpen = false;
		} else {
			alerts.delete(id);
		}
		updateAlerts()
	}
</script>

{#if showAlerts}
	<div class="alerts-container">
		<div class="alerts me-3 mt-3" bind:this={filler}>
			{#each visibleAlerts as [k, v] (k)}
				<div
					animate:flip={{ duration: animDuration }}
					in:fly={{ y: -100, duration: animDuration }}
					out:fly={{ x: 200, duration: animDuration }}
					class={`mb-3 alert alert-${v.color}`}
					class:alert-dismissible={v.dismissible === true}
					data-alertid={k}
				>
					{#if v.title}
						<h4 class="alert-heading text-capitalize">{v.title}</h4>
					{/if}
					{#if v.dismissible === true}
						<button type="button" class="btn-close" aria-label="Close" on:click={closeAlert} />
					{/if}
					{v.text}
				</div>
			{/each}
		</div>
	</div>
{/if}

<style>
	.alerts-container {
		position: fixed;
		/* navbar margin */
		top: 3.5rem;
		right: 0;
		bottom: 0;
		width: 20rem;
		/* below navbar */
		z-index: 900;
		pointer-events: none;
	}
	.alerts {
		max-height: 100%;
		overflow: auto;
		pointer-events: auto;
	}
</style>
