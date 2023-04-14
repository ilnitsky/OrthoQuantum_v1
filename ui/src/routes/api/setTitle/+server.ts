import { setTitle } from '$lib/server/db';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = (async (t) => {
  const req = await t.request.json();
  console.log(req);
  if (req.title === "Cancel"){
    return new Response(`{"ok": false}`, {
      status: 500
    });
  }
  await setTitle(req.qid, req.title);
  return new Response(`{"ok": true}`);
});