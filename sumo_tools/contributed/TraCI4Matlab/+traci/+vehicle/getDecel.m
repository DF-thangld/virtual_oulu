function decel = getDecel(vehID)
%getDecel Returns the deceleration of the vehicle.
%   decel = getDecel(VEHID) Returns the maximum deceleration possibility 
%   in m/s^2 of this vehicle.

%   Copyright 2015 Universidad Nacional de Colombia,
%   Politecnico Jaime Isaza Cadavid.
%   Authors: Andres Acosta, Jairo Espinosa, Jorge Espinosa.
%   $Id: getDecel.m 20 2015-03-02 16:52:32Z afacostag $

import traci.constants
decel = traci.vehicle.getUniversal(constants.VAR_DECEL, vehID);