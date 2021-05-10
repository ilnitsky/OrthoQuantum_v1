import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { TabContent, TabPane, Nav, NavItem, NavLink, Card, Button, CardTitle, CardText, Row, Col } from 'reactstrap';


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
    this.svg_ref = React.createRef();
    this.callback = null;
    this.state = {
      activeTab: "tree",
      nextTab: "",
      shouldRedraw: false, // on mount redraws anyway
      nextTab: null,

    };
  }
  componentDidUpdate() {
    var activeTab = this.state.activeTab;
    switch (this.state.nextTab) {
      case "tree":
        if (this.state.shouldRedraw){
          this.redraw();
        }
        activeTab = "tree";
        break;
      case "svg":
        if (this.state.activeTab !== "svg"){
          phyd3.phylogram.renderSVG(this.svg_ref.current);
        }
        activeTab = "svg";
        break;
      case "png":
        phyd3.phylogram.renderPNG();
      default:
        return;
    }
    this.setState((state) => {
      return { ...state, shouldRedraw: false, activeTab: activeTab, nextTab: null }
    });

  }
  componentDidMount() {
    // listen for resize events
    window.addEventListener('resize', this.handleResize.bind(this))
    this.redraw()
  }
  handleResize() {
    // debounce resize events (redraw at most once per second)
    if (this.callback != null) {
      clearTimeout(this.callback)
    }
    this.callback = setTimeout(this.resizeComponent.bind(this), 1000);
  }
  resizeComponent() {
    // do actual resizing
    this.setState((state) => {
      return { ...state, shouldRedraw: true }
    });
    this.callback = null;
  }
  componentWillUnmount() {
    window.removeEventListener('resize', this.handleResize.bind(this));
    if (this.callback != null) {
      clearTimeout(this.callback)
    }
  }
  redraw() {
    var opts = {
      dynamicHide: false,
      height: this.props.height,
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
      scaleY: 3,
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
    d3.xml(this.props.url, (err, xml) => {
      if (err != null) {
        d3.select(this.ref.current).text("Error");
      } else {
        var tree = phyd3.phyloxml.parse(xml);
        d3.select(this.ref.current).html("Loading");
        phyd3.phylogram.build(this.ref.current, tree, opts);
      }
    });
  }
  toggle(newActiveTab) {
    if (this.state.activeTab === newActiveTab) {
      return
    }
    this.setState((state) => {
      return {
        ...state,
        nextTab: newActiveTab,
      };
    });
  }


  render() {
    return <>
      <Nav tabs>
        <NavItem>
          <NavLink
            className={this.state.activeTab === 'tree' ? "active" : ""}
            onClick={() => { this.toggle('tree'); }}
          >
            Interactive graph
          </NavLink>
        </NavItem>
        <NavItem>
          <NavLink
            className={this.state.activeTab === 'svg' ? "active" : ""}
            onClick={() => { this.toggle('svg'); }}
          >
            Static image
          </NavLink>
        </NavItem>
        <NavItem className="ml-auto">
          <NavLink
            onClick={() => { this.toggle('png'); }}
          >
            Download image
          </NavLink>
        </NavItem>
      </Nav>


    <div className="tab-content">
      <div
        ref={this.ref}
        id="phyd3"
        className={"tab-pane fade" + (this.state.activeTab === "tree" ? "show active" : "")}></div>
      <div
        className={"tab-pane fade" + (this.state.activeTab === "svg" ? "show active" : "")}
        style={{
          paddingTop: this.props.height,
          overflow: "scroll",
          position: "relative",
        }}
      >
        <div
          ref={this.svg_ref}
          id="phyd3svg"
          style={{
            position: "absolute",
            top: 0,
            left: 0,
          }}
        ></div>
      </div>
    </div>
    </>;
  }

}

PhydthreeComponent.defaultProps = {};

PhydthreeComponent.propTypes = {
  /**
   * A label that will be printed when this component is rendered.
   */
  url: PropTypes.string.isRequired,
  height: PropTypes.number.isRequired,
};
