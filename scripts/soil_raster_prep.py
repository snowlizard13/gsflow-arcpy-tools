#--------------------------------
# Name:         soil_raster_prep.py
# Purpose:      GSFLOW soil raster prep
# Notes:        ArcGIS 10.2 Version
# Author:       Charles Morton
# Created       2016-08-04
# Python:       2.7
#--------------------------------

import argparse
import ConfigParser
import datetime as dt
import logging
import os
import sys

import arcpy
from arcpy import env

import support_functions as support


def soil_raster_prep(config_path, overwrite_flag=False, debug_flag=False):
    """Prepare GSFLOW soil rasters

    Args:
        config_file (str): Project config file path
        ovewrite_flag (bool): if True, overwrite existing files
        debug_flag (bool): if True, enable debug level logging

    Returns:
        None
    """

    # Initialize hru_parameters class
    hru = support.HRUParameters(config_path)

    # Open input parameter config file
    inputs_cfg = ConfigParser.ConfigParser()
    try:
        inputs_cfg.readfp(open(config_path))
    except:
        logging.error('\nERROR: Config file could not be read, ' +
                      'is not an input file, or does not exist\n' +
                      'ERROR: config_file = {}\n').format(config_path)
        sys.exit()

    # Log DEBUG to file
    log_file_name = 'soil_prep_log.txt'
    log_console = logging.FileHandler(
        filename=os.path.join(hru.log_ws, log_file_name), mode='w')
    log_console.setLevel(logging.DEBUG)
    log_console.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger('').addHandler(log_console)
    logging.info('\nPrepare GSFLOW Soil Rasters')

    soil_orig_ws  = inputs_cfg.get('INPUTS', 'soil_orig_folder')
    awc_name      = inputs_cfg.get('INPUTS', 'awc_name')
    clay_pct_name = inputs_cfg.get('INPUTS', 'clay_pct_name')
    sand_pct_name = inputs_cfg.get('INPUTS', 'sand_pct_name')
    # silt_pct_name = inputs_cfg.get('INPUTS', 'silt_pct_name')
    soil_proj_method = 'NEAREST'
    soil_cs = inputs_cfg.getint('INPUTS', 'soil_cellsize')
    fill_soil_nodata_flag = inputs_cfg.getboolean(
        'INPUTS', 'fill_soil_nodata_flag')

