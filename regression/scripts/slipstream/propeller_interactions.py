# propeller_interactions.py
# 
# Created:  April 2021, R. Erhard
# Modified: 

#----------------------------------------------------------------------
#   Imports
# ----------------------------------------------------------------------

import SUAVE
from SUAVE.Core import Units, Data

from SUAVE.Methods.Aerodynamics.Common.Fidelity_Zero.Lift.generate_propeller_wake_distribution import generate_propeller_wake_distribution
from SUAVE.Methods.Aerodynamics.Common.Fidelity_Zero.Lift.compute_wake_induced_velocity import compute_wake_induced_velocity
from SUAVE.Methods.Aerodynamics.Common.Fidelity_Zero.Lift.compute_propeller_nonuniform_freestream import compute_propeller_nonuniform_freestream
from SUAVE.Plots.Propeller_Plots import plot_propeller_disc_inflow, plot_propeller_disc_performance
from SUAVE.Plots.Geometry_Plots.plot_vehicle import plot_propulsor
import numpy as np
import pylab as plt
import copy
import sys

sys.path.append('../Vehicles/Propellers') 
from APC_10x7_thin_electric import propeller_geometry

def main():
    '''
    This example shows a propeller operating in a nonuniform freestream flow.
    A propeller upstream of another propeller produces a wake, which is accounted 
    for in the analysis of the downstream propeller.
    '''
    #--------------------------------------------------------------------
    #    SETUP
    #--------------------------------------------------------------------
    # flag for plotting results
    plot_flag = True
    
    # set the basic propeller geometry
    vehicle = vehicle_setup()
    prop    = vehicle.propulsors.prop_net.propeller
    
    # set the atmospheric conditions
    conditions = simulation_conditions()
    
    # set the grid and VLM settings
    grid_settings, VLM_settings = simulation_settings(vehicle)
    
    # generate the grid points at the downstream propeller:
    grid_points = generate_propeller_grid(prop, grid_settings, plot_grid=plot_flag)
    
    ## plot the propeller system
    #fig = plt.figure()
    #axes = fig.add_subplot(projection='3d')
    #for propulsor in vehicle.propulsors:  
        #plot_propulsor(axes,propulsor)  
        #axes.set_xlabel('x')
        #axes.set_ylabel('y')
        #axes.set_zlabel('z')
        #axes.set_xlim([-0.5,3.5])
        #axes.set_ylim([-0.5,3.5])
        #axes.set_zlim([-0.5,3.5])
    
    #--------------------------------------------------------------------
    #    ANALYSIS
    #--------------------------------------------------------------------    
    
    # run the BEMT for upstream isolated propeller
    T_iso, Q_iso, P_iso, Cp_iso, outputs_iso , etap_iso = prop.spin(conditions)
    prop.outputs = outputs_iso
    
    T_iso_true, Q_iso_true, P_iso_true, Cp_iso_true, etap_iso_true = 1.23118019, 0.03279611, 15.45480129, 0.04350239, 0.71225347
    
    assert(abs(T_iso-T_iso_true)<1e-6)
    assert(abs(Q_iso-Q_iso_true)<1e-6)
    assert(abs(P_iso-P_iso_true)<1e-6)
    assert(abs(Cp_iso-Cp_iso_true)<1e-6)
    assert(abs(etap_iso-etap_iso_true)<1e-6)
    
    
    # compute the induced velocities from upstream propeller at the grid points on the downstream propeller
    propeller_wake              = compute_propeller_wake(prop, grid_settings, grid_points, plot_velocities=plot_flag)
    
    # run the downstream propeller in the presence of this nonuniform flow
    T, Q, P, Cp, outputs , etap = run_downstream_propeller(prop, propeller_wake, conditions, plot_performance=plot_flag)
    
    T_true, Q_true, P_true, Cp_true, etap_true = 13.02920345,0.6556547,308.96999913,0.86969297,0.37703176
    assert(abs(T-T_true)<1e-6)
    assert(abs(Q-Q_true)<1e-6)
    assert(abs(P-P_true)<1e-6)
    assert(abs(Cp-Cp_true)<1e-6)
    assert(abs(etap-etap_true)<1e-6)    
    
    # Display plots:
    if plot_flag:
        plt.show()
    
    return

