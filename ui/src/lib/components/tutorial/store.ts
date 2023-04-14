import { browser } from '$app/environment';
import { writable } from 'svelte/store';

export const showTutorial = writable(
	// if prerendering - show tooltips
	!browser || (localStorage.getItem('showTutorial') || '1') === '1'
);

if (browser) {
	showTutorial.subscribe((value) => {
		localStorage.setItem('showTutorial', value ? '1' : '0');
	});
}