# Use Ksat to calculate ssr2gw_rate and slowcoef_lin
    # calc_ssr2gw_rate_flag = inputs_cfg.getboolean(
    #    'INPUTS', 'calc_ssr2gw_rate_flag')
    # calc_slowcoef_flag = inputs_cfg.getboolean(
    #    'INPUTS', 'calc_slowcoef_flag')
    # if calc_ssr2gw_rate_flag or calc_slowcoef_flag:
    ksat_name = inputs_cfg.get('INPUTS', 'ksat_name')

    # Clip root depth to soil depth
    clip_root_depth_flag = inputs_cfg.getboolean(
        'INPUTS', 'clip_root_depth_flag')
    if clip_root_depth_flag:
        soil_depth_name = inputs_cfg.get('INPUTS', 'soil_depth_name')

    # Check input paths
    if not arcpy.Exists(hru.polygon_path):
        logging.error(
            '\nERROR: Fishnet ({}) does not exist'.format(
                hru.polygon_path))
        sys.exit()
    # All of the soil rasters must exist
    awc_orig_path = os.path.join(soil_orig_ws, awc_name)
    clay_pct_orig_path = os.path.join(soil_orig_ws, clay_pct_name)
    sand_pct_orig_path = os.path.join(soil_orig_ws, sand_pct_name)
    # silt_orig_path = os.path.join(soil_orig_ws, silt_pct_name)
    # if calc_ssr2gw_rate_flag or calc_slowcoef_flag:
    ksat_orig_path = os.path.join(soil_orig_ws, ksat_name)
    if clip_root_depth_flag:
        soil_depth_path = os.path.join(soil_orig_ws, soil_depth_name)

    # Check that either the original or projected/clipped raster exists
    if not arcpy.Exists(awc_orig_path):
        logging.error('\nERROR: AWC raster does not exist')
        sys.exit()
    if not arcpy.Exists(clay_pct_orig_path):
        logging.error('\nERROR: Clay raster does not exist')
        sys.exit()
    if not arcpy.Exists(sand_pct_orig_path):
        logging.error('\nERROR: Sand raster does not exist')
        sys.exit()
    # if not arcpy.Exists(silt_orig_path):
    #    logging.error('\nERROR: Silt raster does not exist')
    #    sys.exit()
    # if ((calc_ssr2gw_rate_flag or calc_slowcoef_flag) and
    #    not arcpy.Exists(ksat_orig_path)):
    if not arcpy.Exists(ksat_orig_path):
        logging.error('\nERROR: Ksat raster does not exist')
        sys.exit()
    if clip_root_depth_flag and not arcpy.Exists(soil_depth_orig_path):
        logging.error('\nERROR: Soil depth raster does not exist')
        sys.exit()

    # Check other inputs
    if soil_cs <= 0:
        logging.error('\nERROR: soil cellsize must be greater than 0')
        sys.exit()
    soil_proj_method_list = ['BILINEAR', 'CUBIC', 'NEAREST']
    if soil_proj_method.upper() not in soil_proj_method_list:
        logging.error('\nERROR: Soil projection method must be: {}'.format(
            ', '.join(soil_proj_method_list)))
        sys.exit()

    # Build output folder if necessary
    soil_temp_ws = os.path.join(hru.param_ws, 'soil_rasters')
    if not os.path.isdir(soil_temp_ws):
        os.mkdir(soil_temp_ws)
    # Output paths
    awc_path = os.path.join(soil_temp_ws, 'awc.img')
    clay_pct_path = os.path.join(soil_temp_ws, 'clay_pct.img')
    sand_pct_path = os.path.join(soil_temp_ws, 'sand_pct.img')
    # silt_pct_path = os.path.join(soil_temp_ws, 'silt_pct.img')
    ksat_path = os.path.join(soil_temp_ws, 'ksat.img')
    soil_depth_path = os.path.join(soil_temp_ws, 'soil_depth.img')

    # Root depth is calculated by veg script
    # veg_temp_ws = os.path.join(hru.param_ws, 'veg_rasters')
    # root_depth_path = os.path.join(veg_temp_ws, 'root_depth.img')
    # if not arcpy.Exists(root_depth_path):
    #    logging.error(
    #        '\nERROR: Root depth raster does not exists' +
    #        '\nERROR: Try re-running veg_parameters script\n')
    #    sys.exit()


    # Set ArcGIS environment variables
    arcpy.CheckOutExtension('Spatial')
    env.overwriteOutput = True
    env.pyramid = 'PYRAMIDS -1'
    # env.pyramid = 'PYRAMIDS 0'
    env.workspace = soil_temp_ws
    env.scratchWorkspace = hru.scratch_ws

    # Available Water Capacity (AWC)
    logging.info('\nProjecting/clipping AWC raster')
    soil_orig_sr = arcpy.sa.Raster(awc_orig_path).spatialReference
    logging.debug('  AWC GCS:  {}'.format(
        soil_orig_sr.GCS.name))
    # Remove existing projected raster
    if arcpy.Exists(awc_path):
        arcpy.Delete_management(awc_path)
    # Set preferred transforms
    transform_str = support.transform_func(hru.sr, soil_orig_sr)
    logging.debug('  Transform: {}'.format(transform_str))
    logging.debug('  Projection method: NEAREST')
    # Project soil raster
    # DEADBEEF - Arc10.2 ProjectRaster does not honor extent
    support.project_raster_func(
        awc_orig_path, awc_path, hru.sr,
        soil_proj_method, soil_cs, transform_str,
        '{} {}'.format(hru.ref_x, hru.ref_y), soil_orig_sr, hru)
    # env.extent = hru.extent
    # arcpy.ProjectRaster_management(
    #    awc_orig_path, awc_path, hru.sr,
    #    soil_proj_method, soil_cs, transform_str,
    #    '{} {}'.format(hru.ref_x, hru.ref_y),
    #    soil_orig_sr)
    # arcpy.ClearEnvironment('extent')

    # Percent clay
    logging.info('Projecting/clipping clay raster')
    soil_orig_sr = arcpy.sa.Raster(clay_pct_orig_path).spatialReference
    logging.debug('  Clay GCS: {}'.format(
        soil_orig_sr.GCS.name))
    # Remove existing projected raster
    if arcpy.Exists(clay_pct_path):
        arcpy.Delete_management(clay_pct_path)
    # Set preferred transforms
    transform_str = support.transform_func(hru.sr, soil_orig_sr)
    logging.debug('  Transform: {}'.format(transform_str))
    logging.debug('  Projection method: NEAREST')
    # Project soil raster
    # DEADBEEF - Arc10.2 ProjectRaster does not extent
    support.project_raster_func(
        clay_pct_orig_path, clay_pct_path, hru.sr,
        soil_proj_method, soil_cs, transform_str,
        '{} {}'.format(hru.ref_x, hru.ref_y), soil_orig_sr, hru)
    # env.extent = hru.extent
    # arcpy.ProjectRaster_management(
    #    clay_pct_orig_path, clay_pct_path, hru.sr,
    #    soil_proj_method, soil_cs, transform_str,
    #    '{} {}'.format(hru.ref_x, hru.ref_y),
    #    soil_orig_sr)
    # arcpy.ClearEnvironment('extent')

    # Percent sand
    logging.info('Projecting/clipping sand raster')
    soil_orig_sr = arcpy.sa.Raster(sand_pct_orig_path).spatialReference
    logging.debug('  Sand GCS: {}'.format(
        soil_orig_sr.GCS.name))
    # Remove existing projected raster
    if arcpy.Exists(sand_pct_path):
        arcpy.Delete_management(sand_pct_path)
    # Set preferred transforms
    transform_str = support.transform_func(hru.sr, soil_orig_sr)
    logging.debug('  Transform: {}'.format(transform_str))
    logging.debug('  Projection method: NEAREST')
    # Project soil raster
    # DEADBEEF - Arc10.2 ProjectRaster does not honor extent
    support.project_raster_func(
        sand_pct_orig_path, sand_pct_path, hru.sr,
        soil_proj_method, soil_cs, transform_str,
        '{} {}'.format(hru.ref_x, hru.ref_y), soil_orig_sr, hru)
    # env.extent = hru.extent
    # arcpy.ProjectRaster_management(
    #    sand_pct_orig_path, sand_pct_path, hru.sr,
    #    soil_proj_method, soil_cs, transform_str,
    #    '{} {}'.format(hru.ref_x, hru.ref_y),
    #    soil_orig_sr)
    # arcpy.ClearEnvironment('extent')

    # Hydraulic conductivity
    # if calc_ssr2gw_rate_flag or calc_slowcoef_flag:
    logging.info('Projecting/clipping ksat raster')
    ksat_orig_sr = arcpy.sa.Raster(ksat_orig_path).spatialReference
    logging.debug('  Ksat GCS: {}'.format(
        soil_orig_sr.GCS.name))
    # Remove existing projected raster
    if arcpy.Exists(ksat_path):
        arcpy.Delete_management(ksat_path)
    # Set preferred transforms
    transform_str = support.transform_func(hru.sr, ksat_orig_sr)
    logging.debug('  Transform: {}'.format(transform_str))
    logging.debug('  Projection method: NEAREST')
    # Project ksat raster
    # DEADBEEF - Arc10.2 ProjectRaster does not honor extent
    support.project_raster_func(
        ksat_orig_path, ksat_path, hru.sr,
        soil_proj_method, soil_cs, transform_str,
        '{} {}'.format(hru.ref_x, hru.ref_y), soil_orig_sr, hru)
    # env.extent = hru.extent
    # arcpy.ProjectRaster_management(
    #    ksat_orig_path, ksat_path, hru.sr,
    #    soil_proj_method, soil_cs, transform_str,
    #    '{} {}'.format(hru.ref_x, hru.ref_y),
    #    soil_orig_sr)
    # arcpy.ClearEnvironment('extent')

    # Soil depth is only needed if clipping root depth
    if clip_root_depth_flag:
        logging.info('\nProjecting/clipping depth raster')
        soil_orig_sr = arcpy.sa.Raster(soil_depth_orig_path).spatialReference
        logging.debug('  Depth GCS: {}'.format(
            soil_orig_sr.GCS.name))
        # Remove existing projected raster
        if arcpy.Exists(soil_depth_path):
            arcpy.Delete_management(soil_depth_path)
        # Set preferred transforms
        transform_str = support.transform_func(hru.sr, soil_orig_sr)
        logging.debug('  Transform: {}'.format(transform_str))
        logging.debug('  Projection method: NEAREST')
        # Project soil raster
        # DEADBEEF - Arc10.2 ProjectRaster does not honor extent
        support.project_raster_func(
            soil_depth_orig_path, soil_depth_path, hru.sr,
            soil_proj_method, soil_cs, transform_str,
            '{} {}'.format(hru.ref_x, hru.ref_y), soil_orig_sr, hru)
        # env.extent = hru.extent
        # arcpy.ProjectRaster_management(
        #    soil_depth_orig_path, soil_depth_path, hru.sr,
        #    soil_proj_method, soil_cs, transform_str,
        #    '{} {}'.format(hru.ref_x, hru.ref_y),
        #    soil_orig_sr)
        # arcpy.ClearEnvironment('extent')

    # Clip root depth to soil depth
    # if clip_root_depth_flag:
    #    # This will clip root depth to soil depth
    #    # Minimum of root depth and soil depth
    #    logging.info('Clipping root depth to soil depth')
    #    root_depth_obj = Con(
    #       arcpy.sa.Raster(root_depth_path) <arcpy.sa.Raster(soil_depth_path),
    #       arcpy.sa.Raster(root_depth_path),arcpy.sa.Raster(soil_depth_path))
    #    root_depth_obj.save(root_depth_path)
    #    del root_depth_obj

    # Fill soil nodata values using nibble
    if fill_soil_nodata_flag:
        logging.info('\nFilling soil nodata values using Nibble')
        soil_raster_list = [
            awc_path, clay_pct_path, sand_pct_path, ksat_path]
        if clip_root_depth_flag:
            soil_raster_list.append(soil_depth_path)
        for soil_raster_path in soil_raster_list:
            logging.info('  {}'.format(soil_raster_path))
            # DEADBEEF - Check if there is any nodata to be filled first?
            mask_obj = Int(1000 * SetNull(
               arcpy.sa.Raster(soil_raster_path) < 0,arcpy.sa.Raster(soil_raster_path)))
            input_obj = Con(IsNull(mask_obj), 0, mask_obj)
            nibble_obj = 0.001 * Nibble(input_obj, mask_obj, 'ALL_VALUES')
            nibble_obj.save(soil_raster_path)
            arcpy.BuildPyramids_management(soil_raster_path)


