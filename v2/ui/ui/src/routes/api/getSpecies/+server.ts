import type { Species } from '$lib/dbTypes';
import { getSpecies } from '$lib/server/db';
import { ObjectId } from 'mongodb';
import type { RequestHandler } from './$types';
import { error } from '@sveltejs/kit';
import { serializeGetSpeciesResponse } from '$lib/serde/server';
import { APIResponse } from '$lib/server/apiUtil';

export type Response = {
	ok: true;
	data: Data;
};

export type Data = Species[];

export const GET: RequestHandler = async (req) => {
	const input = req.url.searchParams.get('taxon_id');
	let taxon_id: ObjectId | undefined;
	if (input) {
		try {
			taxon_id = new ObjectId(input);
		} catch {
			throw error(400, 'bad request');
		}
	}
	req.setHeaders({ 'cache-control': 'public,max-age=3600' });
	return APIResponse(
		req,
		{
			ok: true,
			data: await getSpecies(taxon_id),
		},
		serializeGetSpeciesResponse
	);
};
