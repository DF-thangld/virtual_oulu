var is_running = true;
//var marker = null;
var map = null;
var markers = [];
var lines = [];
var places = {};
var displaying_line = null;
//var place_marker = null;
var nodes = {};
var vehicles = {};
var congested_places = {};
var infowindow = null;
var dragging_marker = null;

/* obsolete functions, not in use anymore */
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

function display_traffic_lights()
{
    var results = [];
    $.ajax({
        url: server + "get_traffic_lights",
        cache: false,
        dataType: "json",
        success: function(data)
        {
            console.log(data);
            $.each(data, function( index, traffic_light ) {
                var marker = new google.maps.Marker({
                    position: new google.maps.LatLng(traffic_light['lat'], traffic_light['lon']),
                    map: map,
                    optimized: false,
                    draggable:true,
                    icon: 'http://maps.google.com/mapfiles/ms/icons/green-dot.png'
                });

                google.maps.event.addListener(marker, "click", function(event) {
                    if (infowindow) {
                        infowindow.close();
                    }
                    infowindow = new google.maps.InfoWindow({
                        content: "Traffic light ID: " + traffic_light['tl'] + "<br/>Node ID: " + traffic_light['node_id']
                    });
                    infowindow.open(map, marker);
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
/* obsolete functions, not in use anymore */

function initialize() {
    var mapProp = {
        center:new google.maps.LatLng(65.007234, 25.482090),
        zoom:12,
        mapTypeId:google.maps.MapTypeId.ROADMAP
    };
    map = new google.maps.Map(document.getElementById("map_area"),mapProp);

    // refresh data every second
    setInterval(function () {
        if (is_running) {
            refresh_car();
        }
    }, 1000);

    google.maps.event.addListener(map, "mousedown", function(event) {
        if (infowindow) {
            infowindow.close();
        }
    });

    // rightclick event
    google.maps.event.addListener(map, "rightclick", function(event) {
        var lat = event.latLng.lat();
        var lng = event.latLng.lng();
        // populate yor box/field with lat, lng

        if (infowindow) {
            infowindow.close();
        }

        infowindow = new google.maps.InfoWindow({
          content: '<a style="text-decoration:underline; cursor: pointer;" onclick="add_congestion(' + lat.toString() + ', ' + lng.toString() + '); return false;">Add congestion</a>'
        });
        infowindow.setPosition(event.latLng);

        infowindow.open(map);

    });
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
            $('#current_time').html('Simulating time: ' + format_time(data['time']/1000));
            $('#more-info').html('Number of running vehicle(s): ' + data['vehicles_positions'].length.toString());
            $.each(vehicles, function( index, vehicle ) {
                if (vehicle) {
                    vehicle.processed = false;
                }

            });
            $.each(congested_places, function( index, place ) {
                if (place) {
                    place.processed = false;
                }

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
                if (typeof(place_object) == 'undefined') //new congested place
                {
                    _add_congestion_marker(place.id, place['lat'], place['lon']);
                }
                else { //old congestion => only move place
                    if (!place_object.dragging) {
                        place_object.setPosition( new google.maps.LatLng( place['lat'], place['lon'] ) );
                        place_object.processed = true;
                    }
                    else {
                        console.log('dragging');
                    }
                }
            });

            //remove old congested places
            var deleted_congestion = [];
            $.each(congested_places, function( index, place ) {
                if (place && (!place.processed && !place.dragging)) {
                    deleted_congestion.push(place.id);
                }
            });

            for (i = 0; i < deleted_congestion.length; i++) {
            console.log('delete marker', deleted_congestion[i]);
                congested_places[deleted_congestion[i]].setMap(null);
                congested_places[deleted_congestion[i]] = null;
                delete congested_places[deleted_congestion[i]];
            }

        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });
}

function delete_congestion(congestion_id)
{
    $.ajax({
        url: server + "delete_congestion/" + congestion_id,
        cache: false,
        dataType: "json",
        success: function(data)
        {
            if (infowindow) {
                infowindow.close();
            }
            congested_places[congestion_id].setMap(null);
            congested_places[congestion_id] = null;
            delete congested_places[congestion_id];
        },
        error: function (xhr, ajaxOptions, thrownError)
        {
            console.log(xhr);
            console.log(ajaxOptions);
            console.log(thrownError);
        }
    });
}

function add_congestion(lat, lng)
{
    $.ajax({
        url: server + "congest_edge/" + lat.toString() + '/' + lng.toString(),
        cache: false,
        dataType: "json",
        success: function(data)
        {
            if (infowindow) {
                infowindow.close();
            }

            _add_congestion_marker(data.id, lat, lng);
        }
    });
}

function _add_congestion_marker(id, lat, lng) {
    var marker = new google.maps.Marker({
        position: new google.maps.LatLng(lat, lng),
        map: map,
        optimized: false,
        draggable:true,
        icon: 'http://maps.google.com/mapfiles/ms/icons/yellow-dot.png'
    });

    google.maps.event.addListener(marker, "rightclick", function(event) {
        if (infowindow) {
            infowindow.close();
        }
        infowindow = new google.maps.InfoWindow({
            content: "<a style='color:black;' href='javascript:delete_congestion(\"" + id + "\");'>Delete congestion</a>"
        });
        infowindow.open(map, marker);
    });

    google.maps.event.addListener(marker, "dragstart", function(event) {
        if (infowindow) {
            infowindow.close();
        }
        dragging_marker = marker.id;
    });
    google.maps.event.addListener(marker, "dragend", function(event) {

        $.ajax({
            url: server + "update_congest/" + marker.id + "/" + event.latLng.lat().toString() + '/' + event.latLng.lng().toString(),
            cache: false,
            dataType: "json",
            success: function(data)
            {
            }
        });
        dragging_marker = null;
    });

    marker.id = id;
    marker.processed = true;
    congested_places[id] = marker;
}

google.maps.event.addDomListener(window, 'load', initialize);

