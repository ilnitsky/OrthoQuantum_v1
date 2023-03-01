<script lang="ts">
  import { Card, CardBody, Col, Label, Row } from "sveltestrap";
  import NumberField from "./blast/NumberField.svelte";
  import PercentField from "./blast/PercentField.svelte";
</script>

<Card class="mb-3">
  <CardBody class="pb-2">
    <Row>
      <Label sm="3" for="evalue">E-value threshold</Label>
      <Col sm="9" md=3>
        <NumberField id="evalue" value="1e-5" />
      </Col>
      <Label sm="3" class="mt-3 mt-md-0" for="pident-input-group">Sequence identity</Label>
      <Col sm="9" md=3 class="mt-3 mt-md-0">
        <PercentField id="pident-input-group" value={80} />
      </Col>
      <Label sm="3" class="mt-1 mt-md-0" for="qcov-input-group">Query coverage</Label>
      <Col sm="9" md=3 class="mt-1 mt-md-0">
        <PercentField id="qcov-input-group" value={80} />
      </Col>
    </Row>
  </CardBody>
</Card>
