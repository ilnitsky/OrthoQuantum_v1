import { writable } from 'svelte/store';

export const showTutorial = writable(
    (localStorage.getItem('showTutorial')??'1') === '1'
);

showTutorial.subscribe(value => {
	localStorage.setItem('showTutorial', value?'1':'0');
});
