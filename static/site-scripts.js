var is_running = true;
var marker = null;
var map = null;
var markers = [];
var lines = [];
var places = {};
var displaying_line = null;
var place_marker = null;
var nodes = {};
var vehicles = {};
var congested_places = {};

function initialize() {
  var mapProp = {
    center:new google.maps.LatLng(65.007234, 25.482090),
    zoom:12,
    mapTypeId:google.maps.MapTypeId.ROADMAP
  };
  map=new google.maps.Map(document.getElementById("map_area"),mapProp);

  // double click event to create congestion
  map.addListener('click', function(e) {
    $.ajax({
        url: server + "congest_edge/" + e.latLng.lat().toString() + '/' + e.latLng.lng().toString(),
        cache: false,
        dataType: "json",
        success: function(data)
        {
            console.log(data);
            if (data['edges'].length > 0)
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(data['lat_lon']['lat'], data['lat_lon']['lon']),
                    map: map,
                    icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',
                });
        }
    });
  });

  // populate data to places combobox
  /*$.ajax({
        url: server + "get_places",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            var select = document.getElementById("places_combobox");
            $.each(data, function( index, place ) {
                places['place_' + place['id']] = place;
                var opt = document.createElement('option');
                opt.value = 'place_' + place['id'];
                opt.innerHTML = place['name'];
                select.appendChild(opt);
            });
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
  });*/

}
google.maps.event.addDomListener(window, 'load', initialize);

function display_edge(edge)
{
    if (displaying_line != null)
        displaying_line.setMap(null);
    path = [];
    if (edge['shape'] == '' || edge['shape'] == null)
    {
        path = [
         new google.maps.LatLng(edge['from_lat'], edge['from_lon']),
         new google.maps.LatLng(edge['to_lat'], edge['to_lon'])
        ];

    }
    else
    {
        coordinates = edge['shape'].split(" ");
        for (var i = 0; i < coordinates.length; i++) {
            lat_lon = coordinates[i].split(',');
            path.push(new google.maps.LatLng(lat_lon[0], lat_lon[1]));
        }
    }
    var edgePath = new google.maps.Polyline({
        path: path,
        geodesic: true,
        strokeColor: '#FF0000',
        strokeOpacity: 1.0,
        strokeWeight: 2
    });

    edgePath.setMap(map);
    displaying_line = edgePath;
}

function format_time(time_in_second)
{
    time_in_second = Math.floor(time_in_second);
    time_in_second = time_in_second - Math.floor(time_in_second/24/3600)*24*3600;
    current_hour = Math.floor(time_in_second/3600);
    current_minute = Math.floor((time_in_second - current_hour*3600)/60);
    current_second = time_in_second - current_hour*3600 - current_minute*60;
    var result = '';
    if (current_hour >= 10)
        result += current_hour.toString() + ':';
    else
        result += '0' + current_hour.toString() + ':';
    if (current_minute >= 10)
        result += current_minute.toString() + ':';
    else
        result += '0' + current_minute.toString() + ':';
    if (current_second >= 10)
        result += current_second.toString();
    else
        result += '0' + current_second.toString();
    return result;
}

