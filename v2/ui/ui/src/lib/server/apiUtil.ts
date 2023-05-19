import { json, text, type RequestEvent } from '@sveltejs/kit';

export function APIResponse<Data = undefined>(
	request: RequestEvent,
	v: App.APIResponse<Data>,
	serializer?: (v: App.APIResponse<Data>) => string
): Response {
	if (serializer) {
		request.setHeaders({ 'content-type': 'application/json' });
		return text(serializer(v));
	} else {
		return json(v);
	}
}
