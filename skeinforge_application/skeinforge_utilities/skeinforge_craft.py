"""
Craft is a script to access the plugins which craft a gcode file.

The plugin buttons which are commonly used are bolded and the ones which are rarely used have normal font weight.

"""

from __future__ import absolute_import
#Init has to be imported first because it has code to workaround the python bug where relative imports don't work if the module is imported as a main module.
import __init__

from fabmetheus_utilities.fabmetheus_tools import fabmetheus_interpret
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from fabmetheus_utilities import settings
from skeinforge_application.skeinforge_utilities import skeinforge_analyze
import os
import sys
import time
import re
from config import config
import logging
import traceback


__author__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__date__ = '$Date: 2008/21/04 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)

__craft_sequence__ = ['carve', 'bottom', 'preface', 'inset', 'fill', 'multiply', 'speed', 'raft', 'dimension', 'export']
#__craft_sequence__ = ['carve', 'scale', 'bottom', 'preface', 'inset', 'fill', 'multiply', 'speed', 'temperature', 'clip', 'raft', 'skirt', 'chamber', 'jitter', 'stretch', 'leadin', 'skin', 'comb', 'cool', 'wipe', 'lash', 'limit', 'dimension', 'olddimension', 'export']
#__craft_sequence__ = ['carve', 'bottom', 'preface', 'export']


def getChainText( fileName, procedure ):
	"Get a crafted shape file."
	logger.debug("filename: %s, procedure: %s", filename, procedure)
	text=''
	if fileName.endswith('.gcode') or fileName.endswith('.svg'):
		text = archive.getFileText(fileName)
	procedures = getProcedures( procedure, text )
	return getChainTextFromProcedures( fileName, procedures, text )

def getChainTextFromProcedures(fileName, procedures, text):
	'Get a crafted shape file from a list of procedures.'
	lastProcedureTime = time.time()
	for procedure in procedures:
		craftModule = getCraftModule(procedure)
		if craftModule != None:
			text = craftModule.getCraftedText(fileName, text)
			if text == '':
				print('Warning, the text was not recognized in getChainTextFromProcedures in skeinforge_craft for')
				print(fileName)
				return ''
			if gcodec.isProcedureDone( text, procedure ):
				print('%s procedure took %s.' % (procedure.capitalize(), euclidean.getDurationString(time.time() - lastProcedureTime)))
				lastProcedureTime = time.time()
	return text

def getCraftModule(fileName):
	"Get craft module."
	return archive.getModuleWithDirectoryPath(getPluginsDirectoryPath(), fileName)

def getPluginsDirectoryPath():
	"Get the plugins directory path."
	return archive.getSkeinforgePluginsPath('craft_plugins')

def writeChainTextWithNounMessage(fileName, procedure, shouldAnalyze=True):
	'Get and write a crafted shape file.'
	logger.info('')
	logger.info('The %s tool is parsing the file: %s', procedure, os.path.basename(fileName))
	logger.info('')
	startTime = time.time()
	fileNameSuffix = fileName[: fileName.rfind('.')] + '_' + procedure + '.gcode'
	craftText = getChainText(fileName, procedure)
	if craftText == '':
		logger.warning('There was no text output in writeChainTextWithNounMessage in skeinforge_craft for: %s', fileName)
		return
	archive.writeFileText(fileNameSuffix, craftText)
	window = None
	if shouldAnalyze:
		window = skeinforge_analyze.writeOutput(fileName, fileNameSuffix, fileNameSuffix, True, craftText)
	logger.info('')
	logger.info('The %s tool has created the file: %s', procedure, fileNameSuffix)
	logger.info('')
	logger.info('It took %s to craft the file.', euclidean.getDurationString(time.time() - startTime))
	return window


def getProcedures( procedure, text ):
	"Get the procedures up to and including the given procedure."
	sequenceIndexPlusOneFromText = getSequenceIndexPlusOneFromText(text)
	procedureIndex = __craft_sequence__.index(procedure) if procedure in __craft_sequence__ else 0
	return __craft_sequence__[ sequenceIndexPlusOneFromText : procedureIndex + 1 ] 

def getSequenceIndexPlusOneFromText(fileText):
	"Get the profile sequence index of the file plus one.  Return zero if the procedure is not in the file"

  	completedProcedures = ''
  	for line in fileText:
  		m = re.search('procedureName=\'([^\']+)\'', line)
  		if m != None:
  			completedProcedures = m.group(1)
  			
  	if completedProcedures == None:
  		return 0

	for craftSequenceIndex in xrange( len( __craft_sequence__ ) - 1, - 1, - 1 ):
		procedure = __craft_sequence__[ craftSequenceIndex ]
		if re.match(procedure, completedProcedures):
			return craftSequenceIndex + 1
	return 0
    
def main():
	"Write craft output."	
	pluginsPath = archive.getSkeinforgePluginsPath('craft_plugins')
	exportModule = archive.getModuleWithDirectoryPath(pluginsPath, 'export')
	if exportModule != None:
		return exportModule.writeOutput(' '.join(sys.argv[1 :]), False)

def handleError(self, record):
	traceback.print_stack()

if __name__ == "__main__":
	logLevel = config.get('general', 'log.level')
	logging.basicConfig(level=logLevel, format='%(asctime)s %(levelname)s (%(name)s) %(message)s')
	logging.Handler.handleError = handleError

	logger.info('started')
	main()
	logger.info('ended')

