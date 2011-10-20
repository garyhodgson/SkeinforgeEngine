"""
Craft is a script to access the plugins which craft a gcode file.
"""

from plugins import *
import os
import sys
import time
import re
from config import config
from datetime import timedelta
import logging
import traceback

__author__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__date__ = '$Date: 2008/21/04 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger('engine')

__craft_sequence__ = ['carve', 'bottom', 'preface', 'inset', 'fill', 'multiply', 'speed', 'raft', 'stretch', 'comb', 'cool', 'dimension', 'export']
#__craft_sequence__ = ['carve', 'scale', 'bottom', 'preface', 'inset', 'fill', 'multiply', 'speed', 'temperature', 'clip', 'raft', 'skirt', 'chamber', 'jitter', 'stretch', 'leadin', 'skin', 'comb', 'cool', 'wipe', 'lash', 'limit', 'dimension', 'olddimension', 'export']
#__craft_sequence__ = ['carve', 'bottom', 'preface', 'export']

def getCraftedTextFromProcedures(fileName, procedures, text):
	'Get a crafted shape file from a list of procedures.'
	lastProcedureTime = time.time()
	for procedure in procedures:
		craftModule = __import__(procedure)
		if craftModule != None:
			text = craftModule.getCraftedText(fileName, text)
			if text == '':
				logger.warning('Procedure %s returned no text', procedure)
				return ''
			logger.info('%s procedure took %s seconds.', procedure.capitalize(), timedelta(seconds=time.time() - lastProcedureTime).total_seconds())
			lastProcedureTime = time.time()
	return text

def main():
	"Starting point for skeinforge engine."
	startTime = time.time()
	fileName = ' '.join(sys.argv[1 :])
	if fileName == '':
		logger.warning('No Filename given to write out in export module.')
		return
	gcodeText = ''
	procedures = __craft_sequence__
	logger.debug("procedures: %s", procedures)	
	gcodeText = getCraftedTextFromProcedures(fileName, procedures[: -1], gcodeText)

	if gcodeText == '':
		logger.warning('No Gcode given to write out in export module.')
		return
	
	export.writeOutput(fileName, gcodeText, 'Default', False)
	logger.info('It took %s seconds to export the file.', timedelta(seconds=time.time()-startTime).total_seconds())

def handleError(self, record):
	traceback.print_stack()

if __name__ == "__main__":
	logLevel = config.get('general', 'log.level')
	logging.basicConfig(level=logLevel, format='%(asctime)s %(levelname)s (%(name)s) %(message)s')
	logging.Handler.handleError = handleError

	sys.path.insert(0, 'skeinforge_application\plugins')
	main()

