<script>
  import './assets/bootstrap.min.css';
  import Main from './lib/Main.svelte';
  import CookieConsent from './lib/CookieConsent.svelte';
  import { Container } from 'sveltestrap';
  import Navbar from './lib/Navbar.svelte';
  import './app.css'

</script>

<div>
  <Navbar/>
<Container fluid>
  <Main/>
</Container>
<CookieConsent />
</div>


