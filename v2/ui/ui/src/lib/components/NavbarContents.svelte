<script lang="ts">
	import {
		Dropdown,
		Nav,
		NavItem,
		DropdownItem,
		DropdownToggle,
		DropdownMenu,
		NavLink,
	} from 'sveltestrap';
	import { isEqual } from 'lodash-es';
	import { page } from '$app/stores';
	import { fetchHandle } from '$lib/fetchUtil';
	import type { Data } from '../../routes/api/getQueries/+server';
	import { afterNavigate, goto } from '$app/navigation';

	let queryListLoading = false;
	let queryListOpen = false;
	let queries: Data = [];

	function update(evt?: Event) {
		if (queryListLoading || (evt && queryListOpen)) {
			return;
		}
		queryListLoading = true;
		fetchHandle<Data>(
			'get the list of queries',
			'/api/getQueries',
			{
				method: 'GET',
			},
			!evt // fail silently if not triggered by user's interaction
		)
			.then((v) => {
				if (!isEqual(queries, v)) {
					queries = v;
				}
			})
			.finally(() => {
				queryListLoading = false;
			});
	}
	afterNavigate(() => {
		update();
	});

	let active: string;
	let in_query = false;
	$: {
		const route = $page.route.id || '';
		in_query = route.startsWith('/query/');
		if (in_query) {
			active = $page.params.qid;
		} else if (route.startsWith('/about')) {
			active = 'about';
		} else {
			active = '';
		}
	}
	function gotoQid(qid: string) {
		goto(`/query/${qid}`, {
			noScroll: in_query,
		});
	}
</script>

<Nav id="nav" navbar class="w-100">
	<NavItem class="me-auto">
		<NavLink
			on:click={() => {
				gotoQid('new');
			}}
			active={active === 'new'}
		>
			New query
		</NavLink>
	</NavItem>

	<Dropdown nav inNavbar bind:isOpen={queryListOpen}>
		<div on:mouseover={update} on:focus={update}>
			<DropdownToggle
				nav
				caret
				class={queries.some((q) => q.qid === active) ? 'active' : undefined}
			>
				My queries
			</DropdownToggle>
			<!-- {#if queryListOpen && queryListLoading}<Spinner size="sm" class="ms-1" />{/if} -->
		</div>
		<DropdownMenu end>
			{#each queries as q (q.qid)}
				<DropdownItem
					on:click={() => {
						gotoQid(q.qid);
					}}
					active={q.qid === active}>{q.title}</DropdownItem
				>
			{:else}
				<DropdownItem disabled={true}>No queries</DropdownItem>
			{/each}
		</DropdownMenu>
	</Dropdown>
	<NavItem>
		<NavLink href="/about" active={active === 'about'}>Help/About</NavLink>
	</NavItem>
</Nav>
