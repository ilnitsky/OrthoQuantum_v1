import { minify } from 'html-minifier-terser';
import { building } from '$app/environment';

/** @type {import('@sveltejs/kit').Handle} */
export async function handle({ event, resolve }) {
	if (!building) {
		return resolve(event);
	}

	let page = '';
	return resolve(event, {
		transformPageChunk: ({ html, done }) => {
			page += html;
			if (done) {
				return minify(page, {
					collapseBooleanAttributes: true,
					collapseWhitespace: true,
					// conservativeCollapse: true,
					decodeEntities: true,
					html5: true,
					ignoreCustomComments: [/^#/],
					minifyCSS: true,
					minifyJS: true,
					removeAttributeQuotes: true,
					removeComments: false, // some hydration code needs comments, so leave them in
					removeEmptyAttributes: true,
					removeOptionalTags: true,
					removeRedundantAttributes: true,
					removeScriptTypeAttributes: true,
					removeStyleLinkTypeAttributes: true,
					sortAttributes: true,
					sortClassName: true,
				});
			}
		},
	});
}