def arg_parse():
    """"""
    parser = argparse.ArgumentParser(
        description='Soil Raster Prep',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '-i', '--ini', required=True,
        help='Project input file', metavar='PATH')
    parser.add_argument(
        '-o', '--overwrite', default=False, action="store_true",
        help='Force overwrite of existing files')
    parser.add_argument(
        '-d', '--debug', default=logging.INFO, const=logging.DEBUG,
        help='Debug level logging', action="store_const", dest="loglevel")
    args = parser.parse_args()

    # Convert input file to an absolute path
    if os.path.isfile(os.path.abspath(args.ini)):
        args.ini = os.path.abspath(args.ini)
    return args


if __name__ == '__main__':
    args = arg_parse()

    logging.basicConfig(level=args.loglevel, format='%(message)s')
    logging.info('\n{}'.format('#' * 80))
    log_f = '{:<20s} {}'
    logging.info(log_f.format(
        'Run Time Stamp:', dt.datetime.now().isoformat(' ')))
    logging.info(log_f.format('Current Directory:', os.getcwd()))
    logging.info(log_f.format('Script:', os.path.basename(sys.argv[0])))

    # Prepare GSFLOW Soil Rasters
    soil_raster_prep(
        config_path=args.ini, overwrite_flag=args.overwrite,
        debug_flag=args.loglevel==logging.DEBUG)
