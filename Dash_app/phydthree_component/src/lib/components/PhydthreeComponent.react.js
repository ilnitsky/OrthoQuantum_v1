import React, { Component } from 'react';
import PropTypes from 'prop-types';

/**
 * ExampleComponent is an example component.
 * It takes a property, `label`, and
 * displays it.
 * It renders an input with the property `value`
 * which is editable by the user.
 */
export default class PhydthreeComponent extends Component {
    constructor(props) {
        super(props);
        this.url = this.props.url;
        this.ref = React.createRef();
        this.callback = null;
    }
    componentDidUpdate() {
        this.redraw()
    }
    componentDidMount() {
        // listen for resize events
        window.addEventListener('resize', this.handleResize.bind(this))
        this.redraw()
    }
    handleResize() {
        // debounce resize events (redraw at most once per second)
        if (this.callback != null){
            clearTimeout(this.callback)
        }
        this.callback = setTimeout(this.resizeComponent.bind(this), 1000);
    }
    resizeComponent() {
        // do actual resizing
        this.forceUpdate();
        this.callback = null;
    }
    componentWillUnmount() {
        window.removeEventListener('resize', this.handleResize.bind(this));
        if (this.callback != null){
            clearTimeout(this.callback)
        }
    }
    redraw() {
        var ref = this.ref;
        var opts = {
            dynamicHide: false,
            height: 2000,
            invertColors: false,
            lineupNodes: true,
            showDomains: false,
            showDomainNames: false,
            showDomainColors: true,
            showGraphs: true,
            showGraphLegend: true,
            showLength: false,
            showNodeNames: true,
            showNodesType: "only leaf",
            nodeHeight: 10,
            scaleY:3,
            showPhylogram: true,
            showTaxonomy: false,
            showFullTaxonomy: false,
            showSequences: false,
            showLabels: false,
            showTaxonomyColors: false,
            backgroundColor: "#f5f5f5",
            foregroundColor: "#000000",
            nanColor: "#f5f5f5",
        };
        // vv url from props
        d3.xml(this.props.url, function (err, xml) {
            if (err != null){
                d3.select(ref.current).text("Error");
            }else{
                var tree = phyd3.phyloxml.parse(xml);
                phyd3.phylogram.build(ref.current, tree, opts);
            }
        });
    }

    render() {
        return (
            <div ref={this.ref} id="phyd3"></div>
        );
    }

}

PhydthreeComponent.defaultProps = {};

PhydthreeComponent.propTypes = {
    /**
     * A label that will be printed when this component is rendered.
     */
    url: PropTypes.string.isRequired,
};
