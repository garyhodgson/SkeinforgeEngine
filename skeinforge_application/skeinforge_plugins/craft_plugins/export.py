"""
This page is in the table of contents.
Export is a script to pick an export plugin and optionally print the output to a file.
"""

from fabmetheus_utilities import archive
from fabmetheus_utilities import gcodec
from skeinforge_application.skeinforge_utilities import skeinforge_analyze
from skeinforge_application.skeinforge_utilities import skeinforge_craft
from skeinforge_application.skeinforge_utilities import skeinforge_profile
import cStringIO
import os
import time
import string
from datetime import timedelta
from config import config
import logging

__author__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__credits__ = 'Gary Hodgson <http://garyhodgson.com/reprap/2011/06/hacking-skeinforge-export-module/>'
__date__ = '$Date: 2008/21/04 $'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedTextFromText(gcodeText):
	'Export a gcode linear move text.'
	if gcodec.isProcedureDoneOrFileIsEmpty( gcodeText, name):
		return gcodeText
	if not config.getboolean(name, 'active'):
		return gcodeText
	return ExportSkein().getCraftedGcode(gcodeText)

def getReplaceableExportGcode(nameOfReplaceFile, replaceableExportGcode):
	'Get text with strings replaced according to replace.csv file.'
	fullReplaceFilePath = os.path.join( archive.getSkeinforgePath('alterations'),  nameOfReplaceFile)
	fullReplaceText = archive.getFileText(fullReplaceFilePath)
	replaceLines = archive.getTextLines(fullReplaceText)
	if len(replaceLines) < 1:
		return replaceableExportGcode
	for replaceLine in replaceLines:
		splitLine = replaceLine.replace('\\n', '\t').split('\t')
		if len(splitLine) > 0:
			replaceableExportGcode = replaceableExportGcode.replace(splitLine[0], '\n'.join(splitLine[1 :]))
	output = cStringIO.StringIO()
	gcodec.addLinesToCString(output, archive.getTextLines(replaceableExportGcode))
	return output.getvalue()

def getSelectedPluginModule( plugins ):
	'Get the selected plugin module.'
	logger.debug("plugins: %s",plugins)
	for plugin in plugins:
		if plugin:
			exportPluginsFolderPath = archive.getAbsoluteFrozenFolderPath(__file__, 'export_plugins')
			exportStaticDirectoryPath = os.path.join(exportPluginsFolderPath, 'static_plugins')
			return archive.getModuleWithDirectoryPath( exportStaticDirectoryPath, plugin )
	return None

def writeOutput(fileName, shouldAnalyze=True):
	'Export a gcode linear move file.'
	if fileName == '':
		return None
	
	startTime = time.time()
	logger.info('File %s is being chain exported.', fileName)
	fileNameSuffix = fileName[: fileName.rfind('.')]
	gcodeText = gcodec.getGcodeFileText(fileName, '')
	
	if config.getboolean(name, 'file.extension.profile'):
		profileName = skeinforge_profile.getProfileName(skeinforge_profile.getCraftTypeName())
		if profileName:
			fileNameSuffix += '.' + string.replace(profileName, ' ', '_')
	fileNameSuffix += '.' + config.get(name,'file.extension')
	procedures = skeinforge_craft.getProcedures(name, gcodeText)
	
	logger.debug("procedures: %s", procedures)
	
	gcodeText = skeinforge_craft.getChainTextFromProcedures(fileName, procedures[: -1], gcodeText)
	
	if gcodeText == '':
		return None
	fileNamePenultimate = fileName[: fileName.rfind('.')] + '_penultimate.gcode'
	filePenultimateWritten = False
	if config.getboolean(name, 'gcode.penultimate.save'):
		archive.writeFileText(fileNamePenultimate, gcodeText)
		filePenultimateWritten = True
		print('The penultimate file is saved as ' + archive.getSummarizedFileName(fileNamePenultimate))
	exportGcode = getCraftedTextFromText(gcodeText)
	window = None
	if shouldAnalyze:
		window = skeinforge_analyze.writeOutput(fileName, fileNamePenultimate, fileNameSuffix,
			filePenultimateWritten, gcodeText)
	replaceableExportGcode = None
	selectedPluginModule = getSelectedPluginModule(config.get(name,'plugins').split(','))
	
	if selectedPluginModule == None:
		replaceableExportGcode = exportGcode
	else:
		if selectedPluginModule.globalIsReplaceable:
			replaceableExportGcode = selectedPluginModule.getOutput(exportGcode)
		else:
			selectedPluginModule.writeOutput(fileNameSuffix, exportGcode)
	
	if replaceableExportGcode != None:
		replaceableExportGcode = getReplaceableExportGcode(config.get(name,'replace.filename'), replaceableExportGcode)
		archive.writeFileText( fileNameSuffix, replaceableExportGcode )
		logger.info('The exported file is saved as %s', archive.getSummarizedFileName(fileNameSuffix))
	
	logger.info('It took %s seconds to export the file.', timedelta(seconds=time.time()-startTime).total_seconds())
	return window

class ExportSkein:
	'A class to export a skein of extrusions.'
	def __init__(self):
		self.crafting = False
		self.decimalPlacesExported = 2
		self.output = cStringIO.StringIO()

	def addLine(self, line):
		'Add a line of text and a newline to the output.'
		if line != '':
			self.output.write(line + '\n')

	def getCraftedGcode( self, gcodeText ):
		'Parse gcode text and store the export gcode.'
		lines = archive.getTextLines(gcodeText)
		for line in lines:
			self.parseLine(line)
		return self.output.getvalue()

	def getLineWithTruncatedNumber(self, character, line, splitLine):
		'Get a line with the number after the character truncated.'
		numberString = gcodec.getStringFromCharacterSplitLine(character, splitLine)
		if numberString == None:
			return line
		return gcodec.getLineWithValueString(character, line, splitLine, str(round(float(numberString), self.decimalPlacesExported)))

	def parseLine(self, line):
		'Parse a gcode line.'
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == '(</crafting>)':
			self.crafting = False
		elif firstWord == '(<decimalPlacesCarried>':
			self.decimalPlacesExported = int(splitLine[1]) - 1
		if config.getboolean(name, 'comments.delete.all') or (config.getboolean(name, 'comments.delete.crafting') and self.crafting):
			if firstWord[0] == '(':
				return
			else:
				line = line.split(';')[0].split('(')[0].strip()
		if firstWord == '(<crafting>)':
			self.crafting = True
		if firstWord == '(</extruderInitialization>)':
			self.addLine('(<procedureName> export </procedureName>)')
		if firstWord != 'G1' and firstWord != 'G2' and firstWord != 'G3' :
			self.addLine(line)
			return
		line = self.getLineWithTruncatedNumber('X', line, splitLine)
		line = self.getLineWithTruncatedNumber('Y', line, splitLine)
		line = self.getLineWithTruncatedNumber('Z', line, splitLine)
		line = self.getLineWithTruncatedNumber('I', line, splitLine)
		line = self.getLineWithTruncatedNumber('J', line, splitLine)
		line = self.getLineWithTruncatedNumber('R', line, splitLine)
		self.addLine(line)
