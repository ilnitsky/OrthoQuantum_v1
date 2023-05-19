import { dev } from '$app/environment';
import { goto } from '$app/navigation';
import { cookieConsent as cookieConsentStore } from '$lib/components/CookieConsent.svelte';

/**
 * Wrapper for fetch with error reporting and action handeling
 *
 * @param action action description, in form "do a thing" (prefixed by "Failed to")
 * @param input fetch input
 * @param init fetch init
 */
export async function fetchHandle<T>(
	action: string,
	input: Parameters<typeof fetch>[0],
	init?: Parameters<typeof fetch>[1],
	silent?: boolean
): Promise<T> {
	let errorText = 'unknown error';
	try {
		const res = await fetch(input, init);
		errorText = res.statusText;
		const json: App.APIResponse<T> = await res.json();
		if (json.message) {
			errorText = json.message;
		}
		if (!silent) {
			switch (json.action?.type) {
				case 'consent-form':
					cookieConsentStore.set(false);
					break;
				case 'goto':
					goto(json.action.path);
					break;
			}
		}
		if (res.ok && json.ok) {
			return json.data as T;
		}
	} catch (error) {
		dev && console.error(`Failed to ${action}: ${errorText}. Error:`, error);
	}
	if (!silent) {
		flashError(`Failed to ${action}: ${errorText}`);
	}
	throw null;
}

function flashError(error: string) {
	alert(error);
}

export function delay(timeout: number): Promise<void> {
	return new Promise<void>((resolve) => {
		setTimeout(resolve, timeout);
	});
}
