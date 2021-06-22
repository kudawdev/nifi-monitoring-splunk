require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function (mvc) {

    // get default token model
    var tokens = mvc.Components.getInstance("default");
    var host = document.getElementById("host");

    // Set required style if init value is undefined to channel
    if (tokens.get("host") === undefined){
        host.classList.add("required");
    }

    // Set required style if init value is undefined to direction
    // if (tokens.get("tokCommerce") === undefined){
    //     direction.classList.add("required");
    //  }

    
    // Dropdown change on channel 
    tokens.on("change:host", function(model, value) {
        if (value === undefined){
            host.classList.add("required");
        } else {
            host.classList.remove("required");
        }
    });

    // Dropdown change on commerce 
    // tokens.on("change:tokCommerce", function(model, value) {
    //    if (value === undefined){
    //        commerce.classList.add("required");
    //    } else {
    //        commerce.classList.remove("required");
    //    }
    // });


});