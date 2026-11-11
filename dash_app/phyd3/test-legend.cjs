const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(`${__dirname}/js/phyd3.phylogram.js`, 'utf8');
const context = {
    phyd3: {phylogram: {}},
    colorbrewer: {Custom: {2: ['#170a1c', '#228cdb'], 4: ['#666666', '#170a1c', '#f72585', '#228cdb']}},
};
vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('    phyd3.phylogram.presenceLegend ='), source.indexOf('    phyd3.phylogram.build =')), context);
const graph = classes => ({type: 'heatmap', legend: {gradient: {name: 'Custom', classes}}});
let entries = context.phyd3.phylogram.presenceLegend([graph(2)]);
assert.equal(entries.length, 2, 'No BLAST entries for a two-color profile');
assert.equal(entries[0].color, '#170a1c');
assert.equal(entries[1].label, 'Found in OrthoDB');
entries = context.phyd3.phylogram.presenceLegend([graph('4'), graph(2)]);
assert.equal(entries.length, 4);
assert.equal(entries.find(e => e.label === 'Pending BLAST').color, '#666666');
assert.equal(context.phyd3.phylogram.presenceLegend([{type: 'pie'}]).length, 0);

function node(tag) {
    return {tag, attrs: {}, children: [],
        append(tag) { const child = node(tag); this.children.push(child); return child; },
        attr(key, value) { this.attrs[key] = value; return this; },
        style(key, value) { this.attrs[key] = value; return this; },
        text(value) { this.value = value; return this; },
    };
}
const svg = node('svg');
Object.assign(context, {svg, statusLegend: entries, selectorWidth: 500, legendColumns: 2,
    options: {plotInsetTop: 118}, getBackgroundColor: () => '#f5f5f5', getForegroundColor: () => '#000'});
vm.runInContext(source.slice(source.indexOf('        function drawPresenceLegend()'), source.indexOf('        function repaint()')), context);
context.drawPresenceLegend();
assert.equal(svg.children[0].attrs.class, 'presence-legend', 'Legend is a root overlay, outside the panning group');
assert.equal(svg.children[0].children.length, 5, 'Background and four entries');
assert.equal(svg.children[0].children[3].attrs.transform, 'translate(12,86)', 'Entries wrap on narrow plots');

const transform = {value: 'translate(5,6)'};
const width = {value: '500px'}, height = {value: '300px'};
const exported = {
    getElementById: () => ({getBBox: () => ({x: 0, y: -40, width: 400, height: 900}), getAttributeNode: () => transform}),
    getAttributeNode: key => key === 'width' ? width : height,
};
class Serializer {
    serializeToString() { return JSON.stringify({transform: transform.value, height: height.value}); }
}
Object.assign(context, {selector: {querySelector: () => exported}, window: {XMLSerializer: Serializer}, XMLSerializer: Serializer});
context.options.marginX = 100;
vm.runInContext(source.slice(source.indexOf('        function getSVGData()'), source.indexOf('        // action handlers for domain view')), context);
const data = JSON.parse(context.getSVGData());
assert.equal(data.transform, 'translate(20, 158)', 'Export reserves the legend header');
assert.equal(data.height, '1038', 'Export includes full tree and header');
assert.equal(transform.value, 'translate(5,6)', 'Export restores interactive position');
assert.equal(height.value, '300px');
console.log('Legend palette, layout and export checks passed');