def run_downstream_propeller(prop, propeller_wake, conditions, plot_performance=False):
    # assess the inflow at the propeller
    prop_copy = copy.deepcopy(prop)
    prop_copy.nonuniform_freestream = True
    prop_copy.origin = np.array([prop.origin[1] ])# only concerned with the impact the upstream prop has on this one
    prop_copy.rotation = [prop.rotation[1]]
    prop = compute_propeller_nonuniform_freestream(prop_copy, propeller_wake, conditions)
    
    # run the propeller in this nonuniform flow
    T, Q, P, Cp, outputs , etap = prop.spin(conditions)
    
    if plot_performance:
        plot_propeller_disc_performance(prop,outputs)
        
    return T, Q, P, Cp, outputs , etap

def compute_propeller_wake(prop,grid_settings,grid_points, plot_velocities=True):
    
    x_plane = prop.origin[1,0] #second propeller, x-location
    
    # generate the propeller wake distribution for the upstream propeller
    prop_copy = copy.deepcopy(prop)
    prop_copy.origin = np.array([prop.origin[0]])
    prop_copy.rotation = [prop.rotation[0]]
    VD                       = Data()
    cpts                     = 1 # only testing one condition
    number_of_wake_timesteps = 80
    init_timestep_offset     = 0
    time                     = 2.55
    
    WD, dt, ts, B, Nr  = generate_propeller_wake_distribution(prop_copy,cpts,VD,init_timestep_offset, time, number_of_wake_timesteps )
    
    # compute the wake induced velocities:
    VD.YC   = grid_points.ymesh
    VD.ZC   = grid_points.zmesh
    VD.XC   = x_plane*np.ones_like(VD.YC)
    VD.n_cp = np.size(VD.YC)
    V_ind   = compute_wake_induced_velocity(WD, VD, cpts)
    u       = V_ind[0,:,0]
    v       = V_ind[0,:,1]
    w       = V_ind[0,:,2]
    
    propeller_wake = Data()
    propeller_wake.u_velocities  = u
    propeller_wake.v_velocities  = v
    propeller_wake.w_velocities  = w
    propeller_wake.VD            = VD
    
    if plot_velocities:
        # plot the velocities input to downstream propeller
        plot_propeller_disc_inflow(prop,propeller_wake,grid_points)
        
    
    return propeller_wake

def generate_propeller_grid(prop, grid_settings, plot_grid=True):
    
    R         = grid_settings.radius
    Rh        = grid_settings.hub_radius
    Nr        = grid_settings.Nr
    Na        = grid_settings.Na
    grid_mode = grid_settings.grid_mode
    Ny        = grid_settings.Ny
    Nz        = grid_settings.Nz
    psi_360   = np.linspace(0,2*np.pi,Na+1)
    influencing_prop = prop.origin[0]
    influenced_prop  = prop.origin[1]
    x_offset         = influenced_prop[0] - influencing_prop[0] 
    y_offset         = influenced_prop[1] - influencing_prop[1] 
    z_offset         = influenced_prop[2] - influencing_prop[2] 

    
    if grid_mode == 'radial':
        psi     = psi_360[:-1]
        psi_2d  = np.tile(np.atleast_2d(psi).T,(1,Nr)) 
        r       = np.linspace(Rh,0.99*R,Nr)
        
        # basic radial grid
        ymesh = r*np.cos(psi_2d)
        zmesh = r*np.sin(psi_2d)
        
    elif grid_mode == 'cartesian':
        y     = np.linspace(-R,R,Ny)
        z     = np.linspace(-R,R,Nz)
        ymesh = np.tile(np.atleast_2d(y).T,(1,Nz))
        zmesh = np.tile(np.atleast_2d(z),(Ny,1))
        
        r_pts   = np.sqrt(ymesh**2 + zmesh**2)
        cutoffs = r_pts<R
        
        ymesh  = ymesh[cutoffs]
        zmesh  = zmesh[cutoffs]
        
    
    grid_points        = Data()
    grid_points.ymesh  = ymesh + y_offset
    grid_points.zmesh  = zmesh + z_offset
    grid_points.Nr     = Nr
    grid_points.Na     = Na
    
    if plot_grid:
        
        # plot the grid points
        fig  = plt.figure()
        axes = fig.add_subplot(1,1,1)
        axes.plot(ymesh,zmesh,'k.')
        
        # plot the propeller radius
        axes.plot(R*np.cos(psi_360), R*np.sin(psi_360), 'r')
        
        axes.set_aspect('equal', 'box')
        axes.set_xlabel('y [m]')
        axes.set_ylabel("z [m]")
        axes.set_title("New Grid Points")
        
        
        #plt.show()    
    
    return grid_points
    
    
