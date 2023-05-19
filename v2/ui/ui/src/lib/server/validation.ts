import { error, type RequestEvent } from '@sveltejs/kit';
import { COOKIE_NAME, COOKIE_VALUE } from '$lib/components/CookieConsent.svelte';
import { ulidToBin, users, Ulid } from './db';
import type { OptionalId } from 'mongodb';
import type { User } from '$lib/dbTypes';
import { env } from '$env/dynamic/private';
import { building } from '$app/environment';
const COOKIES_SECURE = env.HTTPS === 'true';
!building && console.log(`Cookies are ${COOKIES_SECURE ? '' : 'un'}secure`);

// function cookieConsented(req: RequestEvent) {
// 	if (req.cookies.get(COOKIE_NAME) !== COOKIE_VALUE) {
// 		throw error(400, {
// 			message: "you haven't consented to nesessary cookies",
// 			action: { type: 'consent-form' },
// 		});
// 	}
// }

async function registerUser(): Promise<[User, Ulid]> {
	const token = Ulid.generate();
	const user: OptionalId<User> = {
		showTutorial: true,
	};
	user._id = (
		await users.insertOne({
			...user,
			tokens: [
				{
					token: ulidToBin(token),
				},
			],
		})
	).insertedId;
	return [user as User, token];
}

async function validateToken(tok: string | undefined): Promise<User | null> {
	if (!tok || !Ulid.isCanonical(tok)) {
		return null;
	}
	const user = await users.findOne<User>(
		{
			tokens: { $elemMatch: { token: ulidToBin(Ulid.fromCanonicalTrusted(tok)) } },
		},
		{ projection: { tokens: 0 } }
	);
	return user;
}
const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;
const TOKEN_COOKIE = 'TOKEN';
export async function authenticateUser(req: RequestEvent): Promise<User>;
export async function authenticateUser(req: RequestEvent, optional: true): Promise<User | null>;
export async function authenticateUser(req: RequestEvent, optional?: true): Promise<User | null> {
	if (req.locals.user) {
		return req.locals.user;
	}
	if (req.cookies.get(COOKIE_NAME) !== COOKIE_VALUE) {
		if (optional) {
			return null;
		} else {
			throw error(400, {
				message: "you haven't consented to nesessary cookies",
				action: { type: 'consent-form' },
			});
		}
	}

	let token: Ulid;
	let user = await validateToken(req.cookies.get(TOKEN_COOKIE));
	if (!user) {
		[user, token] = await registerUser();
		req.cookies.set(TOKEN_COOKIE, token.toCanonical(), {
			path: '/',
			maxAge: COOKIE_MAX_AGE,
			secure: COOKIES_SECURE,
		});
	}
	req.locals.user = user;
	return user;
}
