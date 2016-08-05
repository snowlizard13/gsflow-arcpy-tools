#--------------------------------
# Name:         fishnet_generator.py
# Purpose:      GSFLOW fishnet generator
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


def fishnet_func(config_path, overwrite_flag=False, debug_flag=False):
    """GSFLOW Fishnet Generator

    Args:
        config_file (str): Project config file path
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
    log_file_name = 'fishnet_generator_log.txt'
    log_console = logging.FileHandler(
        filename=os.path.join(hru.log_ws, log_file_name), mode='w')
    log_console.setLevel(logging.DEBUG)
    log_console.setFormatter(logging.Formatter('%(message)s'))
    logging.getLogger('').addHandler(log_console)
    logging.info('\nGSFLOW Fishnet Generator')

    # Check input paths
    study_area_path = inputs_cfg.get('INPUTS', 'study_area_path')
    if not arcpy.Exists(study_area_path):
        logging.error(
            '\nERROR: Study area ({}) does not exist'.format(
                study_area_path))
        sys.exit()

    # For now, study area has to be a polygon
    if arcpy.Describe(study_area_path).datasetType != 'FeatureClass':
        logging.error(
            '\nERROR: For now, study area must be a polygon shapefile')
        sys.exit()

    # Build output folder if necessary
    fishnet_temp_ws = os.path.join(hru.param_ws, 'fishnet_temp')
    if not os.path.isdir(fishnet_temp_ws):
        os.mkdir(fishnet_temp_ws)
    # Output paths
    study_area_proj_path = os.path.join(
        fishnet_temp_ws, 'projected_study_area.shp')

    # Set ArcGIS environment variables
    arcpy.CheckOutExtension('Spatial')
    env.overwriteOutput = True
    env.pyramid = 'PYRAMIDS -1'
    # env.pyramid = 'PYRAMIDS 0'
    env.workspace = hru.param_ws
    env.scratchWorkspace = hru.scratch_ws

    # Get spatial reference of study_area
    study_area_desc = arcpy.Describe(study_area_path)
    study_area_sr = study_area_desc.spatialReference
    logging.debug('\n  Study area: {}'.format(study_area_path))
    logging.debug('  Study area spat. ref.:  {}'.format(
        study_area_sr.name))
    logging.debug('  Study area GCS:         {}'.format(
        study_area_sr.GCS.name))

    # Set spatial reference of hru shapefile
    # If the spatial reference can be set to an int,
    #   assume it is an EPSG or ArcGIS WKID
    # If not, try setting the spatial reference directly from
    if support.is_number(hru.sr_name):
        hru.sr = arcpy.SpatialReference(int(hru.sr_name))
    elif os.path.isfile(hru.sr_name) and hru.sr_name.endswith('.prj'):
        hru.sr = arcpy.SpatialReference(hru.sr_name)
    # DEADBEEF - actually check if the file is a raster/feature class
    elif arcpy.Exists(hru.sr_name) and not hru.sr_name.endswith('.prj'):
        hru.sr = arcpy.Describe(hru.sr_name).spatialReference
    else:
        hru.sr = arcpy.SpatialReference(hru.sr_name)
    logging.debug('  HRU spat. ref.: {}'.format(hru.sr.name))
    logging.debug('  HRU GCS:        {}'.format(hru.sr.GCS.name))

    # If study area spat_ref doesn't match hru_param spat_ref
    # Project study are to hru_param and get projected extent
    # Otherwise, read study_area extent directly
    # DEADBEEF - This will fail for NAD83 Zone 11N Meters and Feet
    if hru.sr.name != study_area_sr.name:
        logging.info('\n  Projecting study area...')
        # Set preferred transforms
        transform_str = support.transform_func(hru.sr, study_area_sr)
        logging.debug('    Transform: {}'.format(transform_str))
        # Project study area
        arcpy.Project_management(
            study_area_path, study_area_proj_path, hru.sr,
            transform_str, study_area_sr)
        study_area_extent = arcpy.Describe(study_area_proj_path).extent
        arcpy.Delete_management(study_area_proj_path)
        logging.info('\n  Projected extent:  {}'.format(
            support.extent_string(study_area_extent)))
        del study_area_proj_path, transform_str
    else:
        study_area_extent = arcpy.Describe(study_area_path).extent
        logging.info('\n  Study Area extent: {}'.format(
            support.extent_string(study_area_extent)))

    # Buffer extent
    buffer_extent = support.buffer_extent_func(
        study_area_extent, hru.buffer_cells * hru.cs)
    logging.info('  HRU extent:        {}'.format(
        support.extent_string(buffer_extent)))

    # Adjust study area extent to reference points
    hru.ref_pnt = arcpy.Point(hru.ref_x, hru.ref_y)
    hru.extent = support.adjust_extent_to_snap(
        buffer_extent, hru.ref_pnt, hru.cs, hru.snap_method)
    logging.info('  Snapped Extent:    {}'.format(
        support.extent_string(hru.extent)))

    # Build hru_param
    logging.info('\nBuilding HRU parameter fishnet')
    build_fishnet_func(
        hru.polygon_path, hru.point_path, hru.extent, hru.cs, hru.sr)

    # Write initial parameters to hru_param (X/Y, ROW/COL, Unique ID)
    # set_hru_id_func(hru.polygon_path, hru.extent, hru.cs)


def build_fishnet_func(hru_polygon_path, hru_point_path, extent, cs, sr):
    """"""
    # Remove existing
    if arcpy.Exists(hru_polygon_path):
        arcpy.Delete_management(hru_polygon_path)
    if arcpy.Exists(hru_point_path):
        arcpy.Delete_management(hru_point_path)
    # Calculate LL/UR corner points
    origin_pnt = (extent.XMin, extent.YMin)
    yaxis_pnt = (extent.XMin, extent.YMin + cs)
    corner_pnt = (extent.XMax, extent.YMax)
    origin_str = ' '.join(map(str, origin_pnt))
    yaxis_str = ' '.join(map(str, yaxis_pnt))
    corner_str = ' '.join(map(str, corner_pnt))
    logging.debug('  Origin: {}'.format(origin_str))
    logging.debug('  Y-Axis: {}'.format(yaxis_str))
    logging.debug('  Corner: {}'.format(corner_str))
    # Build fishnet & labels
    arcpy.CreateFishnet_management(
        hru_polygon_path, origin_str, yaxis_str, cs, cs,
        '0', '0', corner_str, 'LABELS', '#', 'POLYGON')
    arcpy.DefineProjection_management(hru_polygon_path, sr)
    arcpy.DefineProjection_management(hru_point_path, sr)


def arg_parse():
    """"""
    parser = argparse.ArgumentParser(
        description='Fishnet Generator',
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

    # Run GSFLOW Fishnet Generator
    fishnet_func(
        config_path=args.ini, overwrite_flag=args.overwrite,
        debug_flag=args.loglevel==logging.DEBUG)
