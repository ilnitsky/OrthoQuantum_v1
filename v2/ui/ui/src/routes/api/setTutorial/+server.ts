import { users } from '$lib/server/db';
import type { RequestHandler } from './$types';
import { deserializeSetTutorialRequest } from '$lib/serde/server';
import { authenticateUser } from '$lib/server/validation';
import { APIResponse } from '$lib/server/apiUtil';

export type Request = {
	showTutorial: boolean;
};
export type Response = undefined;

export const POST: RequestHandler = async (request) => {
	const user = await authenticateUser(request);
	const req = await deserializeSetTutorialRequest(request.request);
	await users.findOneAndUpdate({ _id: user._id }, { $set: { showTutorial: req.showTutorial } });
	return APIResponse(request, { ok: true });
};
