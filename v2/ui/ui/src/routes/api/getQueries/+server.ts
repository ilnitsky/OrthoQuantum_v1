import { qidFormat, queries } from '$lib/server/db';
import type { ObjectId } from 'mongodb';
import type { RequestHandler } from './$types';
import { serializeGetQueriesResponse } from '$lib/serde/server';
import { APIResponse } from '$lib/server/apiUtil';
import { authenticateUser } from '$lib/server/validation';

export type Response = {
	ok: true;
	data: Data;
};

export type Data = { title: string; qid: string }[];

function getUserQueries(uid: ObjectId): Promise<Data> {
	return queries
		.find(
			{
				uid: uid,
			},
			{
				sort: { _id: -1 },
				projection: { _id: 1, title: 1 },
			}
		)
		.map(({ title, _id }) => ({
			title,
			qid: qidFormat(_id),
		}))
		.toArray();
}

export const GET: RequestHandler = async (req) => {
	const user = await authenticateUser(req);
	return APIResponse(
		req,
		{
			ok: true,
			data: await getUserQueries(user._id),
		},
		serializeGetQueriesResponse
	);
};
