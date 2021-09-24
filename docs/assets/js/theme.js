/*
 * Initialize custom dropdown component
 */
var dropdowns = document.getElementsByClassName('md-tabs__dropdown-link');
var dropdownItems = document.getElementsByClassName('mb-tabs__dropdown-item');


function getLang(){
  return window.location.pathname.split("/")[1]
}

function getVersion(){
  return window.location.pathname.split("/")[2]
}


function getURL(lang, version, params){
  if (!lang){
    lang = params.lang.default;
  }
  if (!version){
    version = params.version.default;
  }
  var url = window.location.origin + '/' +lang + '/' + version;
  return url
}

function indexInParent(node) {
    var children = node.parentNode.childNodes;
    var num = 0;
    console.log("indexInParent");
    for (var i=0; i < children.length; i++) {
         if (children[i]==node) return num;
         if (children[i].nodeType==1) num++;
    }
    return -1;
}

for (var i = 0; i < dropdowns.length; i++) {
    var el = dropdowns[i];
    var openClass = 'open';
    console.log("for");
    el.onclick = function () {
        if (this.parentElement.classList) {
            this.parentElement.classList.toggle(openClass);
        } else {
            var classes = this.parentElement.className.split(' ');
            var existingIndex = classes.indexOf(openClass);

            if (existingIndex >= 0)
                classes.splice(existingIndex, 1);
            else
                classes.push(openClass);

            this.parentElement.className = classes.join(' ');
        }
    };
};



/* 
 * Reading Lang
 */

var docSetUrl = window.location.origin + '/'
var request2 = new XMLHttpRequest();

request2.open('GET', docSetUrl + 'params.json', true);

request2.onload = function() {
  if (request2.status >= 200 && request2.status < 400) {

      var data = JSON.parse(request2.responseText);
      var dropdown =  document.getElementById('lang-select-dropdown');
      /* 
       * Appending lang to the lang selector dropdown 
       */
      if (dropdown){
          data.lang.list.forEach(function(key, index){
              var langData = data.lang.list;

              if(langData) {
                  var liElem = document.createElement('li');
                  var langName = data.lang.list[index].name;
                  var target = '_self';
                  var url = getURL(langName, getVersion(), data)

                  liElem.className = 'md-tabs__item mb-tabs__dropdown';
                  liElem.innerHTML =  '<a href="' + url + '" target="' + target + '">' + langName + '</a>';

                  dropdown.insertBefore(liElem, dropdown.firstChild);
              }
          });
      }
  } else {
      console.error("We reached our target server, but it returned an error");
  }
};

request2.onerror = function() {
    console.error("There was a connection error of some sort");
};

request2.send();




/* 
 * Reading versions
 */

var docSetUrl = window.location.origin + '/'
var request = new XMLHttpRequest();

request.open('GET', docSetUrl + 'params.json', true);

request.onload = function() {
  if (request.status >= 200 && request.status < 400) {

      var data = JSON.parse(request.responseText);
      var dropdown =  document.getElementById('version-select-dropdown');
      
      /* 
       * Appending versions to the version selector dropdown 
       */
      if (dropdown){
          data.version.list.reverse().forEach(function(key, index){
              var versionData = data.version.list[index];
              
              if(versionData) {
                  var liElem = document.createElement('li');
                  var versionName = data.version.list[index].name;
                  var target = '_self';
                  var url = getURL(getLang(), versionName, data);
                  
                  liElem.className = 'md-tabs__item mb-tabs__dropdown';
                  liElem.innerHTML =  '<a href="' + url + '" target="' + target + '">' + versionName + '</a>';

                  dropdown.insertBefore(liElem, dropdown.firstChild);
              }
          });
      }
  } else {
      console.error("We reached our target server, but it returned an error");
  }
};

request.onerror = function() {
    console.error("There was a connection error of some sort");
};

request.send();




