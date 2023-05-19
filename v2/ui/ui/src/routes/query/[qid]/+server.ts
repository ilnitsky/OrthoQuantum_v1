import { ClientUninterested, SSESender } from '$lib/server/sseSender';
import { Binary, ObjectId, Timestamp } from 'mongodb';
import {
	defaultQuery,
	getFullData,
	qidCheck,
	qidConvertTrusted,
	queries,
	Ulid,
} from '$lib/server/db';
import { error, type RequestHandler } from '@sveltejs/kit';
import { deserializeInput } from '$lib/serde/server';
import { authenticateUser } from '$lib/server/validation';
import type { SubmitQuery } from '$lib/dbTypes';
import { APIResponse } from '$lib/server/apiUtil';

function getUpdates(qid: Binary, changeStreamStart: string) {
	return queries.watch(
		[
			{
				$match: {
					operationType: { $in: ['update', 'invalidate', 'replace'] },
					documentKey: { _id: qid },
				},
			},
			{
				$project: {
					clusterTime: 1,
					updateDescription: 1,
					operationType: 1,
					fullDocument: 1,
				},
			},
		],
		{ startAtOperationTime: Timestamp.fromString(changeStreamStart, 10) }
	);
}

export const GET: RequestHandler = ({ url, request, params }) => {
	const sseStartTime = url.searchParams.get('sse');
	if (!sseStartTime || request.headers.get('accept') !== 'text/event-stream' || !params.qid) {
		throw error(400, 'Incorrect request');
	}
	const lastEventID = request.headers.get('Last-Event-ID');

	let clientGone: (reason: typeof ClientUninterested) => void;
	const clientGonePromise = new Promise<never>((resolve, reject) => {
		clientGone = reject;
	});
	const qid = qidCheck(params.qid);
	const stream = new ReadableStream({
		async start(controller) {
			try {
				const sender = new SSESender(
					lastEventID || sseStartTime,
					controller,
					clientGonePromise,
					(startTime) => getUpdates(qid, startTime),
					() => getFullData(qid)
				);
				await sender.updateLoop(lastEventID === null);
			} catch {
				controller.close();
			}
		},
		cancel() {
			clientGone(ClientUninterested);
		},
	});

	return new Response(stream, {
		headers: [
			['connection', 'keep-alive'],
			['content-type', 'text/event-stream'],
			['cache-control', 'no-cache'],
		],
	});
};

///fire-and-forget
function giveOrdinalName(qid: Binary, uid: ObjectId) {
	queries
		.countDocuments({ uid: { $eq: uid }, _id: { $lte: qid } })
		.then((num) => queries.updateOne({ _id: qid }, { $set: { title: `Query #${num}` } }))
		.catch((err) => console.log(`Failed to set ordinal name (non-critical): ${err.toString()}`));
}

// TODO: add to job_q
async function newQuery(uid: ObjectId, query: SubmitQuery) {
	const qid = Ulid.generate();
	const qidBin = new Binary(qid.bytes);

	await queries.insertOne({
		...query,
		_id: qidBin,
		output: {},
		uid: uid,
		last_submit: new Date(),
		last_view: new Date(),
	});
	if (query.title == defaultQuery.title) {
		giveOrdinalName(qidBin, uid);
	}
	return qid.toCanonical();
}

export const POST: RequestHandler = async (req) => {
	const qid = req.params['qid'];
	if (!qid || (qid != 'new' && !Ulid.isCanonical(qid))) {
		throw error(400, 'bad request');
	}
	const [user, query] = await Promise.all([authenticateUser(req), deserializeInput(req.request)]);

	const resp: App.APIResponse = {
		ok: true,
	};
	if (qid == 'new') {
		const created_qid = await newQuery(user._id, query);
		resp.action = {
			type: 'goto',
			path: `/query/${created_qid}`,
		};
	} else {
		const res = await queries.updateOne(
			{ _id: qidConvertTrusted(qid) },
			{
				$set: query,
				$currentDate: { last_submit: true },
				// { $type: "timestamp" }
			}
		);
		if (res.modifiedCount != 1) {
			throw error(404, 'query not found');
		}
	}
	return APIResponse(req, resp);
};