function refresh_car()
{
    $.ajax({
        url: server + "vehicles_positions.php",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            console.log(data);
            $('#current_time').html('Simulating time: ' + format_time(data['time']/1000));

            $.each(vehicles, function( index, vehicle ) {
                vehicle.processed = false;
            });
            $.each(congested_places, function( index, place ) {
                place.processed = false;
            });

            //process received vehicles
            $.each(data['vehicles_positions'], function( index, vehicle ) {
                var vehicle_object = vehicles[vehicle.vehicle_id];

                if (typeof(vehicle_object) == 'undefined') { //new vehicle

                    var marker = new google.maps.Marker({
                        position: new google.maps.LatLng(vehicle['lat'], vehicle['lon']),
                        map: map
                    });
                    marker.vehicle_id = vehicle.vehicle_id
                    marker.processed = true;
                    vehicles[vehicle.vehicle_id] = marker;
                }
                else { //old vehicle => only move place
                    vehicle_object.setPosition( new google.maps.LatLng( vehicle['lat'], vehicle['lon'] ) );
                    vehicle_object.processed = true;
                }
            });

            //remove old vehicle
            $.each(vehicles, function( index, vehicle ) {
                if (!vehicle.processed) {
                    vehicle.setMap(null);
                    vehicles[vehicle.vehicle_id] = null;
                    delete vehicles[vehicle.vehicle_id];
                }
            });

            //display congested places
            $.each(data['congested_places'], function( index, place ) {

                var place_object = congested_places[place.id];

                if (typeof(place_object) == 'undefined') { //new congested place

                    var infowindow = new google.maps.InfoWindow({
                        content: "<a href='javascript:delete_congestion(\"" + place.id + "\");'>Delete congestion</a>"
                    });

                    var marker = new google.maps.Marker({
                        position: new google.maps.LatLng(place['lat'], place['lon']),
                        map: map,
                        icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png'
                    });
                    marker.addListener('click', function() {
                        infowindow.open(map, marker);
                    });

                    marker.id = place.id;
                    marker.processed = true;
                    congested_places[place.id] = marker;
                }
                else { //old vehicle => only move place
                    place_object.setPosition( new google.maps.LatLng( place['lat'], place['lon'] ) );
                    place_object.processed = true;
                }



                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(place['lat'], place['lon']),
                    map: map,
                    icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png'
                });
            });

            //remove old congested places
            $.each(congested_places, function( index, place ) {
                if (!place.processed) {
                    place.setMap(null);
                    place[place.id] = null;
                    delete congested_places[place.id];
                }
            });


            /*for (var i = 0; i < markers.length; i++) {
                markers[i].setMap(null);
            }

            // TODO: add new markers to the map
            markers = []
            $.each(data['vehicles_positions'], function( index, vehicle ) {
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(vehicle['lat'], vehicle['lon']),
                    map: map
                });

                markers.push(marker);
            });

            $.each(data['congested_places'], function( index, place ) {
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(place['lat'], place['lon']),
                    map: map,
                    icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png'
                });

                markers.push(marker);
            });
            //refresh_car();*/
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
            //refresh_car()
        }
    });
}

function delete_congestion(congestion_id) {
    $.ajax({
        url: server + "delete_congestion/" + congestion_id,
        cache: false,
        dataType: "json",
        success: function(data)
        {
            console.log(data);
            /*if (data['edges'].length > 0)
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(data['lat_lon']['lat'], data['lat_lon']['lon']),
                    map: map,
                    icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png',
                });*/
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });
}

function display_nodes()
{
    $.ajax({
        url: server + "get_nodes",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            $.each(data, function( index, node ) {
                nodes[node['id']] = {'id': node['id'], 'lat': node['lat'], 'lon': node['lon']};
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(node['lat'], node['lon']),
                    map: map
                });

                var infowindow = new google.maps.InfoWindow({
                    content: '<div>' + node['id'] + '</div>'
                });
                google.maps.event.addListener(marker, 'click', function() {
                    infowindow.open(map,marker);
                });

            });
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });

}

function display_lines()
{
    var nodes = {};
    $.ajax({
        url: server + "get_nodes",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            $.each(data, function( index, node ) {
                nodes[node['id']] = {'id': node['id'], 'lat': node['lat'], 'lon': node['lon']};
            });
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });
    $.ajax({
        url: server + "get_edges",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            //console.log(data);
            $.each(data, function( index, edge ) {
                path = [];
                if (edge['shape'] == null)
                {
                    node_from = nodes[edge['from']];
                    node_to = nodes[edge['to']];
                    path = [
                     new google.maps.LatLng(node_from['lat'], node_from['lon']),
                     new google.maps.LatLng(node_to['lat'], node_to['lon'])];

                }
                else
                {
                    coordinates = edge['shape'].split(" ");
                    for (var i = 0; i < coordinates.length; i++) {
                        lat_lon = coordinates[i].split(',');
                        path.push(new google.maps.LatLng(lat_lon['lat'], lat_lon['lon']));
                    }
                }
                var edgePath = new google.maps.Polyline({
                    path: path,
                    geodesic: true,
                    strokeColor: '#FF0000',
                    strokeOpacity: 1.0,
                    strokeWeight: 2
                });

                edgePath.setMap(map);
                lines.push(edgePath);
            });
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });
}

function display_place()
{
    console.log(places[document.getElementById('places_combobox').value]);
    var place = places[document.getElementById('places_combobox').value];
    display_edge(place);
    if (place_marker != null)
        place_marker.setMap(null);

    place_marker = new google.maps.Marker({
        position: new google.maps.LatLng(place['lat'], place['lon']),
        icon: 'http://maps.google.com/mapfiles/ms/icons/blue-dot.png',
        map: map
    });

    map.panTo(new google.maps.LatLng(place['lat'], place['lon']));

}

$(document).ready(function() {
    setInterval(function () {
        if (is_running) {
            refresh_car();
        }

    }, 1000);
});