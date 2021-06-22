require([
    'underscore',
    'jquery',
    'splunkjs/mvc',
    'splunkjs/mvc/tableview',
    'splunkjs/mvc/simplexml/ready!'
], function(_, $, mvc, TableView) {

    var CustomIconRenderer = TableView.BaseCellRenderer.extend({
        canRender: function(cell) {
            return cell.field;
        },

         render: function($td, cell) {
            var cell_td = cell.field;
            var value = cell.value;
            var icon; 

            if (cell_td === 'status'){

                if (value == 'Up') {

                    $td.addClass('icon-inline numeric').html(_.template('<span class=\'green\'><%- text %></span>', {
                    icon: icon,
                    text: cell.value
                    }));

                } else if (value == 'Down') {

                    $td.addClass('icon-inline numeric').html(_.template('<span class=\'red\'><%- text %></span>', {
                    icon: icon,
                    text: cell.value
                    }));

                }

            } else if (cell_td == 'Active Threads'){

                if (value != null) {
                    // Icon name
                    icon = 'icon-distributed-environment'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Total Queued Data') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-list'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

             } else if (cell_td == 'Transmitting Remote Process Group') {

                 if (value != null) {
                    // Icon name
                    icon = 'icon-boolean'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                 }


             } else if (cell_td == 'Not Transmitting Remote Process Group') {

                 if (value != null) {
                    // Icon name
                    icon = 'icon-circle'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                 }
            
            } else if (cell_td == 'Running Components') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-triangle-right'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

             } else if (cell_td == 'Stopped Components') {

                 if (value != null) {
                    // Icon name
                    icon = 'icon-box-filled'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                 }

             } else if (cell_td == 'Invalid Components') {

                 if (value != null) {
                    // Icon name
                    icon = 'icon-alert'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                 }

            } else if (cell_td == 'Disabled Components') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-minus-circle'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Up To Date Versioned Process Group') {

                if (value !=null ) {
                    // Icon name
                    icon = 'icon-check'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Locally Modified Versioned Process Group') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-star'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Stale Versioned Process Group') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-arrow-up'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    })); 

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Locally Modified And Stale Versioned Process Group') {

                if (value != null) {
                    // Icon name
                    icon = 'icon-info-circle'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }
            
            } else if (cell_td == 'Sync Failure Versioned Process Group') {
                

                if (value != null) {
                    // Icon name
                    icon = 'icon-question'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else if (cell_td == 'Bulletin Errors') {
                // Icon name

                if (value > 0) {
        
                    icon = 'icon-report'
                    
                    $td.addClass('icon-inline numeric').html(_.template('<span data-toggle="tooltip" data-placement="top" title="<%- cell_td %>"><i class="<%-icon%>"></i> <%- text %></span>', {
                        icon: icon,
                        text: cell.value,
                        cell_td: cell_td
                    })); 

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else {
                // columns without icons
                 $td.addClass('icon-inline numeric').html(_.template('<%- text %>', {
                    icon: icon,
                    text: cell.value
                }));

            }
        }
    });

    var DataBarCellRenderer = TableView.BaseCellRenderer.extend({
        canRender: function(cell){
            return cell.field;
        },

        render: function($td, cell){

            var cell_td = cell.field;
            var value = cell.value;

            if (cell_td == 'Content %'){

                if (value != null){

                    $td.addClass('data-bar-cell').html(_.template('<div class="data-bar-wrapper" data-toggle="tooltip" data-placement="top" title="<%- percent %>"><div class="data-bar" style="width:<%- percent %>"></div></div>', {
                        percent: value
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();

                }

            } else if (cell_td == 'Flow %'){

                if (value != null){
                    $td.addClass('data-bar-cell').html(_.template('<div class="data-bar-wrapper" data-toggle="tooltip" data-placement="top" title="<%- percent %>"><div class="data-bar" style="width:<%- percent %>"></div></div>', {
                        percent: value
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

             } else if (cell_td == 'Provenance %'){

                if (value != null){
                    $td.addClass('data-bar-cell').html(_.template('<div class="data-bar-wrapper" data-toggle="tooltip" data-placement="top" title="<%- percent %>"><div class="data-bar" style="width:<%- percent %>"></div></div>', {
                        percent: value
                    }));

                    $td.children('[data-toggle="tooltip"]').tooltip();
                }

            } else {
                $td.html(_.template('<%- text %>', {
                    text: cell.value
                }));
            }

        }
    })


    mvc.Components.get('table_nifi_status').getVisualization(function(tableView){
        // Register custom cell renderer, the table will re-render automatically
        tableView.addCellRenderer(new CustomIconRenderer());
        tableView.table.render();

/* 
        tableView.on('rendered', function() {
            setTimeout(function() {
                $("#table_nifi_status th").html(_.template(' '));
            }, 100);
        });
        */


    });

    mvc.Components.get('table_disk_space_status').getVisualization(function(tableView){
        tableView.addCellRenderer(new DataBarCellRenderer());
    })
});