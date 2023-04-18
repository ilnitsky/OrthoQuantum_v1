import { getAllSpecies, getSpecies } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async (t) => {
	const taxon_id = t.url.searchParams.get('taxon_id');
	return new Response(
		JSON.stringify({
			ok: true,
			data: await (taxon_id ? getSpecies(taxon_id) : getAllSpecies())
		})
	);
};