def simulation_conditions():
    # --------------------------------------------------------------------------------------------------
    # Atmosphere Conditions:
    # --------------------------------------------------------------------------------------------------
    atmosphere = SUAVE.Analyses.Atmospheric.US_Standard_1976()
    atmo_data = atmosphere.compute_values(altitude=14000 * Units.ft)
    rho = atmo_data.density
    mu = atmo_data.dynamic_viscosity
    T = atmo_data.temperature
    a = atmo_data.speed_of_sound
    
    # aerodynamics analyzed for a fixed angle of attack
    aoa = np.array([[3 * Units.deg  ]])  
    Vv = np.array([[ 20 * Units.mph]])
    mach  = Vv/a

    conditions = SUAVE.Analyses.Mission.Segments.Conditions.Aerodynamics()
    conditions.freestream.density = rho
    conditions.freestream.dynamic_viscosity = mu
    conditions.freestream.speed_of_sound = a
    conditions.freestream.temperature = T
    conditions.freestream.mach_number = mach
    conditions.freestream.velocity = Vv
    conditions.aerodynamics.angle_of_attack = aoa
    conditions.frames.body.transform_to_inertial = np.array(
        [[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]]
    )
    conditions.frames.inertial.velocity_vector = np.array([[Vv[0][0],0,0]])
    conditions.propulsion.throttle = np.array([[1]])
    
    return conditions    

def simulation_settings(vehicle):
    
    # grid conditions for downstream propeller
    grid_settings            = Data()
    grid_settings.radius     = vehicle.propulsors.prop_net.propeller.tip_radius
    grid_settings.hub_radius = vehicle.propulsors.prop_net.propeller.hub_radius
    grid_settings.Nr         = 70
    grid_settings.Na         = 40
    
    # cartesian grid specs
    grid_settings.Ny         = 80
    grid_settings.Nz         = 80
    grid_settings.grid_mode  = 'cartesian'
    
    VLM_settings        = Data()
    VLM_settings.number_spanwise_vortices        = 16
    VLM_settings.number_chordwise_vortices       = 4
    VLM_settings.use_surrogate                   = True
    VLM_settings.propeller_wake_model            = False
    VLM_settings.model_fuselage                  = False
    VLM_settings.spanwise_cosine_spacing         = True
    VLM_settings.number_of_wake_timesteps        = 0.
    VLM_settings.leading_edge_suction_multiplier = 1.
    VLM_settings.initial_timestep_offset         = 0.
    VLM_settings.wake_development_time           = 0.5
    
    return grid_settings, VLM_settings

def vehicle_setup():
    #-----------------------------------------------------------------
    #   Vehicle Initialization:
    #-----------------------------------------------------------------
    vehicle = SUAVE.Vehicle()
    vehicle.tag = 'simple_vehicle'    
    
    # ------------------------------------------------------------------
    #   Propulsion Properties
    # ------------------------------------------------------------------
    net                          = SUAVE.Components.Energy.Networks.Battery_Propeller()
    net.tag                      = 'prop_net'
    net.number_of_engines        = 2
    
    prop            = SUAVE.Components.Energy.Converters.Propeller()
    prop,conditions = propeller_geometry() 
    
    # adjust propeller location and rotation:
    prop.rotation = [-1,1]
    prop.origin   = np.array([[0., 0., 0.],
                             [2.5, 0., 0.]]) 
    
    net.propeller = prop
    vehicle.append_component(net)
    
    return vehicle



if __name__ == '__main__':
    main()
    plt.show()
