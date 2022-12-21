$(document).ready(function(){
    function myfun(){
    fetch('tst')
        .then(response => response.json())  // convert to json
        .then(function(json) {
            $('#log').html(json['body'])
          });
    }
    myfun()
    // a = setInterval(myfun, 30000);  

});