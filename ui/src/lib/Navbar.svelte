<script lang="ts">
  import {
    Dropdown,
    Collapse,
    Nav,
    NavItem,
    NavLink,
    DropdownItem,
    NavbarBrand,
    NavbarToggler,
    DropdownToggle,
    DropdownMenu,
  } from "sveltestrap";

  let isOpen = false;

  function handleUpdate(event: CustomEvent<boolean>) {
    isOpen = event.detail;
  }
</script>

<!-- Not using Navbar, need to access inner container -->
<nav class="navbar navbar-expand-md navbar-light bg-light sticky-top">
  <div class="container">
    <NavbarBrand href="/">Home</NavbarBrand>
    <NavbarToggler on:click={() => (isOpen = !isOpen)} />
    <Collapse {isOpen} navbar expand="md" on:update={handleUpdate} class="ml-auto">
      <Nav navbar class="ms-auto">
        <NavItem>
          <NavLink href="/about">Help/About</NavLink>
        </NavItem>
        <Dropdown nav inNavbar>
          <DropdownToggle nav caret>My queries</DropdownToggle>
          <DropdownMenu end>
            <DropdownItem>Option 1</DropdownItem>
            <DropdownItem>Option 2</DropdownItem>
            <DropdownItem divider />
            <DropdownItem>Reset</DropdownItem>
          </DropdownMenu>
        </Dropdown>
      </Nav>
    </Collapse>
  </div>
</nav>

<style>
  /* limit navbar size on xxl */
  @media (min-width: 1400px) {
    .container {
      max-width: 1140px;
    }
  }
</style>
