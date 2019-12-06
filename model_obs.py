"""
This file contain a subclass of the model.py module and Cluster class. It
is dedicated to the computing of observables.

"""

#==================================================
# Requested imports
#==================================================

import numpy as np
import scipy.ndimage as ndimage
import astropy.units as u
from astropy.wcs import WCS
from astropy import constants as const
import scipy.interpolate as interpolate

from ClusterModel import model_tools
from ClusterTools import cluster_global 
from ClusterTools import cluster_profile 
from ClusterTools import cluster_spectra 
from ClusterTools import map_tools


#==================================================
# Observable class
#==================================================

class Observables(object):
    """ Observable class
    This class serves as a parser to the main Cluster class, to 
    include the subclass Observable in this other file.

    Attributes
    ----------  
    The attributes are the same as the Cluster class, see model.py

    Methods
    ----------  
    - get_gamma_spectrum(self, energy=np.logspace(-2,6,1000)*u.GeV, Rmax=None,type_integral='spherical', 
    NR500_los=5.0, Npt_los=100): compute the gamma ray spectrum integrating over the volume up to Rmax
    - get_gamma_profile(self, radius=np.logspace(0,4,1000)*u.kpc, Emin=10.0*u.MeV, Emax=1.0*u.PeV, 
    Energy_density=False, NR500_los=5.0, Npt_los=100): compute the gamma ray profile, integrating over 
    the energy between the gamma ray energy Emin and Emax.
    - get_gamma_flux(self, Rmax=None, type_integral='spherical', NR500_los=5.0, Npt_los=100,
    Emin=10.0*u.MeV, Emax=1.0*u.PeV, Energy_density=False): compute the gamma ray flux between 
    energy range and for R>Rmax.
    - get_gamma_template_map(self, NR500_los=5.0, Npt_los=100): compute the gamma ray template map, 
    normalized so that the integral over the overall cluster is 1.

    - get_ysph_profile(self, radius=np.logspace(0,4,1000)*u.kpc): compute the spherically 
    integrated compton parameter profile
    - get_ycyl_profile(self, radius=np.logspace(0,4,1000)*u.kpc): compute the cylindrincally 
    integrated Compton parameter profile
    - get_y_compton_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100):
    compute the Compton parameter profile
    - get_ymap(self, FWHM=None, NR500_los=5.0, Npt_los=100): compute a Compton parameter map.

    - get_sx_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100,
    output_type='S'): compute the Xray surface brightness profile
    - get_fxsph_profile(self, radius=np.logspace(0,4,1000)*u.kpc, output_type='S'): compute the Xray 
    spherically integrated flux profile
    - get_fxcyl_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100,
    output_type='S'): compute the Xray cylindrically integrated flux profile
    - get_sxmap(self, FWHM=None, NR500_los=5.0, Npt_los=100, output_type='S'): compute the Xray 
    surface brigthness map

    """
    
    #==================================================
    # Compute gamma ray spectrum
    #==================================================

    def get_gamma_spectrum(self, energy=np.logspace(-2,6,100)*u.GeV,
                           Rmin=None, Rmax=None,
                           type_integral='spherical',
                           Rmin_los=None, NR500_los=5.0):
        """
        Compute the gamma ray emission enclosed within [Rmin,Rmax], in 3d (i.e. spherically 
        integrated), or the gamma ray emmission enclosed within an circular area (i.e.
        cylindrical).
        
        Parameters
        ----------
        - energy (quantity) : the physical energy of gamma rays
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, R500)
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - energy (quantity) : the physical energy of gamma rays
        - dN_dEdSdt (np.ndarray) : the spectrum in units of GeV-1 cm-2 s-1

        """
                
        # In case the input is not an array
        energy = model_tools.check_qarray(energy, unit='GeV')

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Rmin_los is None:
            Rmin_los = self._Rmin
            
        # Compute the integral
        if type_integral == 'spherical':
            rad = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_gamma_ray(energy, rad)
            dN_dEdt = model_tools.spherical_integration(dN_dEdVdt, rad)
            
        # Compute the integral        
        if type_integral == 'cylindrical':
            Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)
            Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
            r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            r2d = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_gamma_ray(energy, r3d)
            dN_dEdt = model_tools.cylindrical_integration(dN_dEdVdt, energy, r3d, r2d, los, Rtrunc=self._R_truncation)
        
        # From intrinsic luminosity to flux
        dN_dEdSdt = dN_dEdt / (4*np.pi * self._D_lum**2)

        # Apply EBL absorbtion
        if self._EBL_model != 'none':
            absorb = cluster_spectra.get_ebl_absorb(energy.to_value('GeV'), self._redshift, self._EBL_model)
            dN_dEdSdt = dN_dEdSdt * absorb
        
        return energy, dN_dEdSdt.to('GeV-1 cm-2 s-1')
    

    #==================================================
    # Compute gamma ray profile
    #==================================================

    def get_gamma_profile(self, radius=np.logspace(0,4,100)*u.kpc,
                          Emin=None, Emax=None, Energy_density=False,
                          Rmin_los=None, NR500_los=5.0):
        """
        Compute the gamma ray emission profile within Emin-Emax.
        
        Parameters
        ----------
        - radius (quantity): the projected 2d radius in units homogeneous to kpc, as a 1d array
        - Emin (quantity): the lower bound for gamma ray energy integration
        - Emax (quantity): the upper bound for gamma ray energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 

        Outputs
        ----------
        - dN_dSdtdO (np.ndarray) : the spectrum in units of cm-2 s-1 sr-1 or GeV cm-2 s-1 sr-1

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius, unit='kpc')
        
        # Get the integration limits
        if Emin is None:
            Emin = self._Epmin/10.0 # photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax
        if Rmin_los is None:
            Rmin_los = self._Rmin
        Rmin = np.amin(radius.to_value('kpc'))*u.kpc
        Rmax = np.amax(radius.to_value('kpc'))*u.kpc

        # Define array for integration
        eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
        Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)        
        Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
        r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
        los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
        dN_dEdVdt = self.get_rate_gamma_ray(eng, r3d)

        # Apply EBL absorbtion
        if self._EBL_model != 'none':
            absorb = cluster_spectra.get_ebl_absorb(eng.to_value('GeV'), self._redshift, self._EBL_model)
            dN_dEdVdt = dN_dEdVdt * model_tools.replicate_array(absorb, len(r3d), T=True)
            
        # Compute energy integal
        dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)
        
        # Compute integral over l.o.s.
        dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
        dN_dVdt_proj[radius > self._R_truncation] = 0
        
        # Convert to physical to angular scale
        dN_dtdO = dN_dVdt_proj * self._D_ang**2 * u.Unit('sr-1')

        # From intrinsic luminosity to flux
        dN_dSdtdO = dN_dtdO / (4*np.pi * self._D_lum**2)
        
        # return
        if Energy_density:
            dN_dSdtdO = dN_dSdtdO.to('GeV cm-2 s-1 sr-1')
        else :
            dN_dSdtdO = dN_dSdtdO.to('cm-2 s-1 sr-1')
            
        return radius, dN_dSdtdO

    
    #==================================================
    # Compute gamma ray flux
    #==================================================
    
    def get_gamma_flux(self, Emin=None, Emax=None, Energy_density=False,
                       Rmin=None, Rmax=None,
                       type_integral='spherical',
                       Rmin_los=None, NR500_los=5.0):
        
        """
        Compute the gamma ray emission enclosed within Rmax, in 3d (i.e. spherically 
        integrated), or the gamma ray emmission enclosed within an circular area (i.e.
        cylindrical), and in a given energy band. The minimal energy can be an array to 
        flux(>E) and the radius max can be an array to get flux(<R).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for gamma ray energy integration
        It can be an array.
        - Emax (quantity): the upper bound for gamma ray energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin (quantity): the minimal radius within with the spectrum is computed 
        - Rmax (quantity): the maximal radius within with the spectrum is computed.
        It can be an array.
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - flux (quantity) : the gamma ray flux either in GeV/cm2/s or ph/cm2/s, depending
        on parameter Energy_density

        """

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin_los is None:
            Rmin_los = self._Rmin
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Emin is None:
            Emin = self._Epmin/10.0 # default photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax

        # Check if Emin and Rmax are scalar or array
        if type(Emin.value) == np.ndarray and type(Rmax.value) == np.ndarray:
            raise ValueError('Emin and Rmax cannot both be array simultaneously')

        #----- Case of scalar quantities
        if type(Emin.value) == float and type(Rmax.value) == float:
            # Get a spectrum
            energy = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_gamma_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                        type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los)

            # Integrate over it and return
            flux = model_tools.energy_integration(dN_dEdSdt, energy, Energy_density=Energy_density)

        #----- Case of energy array
        if type(Emin.value) == np.ndarray:
            # Get a spectrum
            energy = model_tools.sampling_array(np.amin(Emin.value)*Emin.unit, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_gamma_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                        type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los)

            # Integrate over it and return
            if Energy_density:
                flux = np.zeros(len(Emin))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Emin))*u.Unit('cm-2 s-1')
                
            itpl = interpolate.interp1d(energy.value, dN_dEdSdt.value, kind='cubic')
                
            for i in range(len(Emin)):
                eng_i = model_tools.sampling_array(Emin[i], Emax, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dEdSdt_i = itpl(eng_i.value)*dN_dEdSdt.unit
                flux[i] = model_tools.energy_integration(dN_dEdSdt_i, eng_i, Energy_density=Energy_density)

        #----- Case of radius array (need to use dN/dVdEdt and not get_profile because spherical flux)
        if type(Rmax.value) == np.ndarray:
            # Get energy integration
            eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            if type_integral == 'spherical':
                Rmax3d = np.amax(Rmax.value)*Rmax.unit
                Rmin3d = Rmin
            if type_integral == 'cylindrical':
                Rmax3d = np.sqrt((NR500_los*self._R500)**2 + (np.amax(Rmax.value)*Rmax.unit)**2)*1.1        
                Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)*0.9
            r3d = model_tools.sampling_array(Rmin3d, Rmax3d, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_gamma_ray(eng, r3d)

            # Apply EBL absorbtion
            if self._EBL_model != 'none':
                absorb = cluster_spectra.get_ebl_absorb(eng.to_value('GeV'), self._redshift, self._EBL_model)
                dN_dEdVdt = dN_dEdVdt * model_tools.replicate_array(absorb, len(r3d), T=True)

            # Compute energy integal
            dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)
        
            # Define output
            if Energy_density:
                flux = np.zeros(len(Rmax))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Rmax))*u.Unit('cm-2 s-1')

            # Case of spherical integral: direct volume integration
            if type_integral == 'spherical':
               itpl = interpolate.interp1d(r3d.to_value('kpc'), dN_dVdt.value, kind='cubic')
               for i in range(len(Rmax)):
                   rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                   dN_dVdt_i = itpl(rad_i.to_value('kpc'))*dN_dVdt.unit
                   lum_i = model_tools.spherical_integration(dN_dVdt_i, rad_i)
                   flux[i] =  lum_i / (4*np.pi * self._D_lum**2)
                
            # Case of cylindrical integral
            if type_integral == 'cylindrical':
                # Compute integral over l.o.s.
                radius = model_tools.sampling_array(Rmin, np.amax(Rmax.value)*Rmax.unit, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
                dN_dVdt_proj[radius > self._R_truncation] = 0

                dN_dSdVdt_proj = dN_dVdt_proj / (4*np.pi * self._D_lum**2)
        
                itpl = interpolate.interp1d(radius.to_value('kpc'), dN_dSdVdt_proj.value, kind='cubic')
                
                for i in range(len(Rmax)):
                    rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                    dN_dSdVdt_proj_i = itpl(rad_i.value)*dN_dSdVdt_proj.unit
                    flux[i] = model_tools.trapz_loglog(2*np.pi*rad_i*dN_dSdVdt_proj_i, rad_i)
        
        # Return
        if Energy_density:
            flux = flux.to('GeV cm-2 s-1')
        else:
            flux = flux.to('cm-2 s-1')
            
        return flux


    #==================================================
    # Compute gamma map
    #==================================================
    def get_gamma_map(self, Emin=None, Emax=None,
                      Rmin_los=None, NR500_los=5.0,
                      Rmin=None, Rmax=None,
                      Energy_density=False, Normalize=False):
        """
        Compute the gamma ray map. The map is normalized so that the integral 
        of the map over the cluster volume is 1 (up to Rmax=5R500).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for gamma ray energy integration.
        Has no effect if Normalized is True
        - Emax (quantity): the upper bound for gamma ray energy integration
        Has no effect if Normalized is True
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, Rtruncation) for getting the normlization flux.
        Has no effect if Normalized is False
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        Has no effect if Normalized is True
        - Normalize (bool): if True, the map is normalized by the flux to get a 
        template in unit of sr-1 

        Outputs
        ----------
        gamma_map (np.ndarray) : the map in units of sr-1 or brightness

        """

        # Get the header
        header = self.get_map_header()

        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map (in deg)
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))
        
        # Define the radius used fo computing the profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min > 10 and theta_max > 10:
            print('!!!!! WARNING: the cluster location is very much offset from the field of view')
        rmax = theta_max*np.pi/180 * self._D_ang
        rmin = theta_min*np.pi/180 * self._D_ang
        radius = model_tools.sampling_array(rmin, rmax, NptPd=self._Npt_per_decade_integ, unit=True)
        
        # Project the integrand
        r_proj, profile = self.get_gamma_profile(radius, Emin=Emin, Emax=Emax, Energy_density=Energy_density,
                                                 Rmin_los=Rmin_los, NR500_los=NR500_los)

        # Convert to angle and interpolate onto a map
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi   # degrees
        gamma_map = map_tools.profile2map(profile.value, theta_proj, dist_map)*profile.unit
        
        # Avoid numerical residual ringing from interpolation
        gamma_map[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Compute the normalization: to return a map in sr-1, i.e. by computing the total flux
        if Normalize:
            if Rmax is None:
                if self._R_truncation is not np.inf:
                    Rmax = self._R_truncation
                else:                    
                    Rmax = NR500_los*self._R500
            if Rmin is None:
                Rmin = self._Rmin
            flux = self.get_gamma_flux(Rmin=Rmin, Rmax=Rmax, type_integral='cylindrical', NR500_los=NR500_los,
                                       Emin=Emin, Emax=Emax, Energy_density=Energy_density)
            gamma_map = gamma_map / flux
            gamma_map = gamma_map.to('sr-1')

        else:
            if Energy_density:
                gamma_map = gamma_map.to('GeV cm-2 s-1 sr-1')
            else :
                gamma_map = gamma_map.to('cm-2 s-1 sr-1')
                
        return gamma_map

    
    #==================================================
    # Compute neutrinos spectrum
    #==================================================

    def get_neutrino_spectrum(self, energy=np.logspace(-2,6,100)*u.GeV,
                              Rmin=None, Rmax=None,
                              type_integral='spherical',
                              NR500_los=5.0,
                              Rmin_los=None, flavor='all'):
        """
        Compute the neutrino emission enclosed within [Rmin,Rmax], in 3d (i.e. spherically 
        integrated), or the neutrino emmission enclosed within an circular area (i.e.
        cylindrical).
        
        Parameters
        ----------
        - energy (quantity) : the physical energy of neutrinos
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, R500)
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case
        - flavor (str): either 'all', 'numu' or 'nue'

        Outputs
        ----------
        - energy (quantity) : the physical energy of neutrino
        - dN_dEdSdt (np.ndarray) : the spectrum in units of GeV-1 cm-2 s-1

        """
                
        # In case the input is not an array
        energy = model_tools.check_qarray(energy, unit='GeV')

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Rmin_los is None:
            Rmin_los = self._Rmin
            
        # Compute the integral
        if type_integral == 'spherical':
            rad = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_neutrino(energy, rad, flavor=flavor)
            dN_dEdt = model_tools.spherical_integration(dN_dEdVdt, rad)
            
        # Compute the integral        
        if type_integral == 'cylindrical':
            Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)
            Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
            r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            r2d = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_neutrino(energy, r3d, flavor=flavor)
            dN_dEdt = model_tools.cylindrical_integration(dN_dEdVdt, energy, r3d, r2d, los, Rtrunc=self._R_truncation)
        
        # From intrinsic luminosity to flux
        dN_dEdSdt = dN_dEdt / (4*np.pi * self._D_lum**2)
        
        return energy, dN_dEdSdt.to('GeV-1 cm-2 s-1')
    

    #==================================================
    # Compute neutrino profile
    #==================================================

    def get_neutrino_profile(self, radius=np.logspace(0,4,100)*u.kpc,
                             Emin=None, Emax=None, Energy_density=False,
                             Rmin_los=None, NR500_los=5.0, flavor='all'):
        """
        Compute the neutrino emission profile within Emin-Emax.
        
        Parameters
        ----------
        - radius (quantity): the projected 2d radius in units homogeneous to kpc, as a 1d array
        - Emin (quantity): the lower bound for neutrino energy integration
        - Emax (quantity): the upper bound for neutrino energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        - flavor (str): either 'all', 'numu' or 'nue'

        Outputs
        ----------
        - dN_dSdtdO (np.ndarray) : the spectrum in units of cm-2 s-1 sr-1 or GeV cm-2 s-1 sr-1

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius, unit='kpc')
        
        # Get the integration limits
        if Emin is None:
            Emin = self._Epmin/10.0 # photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax
        if Rmin_los is None:
            Rmin_los = self._Rmin
        Rmin = np.amin(radius.to_value('kpc'))*u.kpc
        Rmax = np.amax(radius.to_value('kpc'))*u.kpc

        # Define array for integration
        eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
        Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)        
        Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
        r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
        los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
        dN_dEdVdt = self.get_rate_neutrino(eng, r3d, flavor=flavor)

        # Compute energy integal
        dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)

        # Compute integral over l.o.s.
        dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
        dN_dVdt_proj[radius > self._R_truncation] = 0
        
        # Convert to physical to angular scale
        dN_dtdO = dN_dVdt_proj * self._D_ang**2 * u.Unit('sr-1')

        # From intrinsic luminosity to flux
        dN_dSdtdO = dN_dtdO / (4*np.pi * self._D_lum**2)
        
        # return
        if Energy_density:
            dN_dSdtdO = dN_dSdtdO.to('GeV cm-2 s-1 sr-1')
        else :
            dN_dSdtdO = dN_dSdtdO.to('cm-2 s-1 sr-1')
            
        return radius, dN_dSdtdO


    #==================================================
    # Compute neutrino flux
    #==================================================

    def get_neutrino_flux(self, Emin=None, Emax=None, Energy_density=False,
                          Rmin=None, Rmax=None,
                          type_integral='spherical',
                          Rmin_los=None, NR500_los=5.0,
                          flavor='all'):
        
        """
        Compute the neutrino emission enclosed within Rmax, in 3d (i.e. spherically 
        integrated), or the neutrino emmission enclosed within an circular area (i.e.
        cylindrical), and in a given energy band. The minimal energy can be an array to 
        flux(>E) and the radius max can be an array to get flux(<R).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for neutrino energy integration
        It can be an array.
        - Emax (quantity): the upper bound for neutrino energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin (quantity): the minimal radius within with the spectrum is computed 
        - Rmax (quantity): the maximal radius within with the spectrum is computed.
        It can be an array.
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - flux (quantity) : the neutrino flux either in GeV/cm2/s or ph/cm2/s, depending
        on parameter Energy_density

        """

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin_los is None:
            Rmin_los = self._Rmin
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Emin is None:
            Emin = self._Epmin/10.0 # default photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax

        # Check if Emin and Rmax are scalar or array
        if type(Emin.value) == np.ndarray and type(Rmax.value) == np.ndarray:
            raise ValueError('Emin and Rmax cannot both be array simultaneously')

        #----- Case of scalar quantities
        if type(Emin.value) == float and type(Rmax.value) == float:
            # Get a spectrum
            energy = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_neutrino_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                           type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los,
                                                           flavor=flavor)

            # Integrate over it and return
            flux = model_tools.energy_integration(dN_dEdSdt, energy, Energy_density=Energy_density)

        #----- Case of energy array
        if type(Emin.value) == np.ndarray:
            # Get a spectrum
            energy = model_tools.sampling_array(np.amin(Emin.value)*Emin.unit, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_neutrino_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                           type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los,
                                                           flavor=flavor)

            # Integrate over it and return
            if Energy_density:
                flux = np.zeros(len(Emin))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Emin))*u.Unit('cm-2 s-1')
                
            itpl = interpolate.interp1d(energy.value, dN_dEdSdt.value, kind='cubic')
                
            for i in range(len(Emin)):
                eng_i = model_tools.sampling_array(Emin[i], Emax, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dEdSdt_i = itpl(eng_i.value)*dN_dEdSdt.unit
                flux[i] = model_tools.energy_integration(dN_dEdSdt_i, eng_i, Energy_density=Energy_density)

        #----- Case of radius array (need to use dN/dVdEdt and not get_profile because spherical flux)
        if type(Rmax.value) == np.ndarray:
            # Get energy integration
            eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            if type_integral == 'spherical':
                Rmax3d = np.amax(Rmax.value)*Rmax.unit
                Rmin3d = Rmin
            if type_integral == 'cylindrical':
                Rmax3d = np.sqrt((NR500_los*self._R500)**2 + (np.amax(Rmax.value)*Rmax.unit)**2)*1.1        
                Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)*0.9
            r3d = model_tools.sampling_array(Rmin3d, Rmax3d, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_neutrino(eng, r3d)

            # Apply EBL absorbtion
            if self._EBL_model != 'none':
                absorb = cluster_spectra.get_ebl_absorb(eng.to_value('GeV'), self._redshift, self._EBL_model)
                dN_dEdVdt = dN_dEdVdt * model_tools.replicate_array(absorb, len(r3d), T=True)

            # Compute energy integal
            dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)
        
            # Define output
            if Energy_density:
                flux = np.zeros(len(Rmax))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Rmax))*u.Unit('cm-2 s-1')

            # Case of spherical integral: direct volume integration
            if type_integral == 'spherical':
               itpl = interpolate.interp1d(r3d.to_value('kpc'), dN_dVdt.value, kind='cubic')
               for i in range(len(Rmax)):
                   rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                   dN_dVdt_i = itpl(rad_i.to_value('kpc'))*dN_dVdt.unit
                   lum_i = model_tools.spherical_integration(dN_dVdt_i, rad_i)
                   flux[i] =  lum_i / (4*np.pi * self._D_lum**2)
                
            # Case of cylindrical integral
            if type_integral == 'cylindrical':
                # Compute integral over l.o.s.
                radius = model_tools.sampling_array(Rmin, np.amax(Rmax.value)*Rmax.unit, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
                dN_dVdt_proj[radius > self._R_truncation] = 0

                dN_dSdVdt_proj = dN_dVdt_proj / (4*np.pi * self._D_lum**2)
        
                itpl = interpolate.interp1d(radius.to_value('kpc'), dN_dSdVdt_proj.value, kind='cubic')
                
                for i in range(len(Rmax)):
                    rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                    dN_dSdVdt_proj_i = itpl(rad_i.value)*dN_dSdVdt_proj.unit
                    flux[i] = model_tools.trapz_loglog(2*np.pi*rad_i*dN_dSdVdt_proj_i, rad_i)
        
        # Return
        if Energy_density:
            flux = flux.to('GeV cm-2 s-1')
        else:
            flux = flux.to('cm-2 s-1')
            
        return flux
    

    #==================================================
    # Compute neutrino map
    #==================================================
    def get_neutrino_map(self, Emin=None, Emax=None,
                         Rmin_los=None, NR500_los=5.0,
                         Rmin=None, Rmax=None,
                         Energy_density=False, Normalize=False,
                         flavor='all'):
        """
        Compute the neutrino map. The map is normalized so that the integral 
        of the map over the cluster volume is 1 (up to Rmax=5R500).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for nu energy integration.
        Has no effect if Normalized is True
        - Emax (quantity): the upper bound for nu energy integration
        Has no effect if Normalized is True
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, Rtruncation) for getting the normlization flux.
        Has no effect if Normalized is False
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        Has no effect if Normalized is True
        - Normalize (bool): if True, the map is normalized by the flux to get a 
        template in unit of sr-1 
        - flavor (str): either 'all', 'numu' or 'nue'

        Outputs
        ----------
        neutrino_map (np.ndarray) : the map in units of sr-1 or brightness

        """

        # Get the header
        header = self.get_map_header()

        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map (in deg)
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))
        
        # Define the radius used fo computing the profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min > 10 and theta_max > 10:
            print('!!!!! WARNING: the cluster location is very much offset from the field of view')
        rmax = theta_max*np.pi/180 * self._D_ang
        rmin = theta_min*np.pi/180 * self._D_ang
        radius = model_tools.sampling_array(rmin, rmax, NptPd=self._Npt_per_decade_integ, unit=True)
        
        # Project the integrand
        r_proj, profile = self.get_neutrino_profile(radius, Emin=Emin, Emax=Emax, Energy_density=Energy_density,
                                                    Rmin_los=Rmin_los, NR500_los=NR500_los, flavor=flavor)

        # Convert to angle and interpolate onto a map
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi   # degrees
        nu_map = map_tools.profile2map(profile.value, theta_proj, dist_map)*profile.unit
        
        # Avoid numerical residual ringing from interpolation
        nu_map[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Compute the normalization: to return a map in sr-1, i.e. by computing the total flux
        if Normalize:
            if Rmax is None:
                if self._R_truncation is not np.inf:
                    Rmax = self._R_truncation
                else:                    
                    Rmax = NR500_los*self._R500
            if Rmin is None:
                Rmin = self._Rmin
            flux = self.get_neutrino_flux(Rmin=Rmin, Rmax=Rmax, type_integral='cylindrical', NR500_los=NR500_los,
                                          Emin=Emin, Emax=Emax, Energy_density=Energy_density, flavor=flavor)
            nu_map = nu_map / flux
            nu_map = nu_map.to('sr-1')

        else:
            if Energy_density:
                nu_map = nu_map.to('GeV cm-2 s-1 sr-1')
            else :
                nu_map = nu_map.to('cm-2 s-1 sr-1')
                
        return nu_map

    

    #==================================================
    # Compute inverse compton spectrum
    #==================================================

    def get_ic_spectrum(self, energy=np.logspace(-2,6,100)*u.GeV,
                        Rmin=None, Rmax=None,
                        type_integral='spherical',
                        Rmin_los=None, NR500_los=5.0):
        """
        Compute the inverse Compton emission enclosed within [Rmin,Rmax], in 3d (i.e. spherically 
        integrated), or the inverse Compton emmission enclosed within an circular area (i.e.
        cylindrical).
        
        Parameters
        ----------
        - energy (quantity) : the physical energy of photons
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, R500)
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - energy (quantity) : the physical energy of photons
        - dN_dEdSdt (np.ndarray) : the spectrum in units of GeV-1 cm-2 s-1

        """
                
        # In case the input is not an array
        energy = model_tools.check_qarray(energy, unit='GeV')

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Rmin_los is None:
            Rmin_los = self._Rmin
            
        # Compute the integral
        if type_integral == 'spherical':
            rad = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_ic(energy, rad)
            dN_dEdt = model_tools.spherical_integration(dN_dEdVdt, rad)
            
        # Compute the integral        
        if type_integral == 'cylindrical':
            Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)
            Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
            r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            r2d = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_ic(energy, r3d)
            dN_dEdt = model_tools.cylindrical_integration(dN_dEdVdt, energy, r3d, r2d, los, Rtrunc=self._R_truncation)
        
        # From intrinsic luminosity to flux
        dN_dEdSdt = dN_dEdt / (4*np.pi * self._D_lum**2)

        # Apply EBL absorbtion
        if self._EBL_model != 'none':
            absorb = cluster_spectra.get_ebl_absorb(energy.to_value('GeV'), self._redshift, self._EBL_model)
            dN_dEdSdt = dN_dEdSdt * absorb
        
        return energy, dN_dEdSdt.to('GeV-1 cm-2 s-1')


    #==================================================
    # Compute inverse Compton profile
    #==================================================

    def get_ic_profile(self, radius=np.logspace(0,4,100)*u.kpc,
                       Emin=None, Emax=None, Energy_density=False,
                       Rmin_los=None, NR500_los=5.0):
        """
        Compute the inverse Compton emission profile within Emin-Emax.
        
        Parameters
        ----------
        - radius (quantity): the projected 2d radius in units homogeneous to kpc, as a 1d array
        - Emin (quantity): the lower bound for IC energy integration
        - Emax (quantity): the upper bound for IC energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 

        Outputs
        ----------
        - dN_dSdtdO (np.ndarray) : the spectrum in units of cm-2 s-1 sr-1 or GeV cm-2 s-1 sr-1

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius, unit='kpc')
        
        # Get the integration limits
        if Emin is None:
            Emin = self._Epmin/10.0 # photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax
        if Rmin_los is None:
            Rmin_los = self._Rmin
        Rmin = np.amin(radius.to_value('kpc'))*u.kpc
        Rmax = np.amax(radius.to_value('kpc'))*u.kpc

        # Define array for integration
        eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
        Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)        
        Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
        r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
        los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
        dN_dEdVdt = self.get_rate_ic(eng, r3d)

        # Apply EBL absorbtion
        if self._EBL_model != 'none':
            absorb = cluster_spectra.get_ebl_absorb(eng.to_value('GeV'), self._redshift, self._EBL_model)
            dN_dEdVdt = dN_dEdVdt * model_tools.replicate_array(absorb, len(r3d), T=True)
            
        # Compute energy integal
        dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)

        # Compute integral over l.o.s.
        dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
        dN_dVdt_proj[radius > self._R_truncation] = 0
        
        # Convert to physical to angular scale
        dN_dtdO = dN_dVdt_proj * self._D_ang**2 * u.Unit('sr-1')

        # From intrinsic luminosity to flux
        dN_dSdtdO = dN_dtdO / (4*np.pi * self._D_lum**2)
        
        # return
        if Energy_density:
            dN_dSdtdO = dN_dSdtdO.to('GeV cm-2 s-1 sr-1')
        else :
            dN_dSdtdO = dN_dSdtdO.to('cm-2 s-1 sr-1')
            
        return radius, dN_dSdtdO

    #==================================================
    # Compute gamma ray flux
    #==================================================
    
    def get_ic_flux(self, Emin=None, Emax=None, Energy_density=False,
                    Rmin=None, Rmax=None,
                    type_integral='spherical',
                    Rmin_los=None, NR500_los=5.0):
        
        """
        Compute the inverse Compton emission enclosed within Rmax, in 3d (i.e. spherically 
        integrated), or the inverse Compton emmission enclosed within an circular area (i.e.
        cylindrical), and in a given energy band. The minimal energy can be an array to 
        flux(>E) and the radius max can be an array to get flux(<R).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for IC energy integration
        It can be an array.
        - Emax (quantity): the upper bound for IC energy integration
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        - Rmin (quantity): the minimal radius within with the spectrum is computed 
        - Rmax (quantity): the maximal radius within with the spectrum is computed.
        It can be an array.
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - flux (quantity) : the IC flux either in GeV/cm2/s or ph/cm2/s, depending
        on parameter Energy_density

        """

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin_los is None:
            Rmin_los = self._Rmin
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Emin is None:
            Emin = self._Epmin/10.0 # default photon energy down to 0.1 minimal proton energy
        if Emax is None:
            Emax = self._Epmax

        # Check if Emin and Rmax are scalar or array
        if type(Emin.value) == np.ndarray and type(Rmax.value) == np.ndarray:
            raise ValueError('Emin and Rmax cannot both be array simultaneously')

        #----- Case of scalar quantities
        if type(Emin.value) == float and type(Rmax.value) == float:
            # Get a spectrum
            energy = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_ic_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                     type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los)

            # Integrate over it and return
            flux = model_tools.energy_integration(dN_dEdSdt, energy, Energy_density=Energy_density)

        #----- Case of energy array
        if type(Emin.value) == np.ndarray:
            # Get a spectrum
            energy = model_tools.sampling_array(np.amin(Emin.value)*Emin.unit, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            energy, dN_dEdSdt = self.get_ic_spectrum(energy, Rmin=Rmin, Rmax=Rmax,
                                                     type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los)

            # Integrate over it and return
            if Energy_density:
                flux = np.zeros(len(Emin))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Emin))*u.Unit('cm-2 s-1')
                
            itpl = interpolate.interp1d(energy.value, dN_dEdSdt.value, kind='cubic')
                
            for i in range(len(Emin)):
                eng_i = model_tools.sampling_array(Emin[i], Emax, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dEdSdt_i = itpl(eng_i.value)*dN_dEdSdt.unit
                flux[i] = model_tools.energy_integration(dN_dEdSdt_i, eng_i, Energy_density=Energy_density)

        #----- Case of radius array (need to use dN/dVdEdt and not get_profile because spherical flux)
        if type(Rmax.value) == np.ndarray:
            # Get energy integration
            eng = model_tools.sampling_array(Emin, Emax, NptPd=self._Npt_per_decade_integ, unit=True)
            if type_integral == 'spherical':
                Rmax3d = np.amax(Rmax.value)*Rmax.unit
                Rmin3d = Rmin
            if type_integral == 'cylindrical':
                Rmax3d = np.sqrt((NR500_los*self._R500)**2 + (np.amax(Rmax.value)*Rmax.unit)**2)*1.1        
                Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)*0.9
            r3d = model_tools.sampling_array(Rmin3d, Rmax3d, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_ic_ray(eng, r3d)

            # Apply EBL absorbtion
            if self._EBL_model != 'none':
                absorb = cluster_spectra.get_ebl_absorb(eng.to_value('GeV'), self._redshift, self._EBL_model)
                dN_dEdVdt = dN_dEdVdt * model_tools.replicate_array(absorb, len(r3d), T=True)

            # Compute energy integal
            dN_dVdt = model_tools.energy_integration(dN_dEdVdt, eng, Energy_density=Energy_density)
        
            # Define output
            if Energy_density:
                flux = np.zeros(len(Rmax))*u.Unit('GeV cm-2 s-1')
            else:
                flux = np.zeros(len(Rmax))*u.Unit('cm-2 s-1')

            # Case of spherical integral: direct volume integration
            if type_integral == 'spherical':
               itpl = interpolate.interp1d(r3d.to_value('kpc'), dN_dVdt.value, kind='cubic')
               for i in range(len(Rmax)):
                   rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                   dN_dVdt_i = itpl(rad_i.to_value('kpc'))*dN_dVdt.unit
                   lum_i = model_tools.spherical_integration(dN_dVdt_i, rad_i)
                   flux[i] =  lum_i / (4*np.pi * self._D_lum**2)
                
            # Case of cylindrical integral
            if type_integral == 'cylindrical':
                # Compute integral over l.o.s.
                radius = model_tools.sampling_array(Rmin, np.amax(Rmax.value)*Rmax.unit, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dVdt_proj = model_tools.los_integration_1dfunc(dN_dVdt, r3d, radius, los)
                dN_dVdt_proj[radius > self._R_truncation] = 0

                dN_dSdVdt_proj = dN_dVdt_proj / (4*np.pi * self._D_lum**2)
        
                itpl = interpolate.interp1d(radius.to_value('kpc'), dN_dSdVdt_proj.value, kind='cubic')
                
                for i in range(len(Rmax)):
                    rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                    dN_dSdVdt_proj_i = itpl(rad_i.value)*dN_dSdVdt_proj.unit
                    flux[i] = model_tools.trapz_loglog(2*np.pi*rad_i*dN_dSdVdt_proj_i, rad_i)
        
        # Return
        if Energy_density:
            flux = flux.to('GeV cm-2 s-1')
        else:
            flux = flux.to('cm-2 s-1')
            
        return flux

    
    #==================================================
    # Compute IC map
    #==================================================
    def get_ic_map(self, Emin=None, Emax=None,
                   Rmin_los=None, NR500_los=5.0,
                   Rmin=None, Rmax=None,
                   Energy_density=False, Normalize=False):
        """
        Compute the inverse Compton map. The map is normalized so that the integral 
        of the map over the cluster volume is 1 (up to Rmax=5R500).
        
        Parameters
        ----------
        - Emin (quantity): the lower bound for IC energy integration.
        Has no effect if Normalized is True
        - Emax (quantity): the upper bound for IC energy integration
        Has no effect if Normalized is True
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, Rtruncation) for getting the normlization flux.
        Has no effect if Normalized is False
        - Energy_density (bool): if True, then the energy density is computed. Otherwise, 
        the number density is computed.
        Has no effect if Normalized is True
        - Normalize (bool): if True, the map is normalized by the flux to get a 
        template in unit of sr-1 

        Outputs
        ----------
        ic_map (np.ndarray) : the map in units of sr-1 or brightness

        """

        # Get the header
        header = self.get_map_header()

        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map (in deg)
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))
        
        # Define the radius used fo computing the profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min > 10 and theta_max > 10:
            print('!!!!! WARNING: the cluster location is very much offset from the field of view')
        rmax = theta_max*np.pi/180 * self._D_ang
        rmin = theta_min*np.pi/180 * self._D_ang
        radius = model_tools.sampling_array(rmin, rmax, NptPd=self._Npt_per_decade_integ, unit=True)
        
        # Project the integrand
        r_proj, profile = self.get_ic_profile(radius, Emin=Emin, Emax=Emax, Energy_density=Energy_density,
                                              Rmin_los=Rmin_los, NR500_los=NR500_los)

        # Convert to angle and interpolate onto a map
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi   # degrees
        ic_map = map_tools.profile2map(profile.value, theta_proj, dist_map)*profile.unit
        
        # Avoid numerical residual ringing from interpolation
        ic_map[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Compute the normalization: to return a map in sr-1, i.e. by computing the total flux
        if Normalize:
            if Rmax is None:
                if self._R_truncation is not np.inf:
                    Rmax = self._R_truncation
                else:                    
                    Rmax = NR500_los*self._R500
            if Rmin is None:
                Rmin = self._Rmin
            flux = self.get_ic_flux(Rmin=Rmin, Rmax=Rmax, type_integral='cylindrical', NR500_los=NR500_los,
                                       Emin=Emin, Emax=Emax, Energy_density=Energy_density)
            ic_map = ic_map / flux
            ic_map = ic_map.to('sr-1')

        else:
            if Energy_density:
                ic_map = ic_map.to('GeV cm-2 s-1 sr-1')
            else :
                ic_map = ic_map.to('cm-2 s-1 sr-1')
                
        return ic_map


    #==================================================
    # Compute synchrotron spectrum
    #==================================================

    def get_synchrotron_spectrum(self, frequency=np.logspace(-3,2,100)*u.GHz,
                                 Rmin=None, Rmax=None,
                                 type_integral='spherical',
                                 Rmin_los=None, NR500_los=5.0):
        """
        Compute the synchrotron emission enclosed within [Rmin,Rmax], in 3d (i.e. spherically 
        integrated), or the synchrotron emmission enclosed within a circular area (i.e.
        cylindrical).
        
        Parameters
        ----------
        - energy (quantity) : the physical enery of photons
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, R500)
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - frequency (quantity) : the physical energy of photons
        - dN_dEdSdt (np.ndarray) : the spectrum in units of Jy

        """
        
        # In case the input is not an array
        frequency = model_tools.check_qarray(frequency, unit='GHz')
        energy = (const.h * frequency).to('eV')

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500
        if Rmin_los is None:
            Rmin_los = self._Rmin
            
        # Compute the integral
        if type_integral == 'spherical':
            rad = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_synchrotron(energy, rad)
            dN_dEdt = model_tools.spherical_integration(dN_dEdVdt, rad)
            
        # Compute the integral        
        if type_integral == 'cylindrical':
            Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)
            Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
            r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            r2d = model_tools.sampling_array(Rmin, Rmax, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dEdVdt = self.get_rate_synchrotron(energy, r3d)
            dN_dEdt = model_tools.cylindrical_integration(dN_dEdVdt, energy, r3d, r2d, los, Rtrunc=self._R_truncation)
            
        # From intrinsic luminosity to flux
        dN_dEdSdt = dN_dEdt / (4*np.pi * self._D_lum**2)
        
        return frequency, (dN_dEdSdt * energy**2 / frequency).to('Jy')
    

    #==================================================
    # Compute synchrotron profile
    #==================================================

    def get_synchrotron_profile(self, radius=np.logspace(0,4,100)*u.kpc,
                                freq0=1*u.GHz,
                                Rmin_los=None, NR500_los=5.0):
        """
        Compute the synchrotron emission profile at frequency freq0.
        
        Parameters
        ----------
        - radius (quantity): the projected 2d radius in units homogeneous to kpc, as a 1d array
        - freq0 (quantity): the frequency at which the profile is computed
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 

        Outputs
        ----------
        - dN_dSdtdO (np.ndarray) : the spectrum in units of cm-2 s-1 sr-1 or GeV cm-2 s-1 sr-1

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius, unit='kpc')
        
        # Get the integration limits
        if Rmin_los is None:
            Rmin_los = self._Rmin
        Rmin = np.amin(radius.to_value('kpc'))*u.kpc
        Rmax = np.amax(radius.to_value('kpc'))*u.kpc

        # Define array for integration
        eng0 = (freq0 * const.h).to('eV')
        Rmax3d = np.sqrt((NR500_los*self._R500)**2 + Rmax**2)        
        Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)
        r3d = model_tools.sampling_array(Rmin3d*0.9, Rmax3d*1.1, NptPd=self._Npt_per_decade_integ, unit=True)
        los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
        dN_dVdt_E = self.get_rate_synchrotron(eng0, r3d).flatten()
        
        # Compute integral over l.o.s.
        dN_dVdt_E_proj = model_tools.los_integration_1dfunc(dN_dVdt_E, r3d, radius, los)
        dN_dVdt_E_proj[radius > self._R_truncation] = 0
        
        # Convert to physical to angular scale
        dN_dtdO_E = dN_dVdt_E_proj * self._D_ang**2 * u.Unit('sr-1')

        # From intrinsic luminosity to flux
        dN_dSdtdO_E = dN_dtdO_E / (4*np.pi * self._D_lum**2)
        
        # return
        sed = (dN_dSdtdO_E * eng0**2/freq0).to('Jy sr-1')
            
        return radius, sed


    #==================================================
    # Compute synchrotron flux
    #==================================================
    
    def get_synchrotron_flux(self, freq0=1*u.GHz,
                             Rmin=None, Rmax=None,
                             type_integral='spherical',
                             Rmin_los=None, NR500_los=5.0):
        
        """
        Compute the synchrotron emission enclosed within Rmax, in 3d (i.e. spherically 
        integrated), or the synchrotron emmission enclosed within a circular area (i.e.
        cylindrical), and at a given frequency. The radius max can be an array to get flux(<R).
        
        Parameters
        ----------
        - freq0 (quantity): the frequency at which the profile is computed
        - Rmin (quantity): the minimal radius within with the spectrum is computed 
        - Rmax (quantity): the maximal radius within with the spectrum is computed.
        It can be an array.
        - type_integral (string): either 'spherical' or 'cylindrical'
        - Rmin_los (quantity): minimal radius at which l.o.s integration starts
        This is used only for cylindrical case
        - NR500_los (float): the line-of-sight integration will stop at NR500_los x R500. 
        This is used only for cylindrical case

        Outputs
        ----------
        - flux (quantity) : the synchrotron flux in Jy

        """

        # Check the type of integral
        ok_list = ['spherical', 'cylindrical']
        if not type_integral in ok_list:
            raise ValueError("This requested integral type (type_integral) is not available")

        # Get the integration limits
        if Rmin_los is None:
            Rmin_los = self._Rmin
        if Rmin is None:
            Rmin = self._Rmin
        if Rmax is None:
            Rmax = self._R500

        #----- Case of scalar quantities
        if type(Rmax.value) == float:
            freq0, flux = self.get_synchrotron_spectrum(freq0, Rmin=Rmin, Rmax=Rmax,
                                                        type_integral=type_integral, Rmin_los=Rmin_los, NR500_los=NR500_los)
        
        #----- Case of radius array (need to use dN/dVdEdt and not get_profile because spherical flux)
        if type(Rmax.value) == np.ndarray:
            # Get frequency sampling
            eng0 = (freq0 * const.h).to('eV')
            if type_integral == 'spherical':
                Rmax3d = np.amax(Rmax.value)*Rmax.unit
                Rmin3d = Rmin
            if type_integral == 'cylindrical':
                Rmax3d = np.sqrt((NR500_los*self._R500)**2 + (np.amax(Rmax.value)*Rmax.unit)**2)*1.1        
                Rmin3d = np.sqrt(Rmin_los**2 + Rmin**2)*0.9
            r3d = model_tools.sampling_array(Rmin3d, Rmax3d, NptPd=self._Npt_per_decade_integ, unit=True)
            los = model_tools.sampling_array(Rmin_los, NR500_los*self._R500, NptPd=self._Npt_per_decade_integ, unit=True)
            dN_dVdt_E = self.get_rate_synchrotron(eng0, r3d).flatten()

            # Define output
            flux = np.zeros(len(Rmax))*u.Unit('Jy')

            # Case of spherical integral: direct volume integration
            itpl = interpolate.interp1d(r3d.to_value('kpc'), dN_dVdt_E.value, kind='cubic')
            if type_integral == 'spherical':
               for i in range(len(Rmax)):
                   rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                   dN_dVdt_E_i = itpl(rad_i.to_value('kpc'))*dN_dVdt_E.unit
                   lum_i = model_tools.spherical_integration(dN_dVdt_E_i, rad_i) * eng0**2/freq0
                   flux[i] =  lum_i / (4*np.pi * self._D_lum**2)
                
            # Case of cylindrical integral
            if type_integral == 'cylindrical':
                # Compute integral over l.o.s.
                radius = model_tools.sampling_array(Rmin, np.amax(Rmax.value)*Rmax.unit, NptPd=self._Npt_per_decade_integ, unit=True)
                dN_dVdt_E_proj = model_tools.los_integration_1dfunc(dN_dVdt_E, r3d, radius, los)
                dN_dVdt_E_proj[radius > self._R_truncation] = 0

                dN_dSdVdt_E_proj = dN_dVdt_E_proj / (4*np.pi * self._D_lum**2)
        
                itpl = interpolate.interp1d(radius.to_value('kpc'), dN_dSdVdt_E_proj.value, kind='cubic')
                
                for i in range(len(Rmax)):
                    rad_i = model_tools.sampling_array(Rmin, Rmax[i], NptPd=self._Npt_per_decade_integ, unit=True)
                    dN_dSdVdt_E_proj_i = itpl(rad_i.value)*dN_dSdVdt_E_proj.unit
                    flux[i] = model_tools.trapz_loglog(2*np.pi*rad_i*dN_dSdVdt_E_proj_i, rad_i) * eng0**2/freq0
        
        return flux.to('Jy')


    #==================================================
    # Compute synchrotron map
    #==================================================
    def get_synchrotron_map(self, freq0=1*u.GHz,
                            Rmin_los=None, NR500_los=5.0,
                            Rmin=None, Rmax=None,
                            Normalize=False):
        """
        Compute the synchrotron map. The map is normalized so that the integral 
        of the map over the cluster volume is 1 (up to Rmax=5R500).
        
        Parameters
        ----------
        - freq0 (quantity): the frequency at wich we work
        Has no effect if Normalized is True
        - Rmin_los (Quantity): the radius at which line of sight integration starts
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Rmin, Rmax (quantity): the radius within with the spectrum is computed 
        (default is 1kpc, Rtruncation) for getting the normlization flux.
        Has no effect if Normalized is False
        - Normalize (bool): if True, the map is normalized by the flux to get a 
        template in unit of sr-1 

        Outputs
        ----------
        synchrotron_map (np.ndarray) : the map in units of sr-1 or brightness

        """

        # Get the header
        header = self.get_map_header()

        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map (in deg)
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))
        
        # Define the radius used fo computing the profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min > 10 and theta_max > 10:
            print('!!!!! WARNING: the cluster location is very much offset from the field of view')
        rmax = theta_max*np.pi/180 * self._D_ang
        rmin = theta_min*np.pi/180 * self._D_ang
        radius = model_tools.sampling_array(rmin, rmax, NptPd=self._Npt_per_decade_integ, unit=True)
        
        # Project the integrand
        r_proj, profile = self.get_synchrotron_profile(radius, freq0=freq0, 
                                                       Rmin_los=Rmin_los, NR500_los=NR500_los)

        # Convert to angle and interpolate onto a map
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi   # degrees
        synchrotron_map = map_tools.profile2map(profile.value, theta_proj, dist_map)*profile.unit
        
        # Avoid numerical residual ringing from interpolation
        synchrotron_map[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Compute the normalization: to return a map in sr-1, i.e. by computing the total flux
        if Normalize:
            if Rmax is None:
                if self._R_truncation is not np.inf:
                    Rmax = self._R_truncation
                else:                    
                    Rmax = NR500_los*self._R500
            if Rmin is None:
                Rmin = self._Rmin
            flux = self.get_synchrotron_flux(Rmin=Rmin, Rmax=Rmax, type_integral='cylindrical', NR500_los=NR500_los, freq0=freq0)
            synchrotron_map = synchrotron_map / flux
            synchrotron_map = synchrotron_map.to('sr-1')

        else:
            synchrotron_map = synchrotron_map.to('Jy sr-1')
                
        return synchrotron_map



    #==========================================================================================================================
    #==========================================================================================================================
    #==========================================================================================================================

    
    #==================================================
    # Compute Ysph
    #==================================================

    def get_ysph_profile(self, radius=np.logspace(0,4,1000)*u.kpc):
        """
        Get the spherically integrated Compton parameter profile.
        
        Parameters
        ----------
        - radius (quantity) : the physical 3d radius in units homogeneous to kpc, as a 1d array

        Outputs
        ----------
        - radius (quantity): the 3d radius in unit of kpc
        - Ysph_r (quantity): the integrated Compton parameter (homogeneous to kpc^2)

        """

        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        #---------- Define radius associated to the pressure
        press_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'), Rmin=1.0, Nptmin=1000)*u.kpc
        
        #---------- Get the density profile
        rad, p_r = self.get_pressure_gas_profile(radius=press_radius)

        #---------- Integrate the pressure in 3d
        I_p_gas_r = np.zeros(len(radius))
        for i in range(len(radius)):
            I_p_gas_r[i] = cluster_profile.get_volume_any_model(rad.to_value('kpc'), p_r.to_value('keV cm-3'),
                                                                radius.to_value('kpc')[i], Npt=1000)
        
        Ysph_r = const.sigma_T/(const.m_e*const.c**2) * I_p_gas_r*u.Unit('keV cm-3 kpc3')

        return radius, Ysph_r.to('kpc2')


    #==================================================
    # Compute Ycyl
    #==================================================

    def get_ycyl_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100):
        """
        Get the integrated cylindrical Compton parameter profile.
        
        Parameters
        ----------
        - radius (quantity) : the physical 3d radius in units homogeneous to kpc, as a 1d array
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration
        
        Outputs
        ----------
        - radius (quantity): the 3d radius in unit of kpc
        - Ycyl_r : the integrated Compton parameter

        """

        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        #---------- Define radius associated to the Compton parameter
        y_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'), Rmin=1.0, Nptmin=1000)*u.kpc
        
        #---------- Get the Compton parameter profile
        r2d, y_r = self.get_y_compton_profile(y_radius, NR500_los=NR500_los, Npt_los=Npt_los)

        #---------- Integrate the Compton parameter in 2d
        Ycyl_r = np.zeros(len(radius))
        for i in range(len(radius)):
            Ycyl_r[i] = cluster_profile.get_surface_any_model(r2d.to_value('kpc'), y_r.to_value('adu'),
                                                              radius.to_value('kpc')[i], Npt=1000)
        
        return radius, Ycyl_r*u.Unit('kpc2')

    
    #==================================================
    # Compute y profile
    #==================================================
    
    def get_y_compton_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100):
        """
        Get the Compton parameter profile.
        
        Parameters
        ----------
        - radius (quantity): the physical 3d radius in units homogeneous to kpc, as a 1d array
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration
        
        Outputs
        ----------
        - Rproj (quantity): the projected 2d radius in unit of kpc
        - y_r : the Compton parameter

        Note
        ----------
        The pressure profile is truncated at R500 along the line-of-sight.

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        # Define radius associated to the pressure
        p_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'),
                                                            Rmin=1.0, Rmax=NR500_los*self._R500.to_value('kpc'),
                                                            Nptmin=1000)*u.kpc
        
        # Get the pressure profile
        rad3d, p_r = self.get_pressure_gas_profile(radius=p_radius)

        # Project it
        Rmax = np.amax(NR500_los*self._R500.to_value('kpc'))  # Max radius to integrate in 3d
        Rpmax = np.amax(radius.to_value('kpc'))              # Max radius to which we get the profile
        Rproj, Pproj = cluster_profile.proj_any_model(rad3d.to_value('kpc'), p_r.to_value('keV cm-3'),
                                                      Npt=Npt_los, Rmax=Rmax, Rpmax=Rpmax, Rp_input=radius.to_value('kpc'))
        
        # Get the Compton parameter
        Rproj *= u.kpc
        y_compton = Pproj*u.Unit('keV cm-3 kpc') * const.sigma_T/(const.m_e*const.c**2)


        # Apply truncation in case
        y_compton[Rproj > self._R_truncation] = 0.0
        
        return Rproj.to('kpc'), y_compton.to_value('')*u.adu

    
    #==================================================
    # Compute y map 
    #==================================================
    
    def get_ymap(self, FWHM=None, NR500_los=5.0, Npt_los=100):
        """
        Compute a Compton parameter ymap.
        
        Parameters
        ----------
        - FWHM (quantity) : the beam smoothing FWHM (homogeneous to deg)
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration

        Outputs
        ----------
        - ymap (adu) : the Compton parameter map

        """
        
        # Get the header
        header = self.get_map_header()
        w = WCS(header)
        if w.wcs.has_cd():
            if w.wcs.cd[1,0] != 0 or w.wcs.cd[0,1] != 0:
                print('!!! WARNING: R.A and Dec. is rotated wrt x and y. The extracted resolution was not checked in such situation.')
            map_reso_x = np.sqrt(w.wcs.cd[0,0]**2 + w.wcs.cd[1,0]**2)
            map_reso_y = np.sqrt(w.wcs.cd[1,1]**2 + w.wcs.cd[0,1]**2)
        else:
            map_reso_x = np.abs(w.wcs.cdelt[0])
            map_reso_y = np.abs(w.wcs.cdelt[1])
        
        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))

        # Define the radius used fo computing the Compton parameter profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min == 0:
            theta_min = 1e-4 # Zero will cause bug, put <1arcsec in this case
        rmax = theta_max*np.pi/180 * self._D_ang.to_value('kpc')
        rmin = theta_min*np.pi/180 * self._D_ang.to_value('kpc')
        radius = np.logspace(np.log10(rmin), np.log10(rmax), 1000)*u.kpc

        # Compute the Compton parameter projected profile
        r_proj, y_profile = self.get_y_compton_profile(radius, NR500_los=NR500_los, Npt_los=Npt_los) # kpc, [y]
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi                                 # degrees
        
        # Interpolate the profile onto the map
        ymap = map_tools.profile2map(y_profile.to_value('adu'), theta_proj, dist_map)
        
        # Avoid numerical residual ringing from interpolation
        ymap[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Smooth the ymap if needed
        if FWHM != None:
            FWHM2sigma = 1.0/(2.0*np.sqrt(2*np.log(2)))
            ymap = ndimage.gaussian_filter(ymap, sigma=(FWHM2sigma*FWHM.to_value('deg')/map_reso_x,
                                                        FWHM2sigma*FWHM.to_value('deg')/map_reso_y), order=0)

        return ymap*u.adu










    
    #==================================================
    # Compute a Xspec table versus temperature
    #==================================================
    
    def get_sx_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100,
                       output_type='S'):
        """
        Compute a surface brightness Xray profile. An xspec table file is needed as 
        output_dir+'/XSPEC_table.txt'.
        
        Parameters
        ----------
        - radius (quantity): the physical 3d radius in units homogeneous to kpc, as a 1d array
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration
        - output_type (str): type of ooutput to provide: 
        S == energy counts in erg/s/cm^2/sr
        C == counts in ph/s/cm^2/sr
        R == count rate in ph/s/sr (accounting for instrumental response)
        
        Outputs
        ----------
        - Rproj (quantity): the projected 2d radius in unit of kpc
        - Sx (quantity): the Xray surface brightness projectes profile

        """

        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        # Get the gas density profile
        n_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'),
                                                            Rmin=1.0, Rmax=NR500_los*self._R500.to_value('kpc'),
                                                            Nptmin=1000)*u.kpc

        # Get the density and temperature profile
        rad3d, n_e  = self.get_density_gas_profile(radius=n_radius)
        rad3d, T_g  = self.get_temperature_gas_profile(radius=n_radius)

        # Interpolate Xspec table
        dC_xspec, dS_xspec, dR_xspec = self.itpl_xspec_table(self._output_dir+'/XSPEC_table.txt', T_g)
        if np.sum(~np.isnan(dR_xspec)) == 0 and output_type == 'R':
            raise ValueError("You ask for an output in ph/s/sr (i.e. including instrumental response), but the xspec table was generated without response file.")

        # Get the integrand
        mu_gas, mu_e, mu_p, mu_alpha = cluster_global.mean_molecular_weight(Y=self._helium_mass_fraction,
                                                                            Z=self._metallicity_sol*self._abundance)
        constant = 1e-14/(4*np.pi*self._D_ang**2*(1+self._redshift)**2)

        if output_type == 'S':
            integrand = constant.to_value('kpc-2')*dS_xspec.to_value('erg cm3 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        elif output_type == 'C':
            integrand = constant.to_value('kpc-2')*dC_xspec.to_value('cm3 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        elif output_type == 'R':
            integrand = constant.to_value('kpc-2')*dR_xspec.to_value('cm5 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        # Projection to get Emmission Measure            
        Rmax = np.amax(NR500_los*self._R500.to_value('kpc'))  # Max radius to integrate in 3d
        Rpmax = np.amax(radius.to_value('kpc'))              # Max radius to which we get the profile
        Rproj, Sx = cluster_profile.proj_any_model(rad3d.to_value('kpc'), integrand,
                                                   Npt=Npt_los, Rmax=Rmax, Rpmax=Rpmax, Rp_input=radius.to_value('kpc'))
        Rproj *= u.kpc
        Sx[Rproj > self._R_truncation] = 0.0

        # write unit explicitlly
        if output_type == 'S':
            Sx *= u.kpc * u.kpc**-2 * u.erg*u.cm**3/u.s * u.cm**-6
            Sx = (Sx*self._D_ang**2).to('erg s-1 cm-2')/u.sr
            Sx.to('erg s-1 cm-2 sr-1')
        elif output_type == 'C':
            Sx *= u.kpc * u.kpc**-2 * u.cm**3/u.s * u.cm**-6
            Sx = (Sx*self._D_ang**2).to('s-1 cm-2')/u.sr
            Sx.to('s-1 cm-2 sr-1')
        elif output_type == 'R':
            Sx *= u.kpc * u.kpc**-2 * u.cm**5/u.s * u.cm**-6
            Sx = (Sx*self._D_ang**2).to('s-1')/u.sr
            Sx.to('s-1 sr-1')
        else:
            raise ValueError("Output type available are S, C and R.")
        
        return Rproj.to('kpc'), Sx

    
    #==================================================
    # Compute Xray spherical flux
    #==================================================

    def get_fxsph_profile(self, radius=np.logspace(0,4,1000)*u.kpc, output_type='S'):
        """
        Get the spherically integrated Xray flux profile.
        
        Parameters
        ----------
        - radius (quantity) : the physical 3d radius in units homogeneous to kpc, as a 1d array
        - output_type (str): type of ooutput to provide: 
        S == energy counts in erg/s/cm^2/sr
        C == counts in ph/s/cm^2/sr
        R == count rate in ph/s/sr (accounting for instrumental response)
        
        Outputs
        ----------
        - radius (quantity): the 3d radius in unit of kpc
        - Fsph_r (quantity): the integrated Xray flux parameter erg/s/cm2

        """

        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        #---------- Define radius associated to the density/temperature
        press_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'), Rmin=1.0, Nptmin=1000)*u.kpc
        n_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'), Rmin=1.0, Nptmin=1000)*u.kpc
        
        #---------- Get the density profile and temperature
        rad, n_e  = self.get_density_gas_profile(radius=n_radius)
        rad, T_g  = self.get_temperature_gas_profile(radius=n_radius)

        #---------- Interpolate the differential surface brightness
        dC_xspec, dS_xspec, dR_xspec = self.itpl_xspec_table(self._output_dir+'/XSPEC_table.txt', T_g)
        
        #---------- Get the integrand
        mu_gas, mu_e, mu_p, mu_alpha = cluster_global.mean_molecular_weight(Y=self._helium_mass_fraction,
                                                                            Z=self._metallicity_sol*self._abundance)
        constant = 1e-14/(4*np.pi*self._D_ang**2*(1+self._redshift)**2)
        if output_type == 'S':
            integrand = constant.to_value('kpc-2')*dS_xspec.to_value('erg cm3 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        elif output_type == 'C':
            integrand = constant.to_value('kpc-2')*dC_xspec.to_value('cm3 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        elif output_type == 'R':
            integrand = constant.to_value('kpc-2')*dR_xspec.to_value('cm5 s-1') * n_e.to_value('cm-3')**2 * mu_e/mu_p
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        #---------- Integrate in 3d
        EI_r = np.zeros(len(radius))
        for i in range(len(radius)):
            EI_r[i] = cluster_profile.get_volume_any_model(rad.to_value('kpc'), integrand,
                                                           radius.to_value('kpc')[i], Npt=1000)
        if output_type == 'S':
            flux_r = EI_r*u.Unit('kpc-2 erg cm3 s-1 cm-6 kpc3')
            flux_r = flux_r.to('erg s-1 cm-2')
        elif output_type == 'C':
            flux_r = EI_r*u.Unit('kpc-2 cm3 s-1 cm-6 kpc3')
            flux_r = flux_r.to('s-1 cm-2')
        elif output_type == 'R':
            flux_r = EI_r*u.Unit('kpc-2 cm5 s-1 cm-6 kpc3')
            flux_r = flux_r.to('s-1')
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        return radius, flux_r


    #==================================================
    # Compute Xray cylindrical flux
    #==================================================

    def get_fxcyl_profile(self, radius=np.logspace(0,4,1000)*u.kpc, NR500_los=5.0, Npt_los=100,
                          output_type='S'):
        """
        Get the cylindrically integrated Xray flux profile.
        
        Parameters
        ----------
        - radius (quantity) : the physical 3d radius in units homogeneous to kpc, as a 1d array
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration
        - output_type (str): type of ooutput to provide: 
        S == energy counts in erg/s/cm^2/sr
        C == counts in ph/s/cm^2/sr
        R == count rate in ph/s/sr (accounting for instrumental response)
        
        Outputs
        ----------
        - radius (quantity): the 3d radius in unit of kpc
        - Fcyl_r (quantity): the integrated Xray flux parameter erg/s/cm2

        """
        
        # In case the input is not an array
        radius = model_tools.check_qarray(radius)

        #---------- Define radius associated to the Sx profile
        sx_radius = cluster_profile.define_safe_radius_array(radius.to_value('kpc'), Rmin=1.0, Nptmin=1000)*u.kpc
        
        #---------- Get the Sx profile
        r2d, sx_r = self.get_sx_profile(sx_radius, NR500_los=NR500_los, Npt_los=Npt_los, output_type=output_type)

        #---------- Integrate the Compton parameter in 2d
        if output_type == 'S':
            integrand = sx_r.to_value('erg s-1 cm-2 sr-1')
        elif output_type == 'C':
            integrand = sx_r.to_value('s-1 cm-2 sr-1')
        elif output_type == 'R':
            integrand = sx_r.to_value('s-1 sr-1')
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        Fcyl_r = np.zeros(len(radius))
        for i in range(len(radius)):
            Fcyl_r[i] = cluster_profile.get_surface_any_model(r2d.to_value('kpc'), integrand,
                                                              radius.to_value('kpc')[i], Npt=1000)
        if output_type == 'S':
            flux_r = Fcyl_r / self._D_ang.to_value('kpc')**2 * u.Unit('erg s-1 cm-2')
        elif output_type == 'C':
            flux_r = Fcyl_r / self._D_ang.to_value('kpc')**2 * u.Unit('s-1 cm-2')
        elif output_type == 'R':
            flux_r = Fcyl_r / self._D_ang.to_value('kpc')**2 * u.Unit('s-1')
        else:
            raise ValueError("Output type available are S, C and R.")        
                
        return radius, flux_r


    #==================================================
    # Compute Sx map 
    #==================================================
    
    def get_sxmap(self, FWHM=None, NR500_los=5.0, Npt_los=100,
                  output_type='S'):
        """
        Compute a Surface brightness X-ray mmap.
        
        Parameters
        ----------
        - FWHM (quantity) : the beam smoothing FWHM (homogeneous to deg)
        - NR500_los (float): the integration will stop at NR500_los x R500
        - Npt_los (int): the number of points for line of sight integration
        - output_type (str): type of ooutput to provide: 
        S == energy counts in erg/s/cm^2/sr
        C == counts in ph/s/cm^2/sr
        R == count rate in ph/s/sr (accounting for instrumental response)
        
        Outputs
        ----------
        - sxmap (quantity) : the Sx map

        """
        
        # Get the header
        header = self.get_map_header()
        w = WCS(header)
        if w.wcs.has_cd():
            if w.wcs.cd[1,0] != 0 or w.wcs.cd[0,1] != 0:
                print('!!! WARNING: R.A and Dec. is rotated wrt x and y. The extracted resolution was not checked in such situation.')
            map_reso_x = np.sqrt(w.wcs.cd[0,0]**2 + w.wcs.cd[1,0]**2)
            map_reso_y = np.sqrt(w.wcs.cd[1,1]**2 + w.wcs.cd[0,1]**2)
        else:
            map_reso_x = np.abs(w.wcs.cdelt[0])
            map_reso_y = np.abs(w.wcs.cdelt[1])
        
        # Get a R.A-Dec. map
        ra_map, dec_map = map_tools.get_radec_map(header)

        # Get a cluster distance map
        dist_map = map_tools.greatcircle(ra_map, dec_map, self._coord.icrs.ra.to_value('deg'), self._coord.icrs.dec.to_value('deg'))

        # Define the radius used fo computing the Sx profile
        theta_max = np.amax(dist_map) # maximum angle from the cluster
        theta_min = np.amin(dist_map) # minimum angle from the cluster (~0 if cluster within FoV)
        if theta_min == 0:
            theta_min = 1e-4 # Zero will cause bug, put <1arcsec in this case
        rmax = theta_max*np.pi/180 * self._D_ang.to_value('kpc')
        rmin = theta_min*np.pi/180 * self._D_ang.to_value('kpc')
        radius = np.logspace(np.log10(rmin), np.log10(rmax), 1000)*u.kpc

        # Compute the Compton parameter projected profile
        r_proj, sx_profile = self.get_sx_profile(radius, NR500_los=NR500_los, Npt_los=Npt_los, output_type=output_type)
        theta_proj = (r_proj/self._D_ang).to_value('')*180.0/np.pi                           # degrees
        
        # Interpolate the profile onto the map
        if output_type == 'S':
            sxmap = map_tools.profile2map(sx_profile.to_value('erg s-1 cm-2 sr-1'), theta_proj, dist_map)
        elif output_type == 'C':
            sxmap = map_tools.profile2map(sx_profile.to_value('s-1 cm-2 sr-1'), theta_proj, dist_map)
        elif output_type == 'R':
            sxmap = map_tools.profile2map(sx_profile.to_value('s-1 sr-1'), theta_proj, dist_map)
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        # Avoid numerical residual ringing from interpolation
        sxmap[dist_map > self._theta_truncation.to_value('deg')] = 0
        
        # Smooth the ymap if needed
        if FWHM != None:
            FWHM2sigma = 1.0/(2.0*np.sqrt(2*np.log(2)))
            sxmap = ndimage.gaussian_filter(sxmap, sigma=(FWHM2sigma*FWHM.to_value('deg')/map_reso_x,
                                                          FWHM2sigma*FWHM.to_value('deg')/map_reso_y), order=0)
        # Units and return
        if output_type == 'S':
            sxmap = sxmap*u.Unit('erg s-1 cm-2 sr-1')
        elif output_type == 'C':
            sxmap = sxmap*u.Unit('s-1 cm-2 sr-1')
        elif output_type == 'R':
            sxmap = sxmap*u.Unit('s-1 sr-1')
        else:
            raise ValueError("Output type available are S, C and R.")        
        
        return sxmap

