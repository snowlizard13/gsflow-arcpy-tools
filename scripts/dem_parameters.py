#--------------------------------
# Name:         dem_parameters.py
# Purpose:      GSFLOW DEM parameters
# Notes:        ArcGIS 10.2 Version
# Author:       Charles Morton
# Created       2016-08-05
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


def dem_parameters(config_path, overwrite_flag=False, debug_flag=False):
    """Calculate GSFLOW DEM Parameters

    Args:
        config_path: Project config file path
        ovewrite_flag (bool): if True, overwrite existing files
        debug_flag (bool): if True, enable debug level logging

    Returns:
        None
    """

    # Initialize hru parameters class
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
    logging.debug('\nReading Input File')

    # Log DEBUG to file
    log_file_name = 'dem_parameters_log.txt'
    log_console = logging.FileHandler(
        filename=os.path.join(hru.log_ws, log_file_name), mode='w')
    log_console.setLevel(logging.DEBUG)
    log_console.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger('').addHandler(log_console)
    logging.info('\nGSFLOW DEM Parameters')

    #
    dem_orig_path = inputs_cfg.get('INPUTS', 'dem_orig_path')
    # Resampling method 'BILINEAR', 'CUBIC', 'NEAREST'
    dem_proj_method = inputs_cfg.get('INPUTS', 'dem_projection_method').upper()
    dem_cs = inputs_cfg.getint('INPUTS', 'dem_cellsize')

    #
    reset_dem_adj_flag = inputs_cfg.getboolean('INPUTS', 'reset_dem_adj_flag')
    dem_adj_copy_field = inputs_cfg.get('INPUTS', 'dem_adj_copy_field')

    # Use PRISM temperature to set Jensen-Haise coefficient
    calc_prism_jh_coef_flag = inputs_cfg.getboolean(
        'INPUTS', 'calc_prism_jh_coef_flag')

    # Calculate flow accumulation weighted elevation
    calc_flow_acc_dem_flag = inputs_cfg.getboolean(
        'INPUTS', 'calc_flow_acc_dem_flag')
    if calc_flow_acc_dem_flag:
        # Get factor for scaling dem_flowacc values to avoid 32 bit int limits
        try:
            flow_acc_dem_factor = float(
                inputs_cfg.get('INPUTS', 'flow_acc_dem_factor'))
        except:
            # This is a worst case for keeping flow_acc_dem from exceeding 2E9
            # Assume all cells flow to 1 cell
            flow_acc_dem_factor = int(
                arcpy.GetCount_management(hru.point_path).getOutput(0))
            # Assume flow acc is in every DEM cell in HRU cell
            flow_acc_dem_factor *= (float(hru.cs) / dem_cs) ** 2
            # Need to account for the elevation in this worst cell
            # For now just make it 100
            # flow_acc_dem_factor *= max_elevation
            flow_acc_dem_factor *= 100
            # Calculate ratio of flow_acc_dem to a 32 bit int
            flow_acc_dem_factor /= (0.5 * 2**32)
            # If the ratio is less than 0.1, round up to 0.1 so factor -> 1.0
            flow_acc_dem_factor = min(0.1, flow_acc_dem_factor)
            # Round up to next multiple of 10 just to be safe
            flow_acc_dem_factor = 1.0 / 10 ** (int(math.log10(flow_acc_dem_factor)) + 1)
            logging.info(
                ('  flow_acc_dem_factor was not set in the input file\n' +
                 '  Using automatic flow_acc_dem_factor: {}').format(
                     flow_acc_dem_factor))

    # Calc flow_acc/flow_dir
    # DEADBEEF - For now, set these to True only if needed
    # calc_flow_acc_flag = inputs_cfg.getboolean('INPUTS', 'calc_flow_acc_flag')
    # calc_flow_dir_flag = inputs_cfg.getboolean('INPUTS', 'calc_flow_dir_flag')
    if calc_flow_acc_dem_flag:
        calc_flow_acc_flag = True
        calc_flow_dir_flag = True
    else:
        calc_flow_acc_flag = False
        calc_flow_dir_flag = False

    # Remap
    remap_ws = inputs_cfg.get('INPUTS', 'remap_folder')
    aspect_remap_name = inputs_cfg.get('INPUTS', 'aspect_remap')
    temp_adj_remap_name = inputs_cfg.get('INPUTS', 'temp_adj_remap')

    # Check input paths
    if not arcpy.Exists(hru.polygon_path):
        logging.error(
            '\nERROR: Fishnet ({}) does not exist\n'.format(hru.polygon_path))
        sys.exit()
    # Check that either the original DEM raster exists
    if not arcpy.Exists(dem_orig_path):
        logging.error(
            '\nERROR: DEM ({}) raster does not exist\n'.format(dem_orig_path))
        sys.exit()
    # Check that remap folder is valid
    if not os.path.isdir(remap_ws):
        logging.error('\nERROR: Remap folder does not exist\n')
        sys.exit()
    # Check that remap files exist
    # Check remap files comment style
    aspect_remap_path = os.path.join(remap_ws, aspect_remap_name)
    temp_adj_remap_path = os.path.join(remap_ws, temp_adj_remap_name)
    remap_path_list = [aspect_remap_path, temp_adj_remap_path]
    for remap_path in remap_path_list:
        support.remap_check(remap_path)

    # DEADBEEF
    # if not os.path.isfile(aspect_remap_path):
    #    logging.error(
    #        '\nERROR: ASCII remap file ({}) does not exist\n'.format(
    #            os.path.basename(aspect_remap_path)))
    #    sys.exit()
    # if not os.path.isfile(temp_adj_remap_path):
    #    logging.error(
    #        '\nERROR: ASCII remap file ({}) does not exist\n'.format(
    #            os.path.basename(temp_adj_remap_path)))
    #    sys.exit()
    #  Check remap files comment style
    # if '10.2' in arcpy.GetInstallInfo()['version']:
    #    if remap_comment_check(aspect_remap_path):
    #        logging.error(
    #            ('\nERROR: ASCII remap file ({}) has pre-ArcGIS 10.2 ' +
    #             'comments\n').format(os.path.basename(aspect_remap_path)))
    #        sys.exit()
    #    if remap_comment_check(temp_adj_remap_path):
    #        logging.error(
    #            ('\nERROR: ASCII remap file ({}) has pre-ArcGIS 10.2 ' +
    #             'comments\n').format(os.path.basename(temp_adj_remap_path)))
    #        sys.exit()

    # Check other inputs
    if dem_cs <= 0:
        logging.error('\nERROR: DEM cellsize must be greater than 0')
        sys.exit()
    dem_proj_method_list = ['BILINEAR', 'CUBIC', 'NEAREST']
    if dem_proj_method not in dem_proj_method_list:
        logging.error('\nERROR: DEM projection method must be: {}'.format(
            ', '.join(dem_proj_method_list)))
        sys.exit()
    if reset_dem_adj_flag:
        logging.warning('\nWARNING: All values in {} will be overwritten'.format(
            hru.dem_adj_field))
        raw_input('  Press ENTER to continue')


    # Build output folder if necessary
    dem_temp_ws = os.path.join(hru.param_ws, 'dem_rasters')
    if not os.path.isdir(dem_temp_ws):
        os.mkdir(dem_temp_ws)

    # Output paths
    dem_path = os.path.join(dem_temp_ws, 'dem.img')
    dem_fill_path = os.path.join(dem_temp_ws, 'dem_fill.img')
    flow_dir_path = os.path.join(dem_temp_ws, 'flow_dir.img')
    flow_acc_path = os.path.join(dem_temp_ws, 'flow_acc.img')
    flow_acc_dem_path = os.path.join(dem_temp_ws, 'flow_acc_x_dem.img')
    flow_acc_filter_path = os.path.join(dem_temp_ws, 'flow_acc_filter.img')
    dem_integer_path = os.path.join(dem_temp_ws, 'dem_integer.img')
    dem_slope_path = os.path.join(dem_temp_ws, 'dem_slope.img')
    dem_aspect_path = os.path.join(dem_temp_ws, 'dem_aspect.img')
    dem_aspect_reclass_path = os.path.join(dem_temp_ws, 'aspect_reclass.img')
    temp_adj_path = os.path.join(dem_temp_ws, 'temp_adj.img')

    # Set ArcGIS environment variables
    arcpy.CheckOutExtension('Spatial')
    env.overwriteOutput = True
    env.pyramid = 'PYRAMIDS -1'
    # env.pyramid = 'PYRAMIDS 0'
    # env.rasterStatistics = 'NONE'
    # env.extent = 'MINOF'
    env.workspace = dem_temp_ws
    env.scratchWorkspace = hru.scratch_ws

    # Check DEM field
    logging.info('\nAdding DEM fields if necessary')
    support.add_field_func(hru.polygon_path, hru.dem_mean_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_median_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_max_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_min_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_adj_field, 'DOUBLE')
    if calc_flow_acc_dem_flag:
        support.add_field_func(hru.polygon_path, hru.dem_flowacc_field, 'DOUBLE')
        support.add_field_func(hru.polygon_path, hru.dem_sum_field, 'DOUBLE')
        support.add_field_func(hru.polygon_path, hru.dem_count_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_sink8_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_sink4_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_aspect_field, 'LONG')
    support.add_field_func(hru.polygon_path, hru.dem_slope_deg_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_slope_rad_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_slope_pct_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.dem_feet_field, 'DOUBLE')
    # add_field_func(hru.polygon_path, hru.deplcrv_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.jh_tmin_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.jh_tmax_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.jh_coef_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.snarea_thresh_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.tmax_adj_field, 'DOUBLE')
    support.add_field_func(hru.polygon_path, hru.tmin_adj_field, 'DOUBLE')

    # Check that dem_adj_copy_field exists
    if len(arcpy.ListFields(hru.polygon_path, dem_adj_copy_field)) == 0:
        logging.error('\nERROR: dem_adj_copy_field {} does not exist\n'.format(
            dem_adj_copy_field))
        sys.exit()

    # Assume all DEM rasters will need to be rebuilt
    # Check slope, aspect, and proejcted DEM rasters
    # This will check for matching spat. ref., snap point, and cellsize

    # If DEM is GCS, project it to 10m to match
    # DEADBEEF - I had originally wanted the DEM to get projected only once
    #   but if the user wants to rerun this script, then all steps should
    #   be rerun.  This also allows the user to change the DEM raster
    # dem_flag = valid_raster_func(
    #    dem_path, 'projected DEM', hru, dem_cs)
    # if arcpy.Exists(dem_orig_path) and not dem_flag:
    logging.info('\nProjecting DEM raster')
    dem_orig_sr = arcpy.sa.Raster(dem_orig_path).spatialReference
    logging.debug('  DEM GCS:   {}'.format(
        dem_orig_sr.GCS.name))
    # Remove existing projected DEM
    if arcpy.Exists(dem_path):
        arcpy.Delete_management(dem_path)
    # Set preferred transforms
    transform_str = support.transform_func(hru.sr, dem_orig_sr)
    logging.debug('  Transform: {}'.format(transform_str))
    logging.debug('  Projection method: {}'.format(dem_proj_method))
    # Project DEM
    # DEADBEEF - Arc10.2 ProjectRaster does not honor extent
    logging.debug('  Input SR:  {}'.format(dem_orig_sr.exportToString()))
    logging.debug('  Output SR: {}'.format(hru.sr.exportToString()))
    support.project_raster_func(
        dem_orig_path, dem_path, hru.sr,
        dem_proj_method, dem_cs, transform_str,
        '{} {}'.format(hru.ref_x, hru.ref_y),
        dem_orig_sr, hru)
    # env.extent = hru.extent
    # arcpy.ProjectRaster_management(
    #    dem_orig_path, dem_path, hru.sr,
    #    dem_proj_method, dem_cs, transform_str,
    #    '{} {}'.format(hru.ref_x, hru.ref_y),
    #    dem_orig_sr)
    # arcpy.ClearEnvironment('extent')

    # Check linear unit of raster
    # DEADBEEF - The conversion could probably be dynamic
    dem_obj = arcpy.sa.Raster(dem_path)
    linear_unit_list = ['METER', 'FOOT_US', 'FOOT']
    linear_unit = dem_obj.spatialReference.linearUnitName.upper()
    if linear_unit not in linear_unit_list:
        logging.error(
            '\nERROR: The linear unit of the projected/clipped DEM must' +
            ' be meters or feet\n  {}'.format(linear_unit))
        sys.exit()
    del dem_obj

    # Calculate filled DEM, flow_dir, & flow_acc
    logging.info('\nCalculating filled DEM raster')
    dem_fill_obj = arcpy.sa.Fill(dem_path)
    dem_fill_obj.save(dem_fill_path)
    del dem_fill_obj
    if calc_flow_dir_flag:
        logging.info('Calculating flow direction raster')
        dem_fill_obj = arcpy.sa.Raster(dem_fill_path)
        flow_dir_obj = arcpy.sa.FlowDirection(dem_fill_obj, True)
        flow_dir_obj.save(flow_dir_path)
        del flow_dir_obj, dem_fill_obj
    if calc_flow_acc_flag:
        logging.info('Calculating flow accumulation raster')
        flow_dir_obj = arcpy.sa.Raster(flow_dir_path)
        flow_acc_obj = arcpy.sa.FlowAccumulation(flow_dir_obj)
        flow_acc_obj.save(flow_acc_path)
        del flow_acc_obj, flow_dir_obj
    if calc_flow_acc_dem_flag:
        # flow_acc_dem_obj = dem_fill_obj * flow_acc_obj
        # Low pass filter of flow_acc then take log10
        flow_acc_filter_obj = arcpy.sa.Filter(
            arcpy.sa.Raster(flow_acc_path), 'LOW', 'NODATA')
        flow_acc_filter_obj *= flow_acc_dem_factor
        flow_acc_filter_obj.save(flow_acc_filter_path)
        flow_acc_dem_obj = arcpy.sa.Raster(dem_fill_path) * flow_acc_filter_obj
        flow_acc_dem_obj.save(flow_acc_dem_path)
        del flow_acc_dem_obj, flow_acc_filter_obj

    # Calculate an integer version of DEM for median zonal stats
    dem_integer_obj = arcpy.sa.Int(arcpy.sa.Raster(dem_path) * 100)
    dem_integer_obj.save(dem_integer_path)
    del dem_integer_obj

    # Calculate slope
    logging.info('Calculating slope raster')
    dem_slope_obj = arcpy.sa.Slope(dem_fill_path, 'DEGREE')
    # Setting small slopes to zero
    logging.info('  Setting slopes <= 0.01 to 0')
    dem_slope_obj = arcpy.sa.Con(dem_slope_obj <= 0.01, 0, dem_slope_obj)
    dem_slope_obj.save(dem_slope_path)
    del dem_slope_obj

    # Calculate aspect
    logging.info('Calculating aspect raster')
    dem_aspect_obj = arcpy.sa.Aspect(dem_fill_path)
    # Set small slopes to -1 aspect
    logging.debug('  Setting aspect for slopes <= 0.01 to -1')
    dem_aspect_obj = arcpy.sa.Con(
        arcpy.sa.Raster(dem_slope_path) > 0.01, dem_aspect_obj, -1)
    dem_aspect_obj.save(dem_aspect_path)
    del dem_aspect_obj

    # Reclassify aspect
    logging.debug('  Reclassifying: {}'.format(aspect_remap_path))
    dem_aspect_reclass_obj = arcpy.sa.ReclassByASCIIFile(
        dem_aspect_path, aspect_remap_path)
    dem_aspect_reclass_obj.save(dem_aspect_reclass_path)
    del dem_aspect_reclass_obj

    # Temperature Aspect Adjustment
    logging.info('Calculating temperature aspect adjustment raster')
    temp_adj_obj = arcpy.sa.Float(arcpy.sa.ReclassByASCIIFile(
        dem_aspect_reclass_path, temp_adj_remap_path))
    # Since reclass can't remap to floats directly
    # Values are scaled by 10 and stored as integers
    temp_adj_obj *= 0.1
    # This is a function in the
    # temp_adj_obj = reclass_ascii_float_func(
    #    dem_aspect_reclass_path, temp_adj_remap_path)
    temp_adj_obj.save(temp_adj_path)
    del temp_adj_obj


    # List of rasters, fields, and stats for zonal statistics
    zs_dem_dict = dict()
    zs_dem_dict[hru.dem_mean_field] = [dem_path, 'MEAN']
    if calc_flow_acc_dem_flag:
        zs_dem_dict[hru.dem_sum_field] = [flow_acc_dem_path, 'SUM']
        zs_dem_dict[hru.dem_count_field] = [flow_acc_filter_path, 'SUM']
    # CGM - Zonal stats wasn't working with median
    # zs_dem_dict[hru.dem_median_field] = [dem_integer_path, 'MEDIAN']
    zs_dem_dict[hru.dem_max_field] = [dem_path, 'MAXIMUM']
    zs_dem_dict[hru.dem_min_field] = [dem_path, 'MINIMUM']
    zs_dem_dict[hru.dem_aspect_field] = [dem_aspect_reclass_path, 'MAJORITY']
    zs_dem_dict[hru.dem_slope_deg_field] = [dem_slope_path, 'MEAN']
    zs_dem_dict[hru.tmax_adj_field] = [temp_adj_path, 'MEAN']
    zs_dem_dict[hru.tmin_adj_field] = [temp_adj_path, 'MEAN']


    # Calculate DEM zonal statistics
    logging.info('\nCalculating DEM zonal statistics')
    support.zonal_stats_func(
        zs_dem_dict, hru.polygon_path, hru.point_path, hru)

    # Reset DEM_MEDIAN
    # logging.info('\nCalculating {}'.format(hru.dem_median_field))
    # arcpy.CalculateField_management(
    #    hru.polygon_path, hru.dem_median_field,
    #    # Convert meters to feet
    #    '0.01 * !{}!'.format(hru.dem_median_field), 'PYTHON')

    # Calculate HRU_ELEV (HRU elevation in feet)
    logging.info('\nCalculating initial {} from {}'.format(
        hru.dem_feet_field, hru.dem_adj_field))
    if linear_unit in ['METERS']:
        logging.info('  Converting from meters to feet')
        arcpy.CalculateField_management(
            hru.polygon_path, hru.dem_feet_field,
            '!{}! * 3.28084'.format(hru.dem_adj_field), 'PYTHON')
    elif linear_unit in ['FOOT_US', 'FOOT']:
        arcpy.CalculateField_management(
            hru.polygon_path, hru.dem_feet_field,
            '!{}!'.format(hru.dem_adj_field), 'PYTHON')


    # Flow accumulation weighted elevation
    if calc_flow_acc_dem_flag:
        logging.info('Calculating {}'.format(hru.dem_flowacc_field))
        hru_polygon_layer = 'hru_polygon_layer'
        arcpy.MakeFeatureLayer_management(
            hru.polygon_path, hru_polygon_layer)
        arcpy.SelectLayerByAttribute_management(
            hru_polygon_layer, "NEW_SELECTION",
            '"{}" > 0'.format(hru.dem_count_field))
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_flowacc_field,
            'float(!{}!) / !{}!'.format(
                hru.dem_sum_field, hru.dem_count_field),
            'PYTHON')
        # Clear dem_flowacc for any cells that have zero sum or count
        arcpy.SelectLayerByAttribute_management(
            hru_polygon_layer, "NEW_SELECTION",
            '("{}" = 0) OR ("{}" = 0)'.format(
                hru.dem_count_field, hru.dem_sum_field))
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_flowacc_field, 0, 'PYTHON')
        arcpy.Delete_management(hru_polygon_layer)
        # arcpy.DeleteField_management(hru.polygon_path, hru.dem_sum_field)
        # arcpy.DeleteField_management(hru.polygon_path, hru.dem_count_field)

    # Fill DEM_ADJ if it is not set
    if all([row[0] == 0 for row in arcpy.da.SearchCursor(
            hru.polygon_path, [hru.dem_adj_field])]):
        logging.info('Filling {} from {}'.format(
            hru.dem_adj_field, dem_adj_copy_field))
        arcpy.CalculateField_management(
            hru.polygon_path, hru.dem_adj_field,
            'float(!{}!)'.format(dem_adj_copy_field), 'PYTHON')
    elif reset_dem_adj_flag:
        logging.info('Filling {} from {}'.format(
            hru.dem_adj_field, dem_adj_copy_field))
        arcpy.CalculateField_management(
            hru.polygon_path, hru.dem_adj_field,
            'float(!{}!)'.format(dem_adj_copy_field), 'PYTHON')
    else:
        logging.info(
            ('{} appears to already have been set and ' +
             'will not be overwritten').format(hru.dem_adj_field))

    # HRU_SLOPE in radians
    logging.info('Calculating {} (Slope in Radians)'.format(
        hru.dem_slope_rad_field))
    arcpy.CalculateField_management(
        hru.polygon_path, hru.dem_slope_rad_field,
        'math.pi * !{}! / 180'.format(hru.dem_slope_deg_field), 'PYTHON')
    # HRU_SLOPE in percent
    logging.info('Calculating {} (Percent Slope)'.format(
        hru.dem_slope_pct_field))
    arcpy.CalculateField_management(
        hru.polygon_path, hru.dem_slope_pct_field,
        'math.tan(!{}!)'.format(hru.dem_slope_rad_field), 'PYTHON')

    # HRU_DEPLCRV
    # deplcrv is set to 1 for all active cells when writing parameter file
    # logging.info('Calculating {}'.format(hru.deplcrv_field))
    # arcpy.CalculateField_management(
    #    hru.polygon_path, hru.deplcrv_field, '1', 'PYTHON')

    # Jensen-Haise Potential ET air temperature coefficient
    logging.info('Calculating JH_COEF_HRU')
    # First check if PRISM TMAX/TMIN have been set
    # If max July value is 0, use default values
    if (calc_prism_jh_coef_flag and
        (len(arcpy.ListFields(hru.polygon_path, 'TMAX_07')) == 0 or
         support.field_stat_func(hru.polygon_path, 'TMAX_07', 'MAXIMUM') == 0)):
        calc_prism_jh_coef_flag = False
    # Use PRISM temperature values
    if calc_prism_jh_coef_flag:
        logging.info('  Using PRISM temperature values')
        tmax_field_list = ['!TMAX_{:02d}!'.format(m) for m in range(1, 13)]
        tmin_field_list = ['!TMIN_{:02d}!'.format(m) for m in range(1, 13)]
        tmax_expr = 'max([{}])'.format(','.join(tmax_field_list))
        arcpy.CalculateField_management(
            hru.polygon_path, hru.jh_tmax_field, tmax_expr, 'PYTHON')
        # Get TMIN for same month as maximum TMAX
        tmin_expr = 'max(zip([{}],[{}]))[1]'.format(
            ','.join(tmax_field_list), ','.join(tmin_field_list))
        arcpy.CalculateField_management(
            hru.polygon_path, hru.jh_tmin_field, tmin_expr, 'PYTHON')
    # Use default temperature values
    else:
        logging.info('  Using default temperature values (7 & 25)')
        arcpy.CalculateField_management(
            hru.polygon_path, hru.jh_tmax_field, 25, 'PYTHON')
        arcpy.CalculateField_management(
            hru.polygon_path, hru.jh_tmin_field, 7, 'PYTHON')
    support.jensen_haise_func(
        hru.polygon_path, hru.jh_coef_field, hru.dem_feet_field,
        hru.jh_tmin_field, hru.jh_tmax_field)

    # SNAREA_THRESH
    logging.info('Calculating {}'.format(hru.snarea_thresh_field))
    elev_min = support.field_stat_func(
        hru.polygon_path, hru.dem_feet_field, 'MINIMUM')
    arcpy.CalculateField_management(
        hru.polygon_path, hru.snarea_thresh_field,
        '(!{}! - {}) * 0.005'.format(hru.dem_feet_field, elev_min),
        'PYTHON')

    # Clear slope/aspect values for lake cells (HRU_TYPE == 2)
    # Also clear for ocean cells (HRU_TYPE == 0 and DEM_ADJ == 0)
    if True:
        logging.info('\nClearing slope/aspect parameters for lake cells')
        hru_polygon_layer = "hru_polygon_layer"
        arcpy.MakeFeatureLayer_management(
            hru.polygon_path, hru_polygon_layer)
        arcpy.SelectLayerByAttribute_management(
            hru_polygon_layer, "NEW_SELECTION",
            '"{0}" = 2 OR ("{0}" = 0 AND "{1}" = 0)'.format(
                hru.type_field, hru.dem_adj_field))
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_aspect_field, 0, 'PYTHON')
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_slope_deg_field, 0, 'PYTHON')
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_slope_rad_field, 0, 'PYTHON')
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.dem_slope_pct_field, 0, 'PYTHON')
        # arcpy.CalculateField_management(
        #    hru_polygon_layer, hru.deplcrv_field, 0, 'PYTHON')
        # arcpy.CalculateField_management(
        #    hru_polygon_layer, hru.snarea_field, 0, 'PYTHON')
        # arcpy.CalculateField_management(
        #    hru_polygon_layer, hru.tmax_adj_field, 0, 'PYTHON')
        # arcpy.CalculateField_management(
        #    hru_polygon_layer, hru.tmin_adj_field, 0, 'PYTHON')

        # Should JH coefficients be cleared for lakes?
        # logging.info('\nClearing JH parameters for ocean cells')
        arcpy.SelectLayerByAttribute_management(
            hru_polygon_layer, "NEW_SELECTION",
            '"{}" = 0 AND "{}" = 0'.format(
                hru.type_field, hru.dem_adj_field))
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.jh_coef_field, 0, 'PYTHON')
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.jh_tmax_field, 0, 'PYTHON')
        arcpy.CalculateField_management(
            hru_polygon_layer, hru.jh_tmin_field, 0, 'PYTHON')

        arcpy.Delete_management(hru_polygon_layer)
        del hru_polygon_layer


def arg_parse():
    """"""
    parser = argparse.ArgumentParser(
        description='DEM Parameters',
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

    # Calculate GSFLOW DEM Parameters
    dem_parameters(
        config_path=args.ini, overwrite_flag=args.overwrite,
        debug_flag=args.loglevel==logging.DEBUG)
