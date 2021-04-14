# AUTO GENERATED FILE - DO NOT EDIT

phydthreeComponent <- function(url=NULL) {
    
    props <- list(url=url)
    if (length(props) > 0) {
        props <- props[!vapply(props, is.null, logical(1))]
    }
    component <- list(
        props = props,
        type = 'PhydthreeComponent',
        namespace = 'phydthree_component',
        propNames = c('url'),
        package = 'phydthreeComponent'
        )

    structure(component, class = c('dash_component', 'list'))
}
