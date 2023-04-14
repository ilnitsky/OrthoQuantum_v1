<script lang="ts">
	import {
		Dropdown,
		Nav,
		NavItem,
		DropdownItem,
		DropdownToggle,
		DropdownMenu,
		NavLink
	} from 'sveltestrap';

	import { page } from '$app/stores';
	import Alerts from './Alerts.svelte';

	let hasAlerts = false;
	let showAlerts = true;
	let active: string;

	$: if ($page.route.id?.startsWith('/query/')) {
		active = $page.params.qid;
	} else if ($page.route.id?.startsWith('/about')) {
		active = 'about';
	}
</script>

<Nav navbar class="w-100">
	<NavItem class="me-auto">
		<NavLink href="/query/new" active={active === 'new'}>New query</NavLink>
	</NavItem>

	<Dropdown nav inNavbar>
		<DropdownToggle nav caret>My queries</DropdownToggle>
		<DropdownMenu end>
			<!-- TODO: mark active query in the list -->
			<DropdownItem>Query 2</DropdownItem>
			<DropdownItem>Query 1</DropdownItem>
		</DropdownMenu>
	</Dropdown>
	<NavItem>
		<NavLink href="/about" active={active === 'about'}>Help/About</NavLink>
	</NavItem>
	<!-- {#if hasAlerts}
		 <NavItem>
			<NavLink
				on:click={() => {
					showAlerts = !showAlerts;
				}}
				aria-describedby="notificationDisplay"
			>
				<span id="notificationDisplay" class="d-sm-none">{#if showAlerts}Hide{:else}Show{/if} notifications</span>
				<div style:margin-top="-3px" class="d-sm-block d-none">
					{#if showAlerts}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="24"
						height="24"
						fill="currentColor"
						class="bi bi-bell-slash-fill"
						viewBox="0 0 16 16"
					>
						<path
							d="M5.164 14H15c-1.5-1-2-5.902-2-7 0-.264-.02-.523-.06-.776L5.164 14zm6.288-10.617A4.988 4.988 0 0 0 8.995 2.1a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 7c0 .898-.335 4.342-1.278 6.113l9.73-9.73zM10 15a2 2 0 1 1-4 0h4zm-9.375.625a.53.53 0 0 0 .75.75l14.75-14.75a.53.53 0 0 0-.75-.75L.625 15.625z"
						/>
					</svg>
				{:else}
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="24"
						height="24"
						fill="currentColor"
						class="bi bi-bell-fill"
						viewBox="0 0 16 16"
					>
						<path
							d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"
						/>
					</svg>
				{/if}
				</div>
			</NavLink>
		</NavItem>
	{/if}-->
</Nav>

<Alerts bind:hasAlerts bind:showAlerts />
