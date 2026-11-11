// Focused regression checks for wheel scheduling; no browser dependencies.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(`${__dirname}/js/phyd3.phylogram.js`, 'utf8');
const start = source.indexOf('        var zoomFramePending = false;');
const end = source.lastIndexOf('\n    }\n}());');
assert.ok(start >= 0 && end > start, 'wheel handler source must be present');

function viewer() {
    const frames = [];
    const calls = {layout: 0, transform: 0};
    const context = {
        d3: {event: {}},
        options: {
            scaleStep: 0.23, scaleX: 1, scaleY: 1,
            translateX: 0, translateY: 0, graphWidth: 100,
            domainWidth: 100, domainWidthStep: 10, height: 500,
        },
        treeHeight: 1000, treeWidth: 500, selectorWidth: 500,
        requestAnimFrame: callback => frames.push(callback),
        redrawTree: () => calls.layout++,
        applyZoomTransform: () => calls.transform++,
    };
    vm.createContext(context);
    vm.runInContext(source.slice(start, end), context);
    return {
        frames, calls, options: context.options,
        wheel(extra = {}) {
            context.d3.event.sourceEvent = {deltaY: 1, layerX: 50, layerY: 50, ...extra};
            context.zoomed();
        },
        flush() { frames.shift()(); },
    };
}

const pan = viewer();
pan.wheel();
pan.wheel();
assert.equal(pan.frames.length, 1, 'wheel burst schedules one frame');
assert.equal(pan.options.translateY, 230, 'every scroll delta is retained');
assert.equal(pan.options.scaleY, 1, 'plain scrolling preserves scale');
pan.flush();
assert.deepEqual(pan.calls, {layout: 0, transform: 1}, 'pan skips layout');
pan.wheel();
assert.equal(pan.frames.length, 1, 'next frame can be scheduled');

for (const modifier of ['ctrlKey', 'altKey']) {
    const zoom = viewer();
    zoom.wheel({[modifier]: true});
    zoom.wheel();
    assert.equal(zoom.frames.length, 1);
    zoom.flush();
    assert.deepEqual(zoom.calls, {layout: 1, transform: 0}, 'pan must not discard pending zoom');
    assert.ok(zoom.options[modifier === 'ctrlKey' ? 'scaleY' : 'scaleX'] < 1);
}

// Exercise the real transform together with repeated wheel input, including
// recovery after overscrolling and extreme drag translations.
const boundsStart = source.indexOf('        function clampPlotPan(');
assert.ok(boundsStart >= 0);
let translation = [0, 0];
let transform;
const frames = [];
const bounded = {
    d3: {event: {}},
    options: {
        scaleStep: 0.23, scaleX: 1, scaleY: 1, height: 500,
        marginX: 0, marginY: 0, translateX: 0, translateY: 0, lastScale: 0,
    },
    treeHeight: 2000, treeWidth: 400, selectorWidth: 600,
    zoom: {translate: () => translation},
    vis: {
        node: () => ({getBBox: () => ({x: 0, y: 0, width: 400, height: 2000})}),
        attr: (_, value) => { transform = value(); },
    },
    popupReset() {}, zoomLeafTransform() {}, changeLeafVisibility() {},
    highlightSearch() {}, applyLabelGroupTransform() {},
    requestAnimFrame: fn => frames.push(fn),
};
vm.createContext(bounded);
vm.runInContext(source.slice(boundsStart, end), bounded);
for (const direction of [1, -1]) {
    for (let i = 0; i < 200; i++) {
        bounded.d3.event.sourceEvent = {deltaY: direction};
        bounded.zoomed();
        frames.shift()();
    }
    const y = bounded.options.marginY - bounded.options.translateY;
    assert.equal(y, direction === 1 ? -1520 : 20, 'wheel stops at content edge');
}
for (const delta of [1e6, -1e6]) {
    translation = [delta, delta];
    bounded.applyZoomTransform();
    const coordinates = transform.match(/translate\((-?\d+),(-?\d+)\)/).slice(1).map(Number);
    assert.ok(coordinates[0] >= 20 && coordinates[0] <= 180, 'small plot stays inside viewport');
    assert.ok(coordinates[1] >= -1520 && coordinates[1] <= 20, 'tall plot remains reachable');
}

console.log('Wheel scheduling, overscroll recovery and drag bounds passed');
