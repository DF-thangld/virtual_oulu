function trackVehicle(viewID, vehID)
%trackVehicle Track vehicle in SUMO gui.
%   trackVehicle(viewID, vehID) Start visually tracking the given vehicle 
%   on the given view.

%   Copyright 2015 Universidad Nacional de Colombia,
%   Politecnico Jaime Isaza Cadavid.
%   Authors: Andres Acosta, Jairo Espinosa, Jorge Espinosa.
%   $Id: trackVehicle.m 20 2015-03-02 16:52:32Z afacostag $

import traci.constants
traci.sendStringCmd(constants.CMD_SET_GUI_VARIABLE, constants.VAR_TRACK_VEHICLE, viewID, vehID);