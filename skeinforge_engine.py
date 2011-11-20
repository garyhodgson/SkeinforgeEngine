#!/usr/bin/python
"""
Skeins a 3D model into gcode.
"""

from config import config
from datetime import timedelta
from entities import SlicedModel
from fabmetheus_utilities import archive
from importlib import import_module
from utilities import memory_tracker
import argparse
import logging
import os
import re
import sys
import time
import traceback
import StringIO
try:
   import cPickle as pickle
except:
   import pickle

__plugins_path__ = 'plugins'
logger = logging.getLogger('engine')

def getCraftedTextFromPlugins(pluginSequence, gcode):
	'Get a crafted shape file from a list of pluginSequence.'
	lastProcedureTime = time.time()
	if __plugins_path__ not in sys.path:
		sys.path.insert(0, __plugins_path__)	
	for plugin in pluginSequence:
		pluginModule = import_module(plugin)
		if pluginModule != None:
			if gcode.runtimeParameters.profileMemory:
				memory_tracker.create_snapshot('Before %s action' % plugin)
			pluginModule.performAction(gcode)
			logger.info('%s plugin took %s seconds.', plugin.capitalize(), timedelta(seconds=time.time() - lastProcedureTime).total_seconds())
			lastProcedureTime = time.time()

def main(argv=None):
    "Starting point for skeinforge engine."
    parser = argparse.ArgumentParser(description='Skeins a 3D model into slicedModel.')
    parser.add_argument('file', help='The file to skein. Files accepted: stl, obj, gts, and svg or pickledgcode files produced by Skeinforge.')
    parser.add_argument('-c', metavar='config', help='Configuration for skeinforge engine.', default='skeinforge_engine.cfg')
    parser.add_argument('-p', metavar='profile', help='Profile for the skeining.')
    parser.add_argument('-o', metavar='output', help='Output filename. Overrides other export filename settings.')
    parser.add_argument('-r', metavar='reprocess', help='Comma seperated list of plugins to reprocess a pickled slicedModel file. The export plugin is automatically appended.')

    
    if argv is None: 
    	argv = sys.argv[1:]
    args = parser.parse_args(argv)
    
    if args.c == None:
    	logger.error('Invalid or missing configuration file.')
    	return
    config.read(args.c)
    
    logLevel = config.get('general', 'log.level')
    logging.basicConfig(level=logLevel, format='%(asctime)s %(levelname)s (%(name)s) %(message)s')
    	
    defaultProfile = config.get('general', 'default.profile')
    if defaultProfile != None:
    	config.read(defaultProfile)
    profileName = config.get('profile', 'name')
    
    if args.p != None:
    	config.read(args.p)
        if profileName == 'default':
            profileName = os.path.basename(args.p)
    
    logger.info("Profile: %s", profileName)
        
    inputFilename = args.file
    
    if not os.path.isfile(inputFilename):
    	logger.error('File not found: %s', inputFilename)
    	return
 
    logger.info("Processing file: %s", os.path.basename(inputFilename))
    
    if inputFilename.endswith('.pickled_slicedmodel'):
    	pickledSlicedModel = archive.getFileText(inputFilename)
    	slicedModel = pickle.loads(pickledSlicedModel)
    	slicedModel.runtimeParameters.startTime = time.time()
    	slicedModel.runtimeParameters.endTime = None
    else:
    	slicedModel = SlicedModel()
    
    if args.o != None:
        slicedModel.runtimeParameters.outputFilename = args.o
    
    if args.r != None:
    	pluginSequence = args.r.split(',')
    	if 'carve' in pluginSequence:
    		logger.error('Reprocessing a pickled sliced model file with carve is not possible. Please process the original file instead.')
    		return
    	if 'export' not in pluginSequence:
    		pluginSequence.append('export')
    else:
    	pluginSequence = config.get('general', 'plugin.sequence').split(',')
    	
    logger.debug("Plugin Sequence: %s", pluginSequence)
    
    if slicedModel.runtimeParameters.profileMemory:
    	memory_tracker.track_object(slicedModel)
    	memory_tracker.create_snapshot('Start')
    
    slicedModel.runtimeParameters.profileName = profileName
    slicedModel.runtimeParameters.inputFilename = inputFilename
    
    getCraftedTextFromPlugins(pluginSequence[:], slicedModel)
    
    slicedModel.runtimeParameters.endTime = time.time()
    
    logger.info('It took %s seconds to complete.', timedelta(seconds=slicedModel.runtimeParameters.endTime - slicedModel.runtimeParameters.startTime).total_seconds())
    
    if slicedModel.runtimeParameters.profileMemory:
    	memory_tracker.create_snapshot('End')
    	if config.getboolean('general', 'profile.memory.print.summary'):
    		memory_tracker.tracker.stats.print_summary()
    	if config.getboolean('general', 'profile.memory.export.data'):
    		memory_tracker.tracker.stats.dump_stats('%s.memory_tracker.dat' % inputFilename)
    	if config.getboolean('general', 'profile.memory.export.html'):
    		from pympler.classtracker_stats import HtmlStats
    		HtmlStats(tracker=memory_tracker.tracker).create_html('%s.memory_tracker.html' % inputFilename)
            
    return slicedModel

def handleError(self, record):
	traceback.print_stack()

if __name__ == "__main__":
	logging.Handler.handleError = handleError	
	main()
