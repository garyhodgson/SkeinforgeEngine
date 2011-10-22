"""
Skeins a 3D model into gcode.
"""

from plugins import *
from config import config
from datetime import timedelta
import os, sys, time, re, logging, traceback, argparse

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'


__plugins_path__ = 'skeinforge_application\plugins'
logger = logging.getLogger('engine')

def getCraftedTextFromPlugins(fileName, pluginSequence, text):
	'Get a crafted shape file from a list of pluginSequence.'
	lastProcedureTime = time.time()
	sys.path.insert(0, __plugins_path__)
	for plugin in pluginSequence:
		pluginModule = __import__(plugin)
		if pluginModule != None:
			text = pluginModule.getCraftedText(fileName, text)
			if text == '':
				logger.warning('Procedure %s returned no text', plugin)
				return ''
			logger.info('%s plugin took %s seconds.', plugin.capitalize(), timedelta(seconds=time.time() - lastProcedureTime).total_seconds())
			lastProcedureTime = time.time()
	return text

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
	
	defaultProfile = config.get('general', 'default.profile')
	if defaultProfile != None:
		config.read(defaultProfile)
		
	if args.p != None:
		config.read(args.p)

	inputFilename = args.file
	logLevel = config.get('general', 'log.level')
	logging.basicConfig(level=logLevel, format='%(asctime)s %(levelname)s (%(name)s) %(message)s')
	logging.Handler.handleError = handleError
	
	startTime = time.time()
	gcodeText = ''
	pluginSequence = config.get('general', 'plugin.sequence').split(',')
	profileName = config.get('profile', 'name')
	logger.info("Profile: %s", profileName)
	logger.debug("Plugin Sequence: %s", pluginSequence)
	
	gcodeText = getCraftedTextFromPlugins(inputFilename, pluginSequence[:-1], gcodeText)

	if gcodeText == '':
		logger.warning('No Gcode given to write out in export module.')
		return
	
	export.writeOutput(inputFilename, gcodeText, profileName)
	logger.info('It took %s seconds to export the file.', timedelta(seconds=time.time() - startTime).total_seconds())

def handleError(self, record):
	traceback.print_stack()

if __name__ == "__main__":	
	main()
