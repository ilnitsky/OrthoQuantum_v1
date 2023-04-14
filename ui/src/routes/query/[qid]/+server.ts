import { ClientUninterested, SSESender } from '$lib/server/sseSender';
import { ObjectId } from 'mongodb';
import { getFullData, getUpdates, setTitle } from '$lib/server/db';
import type { RequestHandler } from '@sveltejs/kit';

export const GET: RequestHandler = ({ url, request, params }) => {
	const sseStartTime = url.searchParams.get('sse');
	if(!sseStartTime || request.headers.get("accept") !== "text/event-stream" || !params.qid){
		return new Response(null, {
      status: 500
    });
	}
	const lastEventID = request.headers.get('Last-Event-ID');

	let clientGone: (reason: typeof ClientUninterested) => void;
	const clientGonePromise = new Promise<never>((resolve, reject) => {
		clientGone = reject;
	});
	const qid = new ObjectId(params.qid)
	const stream = new ReadableStream({
		async start(controller) {
			try {
				const sender = new SSESender(
					lastEventID || sseStartTime,
					controller,
					clientGonePromise,
					(startTime)=>getUpdates(qid, startTime),
					()=>getFullData(qid)
				);
				await sender.updateLoop(lastEventID === null);
			} catch {
				controller.close();
			}
		},
		cancel() {
			clientGone(ClientUninterested);
		}
	});

	return new Response(stream, {
		headers: {
			Connection: 'keep-alive',
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache'
		}
	});
};

export const POST: RequestHandler = (async ({request, params}) => {
	try {
		if (!params.qid){
			throw "Missing qid";
		}
		const req = await request.json();
		console.log(req);
		if (req.title === "Cancel"){
			throw "Invalid title";
		}
		await setTitle(params.qid, req.title);
		return new Response('{"ok":true}');
	} catch (err) {
		console.error(err);
		return new Response('{"ok":false}', {
      status: 500
    });
	}
});