import React, { Component } from 'react';
import PropTypes from 'prop-types';
import { Nav, NavItem, NavLink, Input, Button, Label } from 'reactstrap';


function delSVG(svg_item) {
  d3.select(svg_item).html(null);
}

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
    this.ref = React.createRef();
    this.svg_ref = React.createRef();
    this.callback = null;
    this.state = {
      activeTab: "tree",
      nextTab: "",
      firstRender: true,
      shouldRedraw: false, // on mount redraws anyway
      nextTab: null,
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
    var changed = false;
    var activeTab = this.state.activeTab;
    var nextTab = this.state.nextTab;
    var shouldRedraw = this.state.shouldRedraw;
    if (this.state.version != this.props.version){
      shouldRedraw = true;
      nextTab = "tree";// this.props.leafCount < 1000 ? "tree" : "svg";
      changed = true;
    }
    switch (nextTab) {
      case "tree":
        delSVG(this.svg_ref.current);
        if (shouldRedraw){
          this.redraw();
        }
        activeTab = "tree";
        changed = true;
        break;
      case "svg":
        if (this.state.activeTab !== "svg"){
          phyd3.phylogram.renderSVG(this.svg_ref.current);
        }
        activeTab = "svg";
        changed = true;
        break;
      default:
        if (shouldRedraw && activeTab == "tree"){
          this.redraw();
          changed = true;
          // this.setState((state) => {
          //   return { ...state, shouldRedraw: false }
          // });
        };
    }
    if (changed) {
      this.setState((state) => {
        return { ...state, shouldRedraw: false, firstRender:false, activeTab: activeTab, nextTab: null, version: this.props.version }
      })
    }


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
    delSVG(this.svg_ref.current);
    delSVG(this.ref.current);
  }



  redraw() {
    if (this.props.version == ""){
      delSVG(this.svg_ref.current);
      delSVG(this.ref.current);
      return;
    }

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
      taskid_for_links: this.props.taskid_for_links,

    };
    if (this.state.showGroups && this.state.showSpecies){
      opts.showNodesType = "all";
    } else if (this.state.showGroups){
      opts.showNodesType = "only inner";
    }

    // vv url from props
    d3.xml(`${this.props.url}?version=${this.props.version}`, (err, xml) => {
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

    return this.props.version == "" ? null : <>
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
            onClick={() => { phyd3.phylogram.renderPNG(); }}
          >
            Download image
          </NavLink>
        </NavItem>
        {
          this.props.show_download_csv &&
          <NavItem>
            <NavLink onClick={() => {
              this.props.setProps({csv_render_n: this.props.csv_render_n+1});
            }}>
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
  csv_render_n: 0,
  leafCount: 0,
  version: "",
  show_download_csv: true,
};

PhydthreeComponent.propTypes = {
  /**
   * A label that will be printed when this component is rendered.
   */
  id: PropTypes.string,
  url: PropTypes.string.isRequired,
  taskid_for_links: PropTypes.string,

  height: PropTypes.number.isRequired,

  leafCount: PropTypes.number,
  version: PropTypes.string,
  show_download_csv: PropTypes.bool,

  csv_render_n: PropTypes.number,

  setProps: PropTypes.func,
};
