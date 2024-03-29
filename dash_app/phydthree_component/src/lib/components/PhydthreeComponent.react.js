import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Nav, NavItem, NavLink, Input, Button, Label } from 'reactstrap';


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
      firstRender: true,
      shouldRedraw: false, // on mount redraws anyway
      nextTab: props.leafCount < 1000 ? null : "svg",
      zoomValue: 100,
      zoomLevel: 1.0,
      displayNames: true,
      version: this.props.version,
      showGroups: false,
      showSpecies: true,
      dynamicHide: false,
    };
  }
  componentDidUpdate() {
    var activeTab = this.state.activeTab;
    var nextTab = this.state.nextTab;
    var shouldRedraw = this.state.shouldRedraw;
    if (this.state.version != this.props.version){
      shouldRedraw = true;
      nextTab = "tree";
    }
    switch (nextTab) {
      case "tree":
        phyd3.phylogram.delSVG(this.svg_ref.current);
        if (shouldRedraw){
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
        if (shouldRedraw && activeTab == "tree"){
          this.redraw();
          this.setState((state) => {
            return { ...state, shouldRedraw: false }
          });
        }
        return;
    }
    this.setState((state) => {
      return { ...state, shouldRedraw: false, firstRender:false, activeTab: activeTab, nextTab: null, version: this.props.version }
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
    d3.select(this.ref.current).html("Loading");
    phyd3.phylogram.delSVG(this.svg_ref.current);
    phyd3.phylogram.delSVG(this.ref.current);
  }
  redraw() {

    const scaleX = 0.4;
    const scaleY = 0.01183*this.props.leafCount;
    var opts = {
      dynamicHide: this.state.dynamicHide,
      height: this.props.height,
      invertColors: false,
      lineupNodes: true,
      showDomains: false,
      showDomainNames: false,
      showDomainColors: true,
      showGraphs: true,
      showGraphLegend: true,
      showLength: false,
      showNodeNames: this.state.showGroups || this.state.showSpecies,
      showNodesType: "only leaf",
      nodeHeight: 10,
      origScaleX: scaleX,
      scaleX: scaleX,
      origScaleY: scaleY,
      scaleY: scaleY,
      scaleStep: 0.23,
      margin: 100,
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
    if (this.state.showGroups && this.state.showSpecies){
      opts.showNodesType = "all";
    } else if (this.state.showGroups){
      opts.showNodesType = "only inner";
    }

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

  transformZoom(zoomVal){
    if (zoomVal>100){
      zoomVal = zoomVal*2 - 100;
    }
    return (zoomVal/100).toFixed(2);
  }


  render() {
    const myScale = `scale(${this.state.zoomLevel})`;
    var csvurl;
    if (this.props.taskid === ""){
      csvurl = "";
    } else {
      csvurl = `/csvdownload?task_id=${this.props.taskid}`;
    }

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
            disabled={this.state.activeTab !== 'tree'}
            onClick={() => { this.toggle('png'); }}
          >
            Download image
          </NavLink>
        </NavItem>
        {
          csvurl !== "" &&
          <NavItem>
            <NavLink href={csvurl} target="_blank">
              Download csv
            </NavLink>
          </NavItem>
        }
      </Nav>


    <div className="tab-content">
      <div style={{height: "56px"}} className="mt-2">
        <div style={{display: this.state.activeTab !== "tree" ? "none" : "inherit"}}>
          <span className="align-top">Show names:</span>
          <div className="align-top d-inline-block">
            <Label check className="ml-4">
              <Input type="checkbox" id="nodeNames" defaultChecked={this.state.showGroups} onClick={e => {
                phyd3.phylogram.updateNodeNames(!this.state.showGroups, this.state.showSpecies);
                this.setState({...this.state, showGroups: !this.state.showGroups});
              }}/>
              Groups
            </Label><br/>
            <Label check className="ml-4">
              <Input type="checkbox" id="nodeNames" defaultChecked={this.state.showSpecies} onClick={e => {
                phyd3.phylogram.updateNodeNames(this.state.showGroups, !this.state.showSpecies);
                this.setState({...this.state, showSpecies: !this.state.showSpecies});
              }}/>
              Species
            </Label>
          </div>
          <div className="ml-4 align-top d-inline-block">
            <Label check className="ml-4">
              <Input type="checkbox" id="dynamicHide" defaultChecked={this.state.dynamicHide} onClick={e => {this.setState({...this.state, dynamicHide: !this.state.dynamicHide})}}/>
              Dynamic hide
            </Label>
          </div>
          <Button id="resetZoom" className="ml-4 align-top">Reset Zoom</Button>
          <Button id="resetPos" className="ml-2 align-top">Reset Position</Button>
          <Button id="fitTree" className="ml-2 align-top">Fit Tree To View</Button>
        </div>

        <div style={{display: this.state.activeTab !== "svg" ? "none" : "inherit"}}>
          <Input type="range" name="range" id="exampleRange"
                  min="1" max="200" step="1" value={this.state.zoomValue}
                  onChange={e => this.setState({...this.state, zoomValue: parseInt(e.target.value)})}
                  onMouseUp={e => this.setState({...this.state, zoomLevel: this.transformZoom(this.state.zoomValue)})}/>
          <span>{this.transformZoom(this.state.zoomValue)}x</span>
        </div>
      </div>
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
            transformOrigin: "0 0",
            transform: myScale,
          }}
        ></div>
      </div>
    </div>
    </>;
  }

}

PhydthreeComponent.defaultProps = {
  taskid: "",
};

PhydthreeComponent.propTypes = {
  /**
   * A label that will be printed when this component is rendered.
   */
  url: PropTypes.string.isRequired,
  taskid: PropTypes.string,
  height: PropTypes.number.isRequired,
  leafCount: PropTypes.number.isRequired,
  version: PropTypes.number.isRequired,
};
