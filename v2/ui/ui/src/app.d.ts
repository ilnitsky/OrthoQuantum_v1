// See https://kit.svelte.dev/docs/types#app
import type { User } from '$lib/dbTypes';

// for information about these interfaces
declare global {
	namespace App {
		type Action =
			| {
					type: 'consent-form';
			  }
			| {
					type: 'goto';
					path: string;
			  };
		interface Error {
			action?: Action;
			message: string;
		}
		type APIResponse<T = undefined> = Partial<Error> &
			(T extends undefined
				? {
						ok: true;
						data?: undefined;
				  }
				: {
						ok: true;
						data: T;
				  });

		interface Locals {
			user?: User;
		}
		// interface PageData {}
		// interface Platform {}
	}
}

export {};
