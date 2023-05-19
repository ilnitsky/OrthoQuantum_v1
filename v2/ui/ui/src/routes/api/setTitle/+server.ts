import { qidConvertTrusted, queries } from '$lib/server/db';
import type { RequestHandler } from './$types';
import { deserializeSetTitleRequest } from '$lib/serde/server';
import { error } from '@sveltejs/kit';
import { APIResponse } from '$lib/server/apiUtil';

export type Request = {
	/**
	 * @ulid
	 */
	qid: string;
	/**
	 * @nonempty
	 */
	title: string;
};
export type Response = undefined;

export const POST: RequestHandler = async (request) => {
	const req = await deserializeSetTitleRequest(request.request);
	console.log(req);

	const res = await queries.updateOne(
		{ _id: qidConvertTrusted(req.qid) },
		{ $set: { title: req.title.trim() }, $currentDate: { last_submit: true } }
	);
	if (res.modifiedCount != 1) {
		throw error(400, 'query not found');
	}
	return APIResponse(request, { ok: true });
};
