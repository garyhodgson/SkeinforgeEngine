#!/usr/bin/python
"""
Skeins a 3D model into gcode.
"""

from config import config
from datetime import timedelta
from fabmetheus_utilities import archive
from gcode import Gcode
from importlib import import_module
import os
import sys
import time
import re
import logging
import traceback
import argparse
from utilities import memory_tracker


__plugins_path__ = 'plugins'
logger = logging.getLogger('engine')

def getCraftedTextFromPlugins(pluginSequence, gcode):
	'Get a crafted shape file from a list of pluginSequence.'
	lastProcedureTime = time.time()
	sys.path.insert(0, __plugins_path__)
	
	for plugin in pluginSequence:
		pluginModule = import_module(plugin)
		if pluginModule != None:
			memory_tracker.tracker.create_snapshot('Before %s action' % plugin)
			pluginModule.performAction(gcode)
			logger.info('%s plugin took %s seconds.', plugin.capitalize(), timedelta(seconds=time.time() - lastProcedureTime).total_seconds())
			lastProcedureTime = time.time()

def main():
	"Starting point for skeinforge engine."
	parser = argparse.ArgumentParser(description='Skeins a 3D model into gcode.')
	parser.add_argument('file', help='the file to skein')
	parser.add_argument('-c', metavar='config', help='configuration for skeinforge engine', default='skeinforge_engine.cfg')
	parser.add_argument('-p', metavar='profile', help='profile for the skeining')
	args = parser.parse_args()
	
	if args.c == None:
		logger.error('Invalid or missing configuration file defined.')
		return
	config.read(args.c)
	
	logLevel = config.get('general', 'log.level')
	logging.basicConfig(level=logLevel, format='%(asctime)s %(levelname)s (%(name)s) %(message)s')
	
	defaultProfile = config.get('general', 'default.profile')
	if defaultProfile != None:
		config.read(defaultProfile)
		
	if args.p != None:
		config.read(args.p)

	inputFilename = args.file
	
	if not os.path.isfile(inputFilename):
		logger.error('File not found: %s', inputFilename)
		return
	
	pluginSequence = config.get('general', 'plugin.sequence').split(',')
	profileName = config.get('profile', 'name')
	logger.info("Profile: %s", profileName)
	logger.debug("Plugin Sequence: %s", pluginSequence)

	gcode = Gcode()
	memory_tracker.tracker.track_object(gcode)
	memory_tracker.tracker.create_snapshot('Start')
	
	gcode.runtimeParameters.profileName = profileName
	gcode.runtimeParameters.inputFilename = inputFilename
	getCraftedTextFromPlugins(pluginSequence[:], gcode)
	
	memory_tracker.tracker.create_snapshot('End')
	gcode.runtimeParameters.endTime = time.time()
	
	logger.info('It took %s seconds to complete.', timedelta(seconds=gcode.runtimeParameters.endTime - gcode.runtimeParameters.startTime).total_seconds())
	
	memory_tracker.tracker.stats.print_summary()
	
def handleError(self, record):
	traceback.print_stack()

if __name__ == "__main__":
	logging.Handler.handleError = handleError
	
	
	main()
