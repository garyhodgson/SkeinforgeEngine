"""
Export prints the output to a file.

Original author 
	'Enrique Perez (perez_enrique@yahoo.com) 
	modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
	
license 
	'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

"""

from config import config
from datetime import timedelta
from fabmetheus_utilities import archive, euclidean, gcodec
import StringIO
import logging
import os
import string
import time

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger('export')
name = 'export'

def writeOutput(fileName, gcodeText, gcode):
	'Export a gcode linear move file.'
	
	exportFileName = fileName[: fileName.rfind('.')]
	profileName = gcode.runtimeParameters.profileName

	if config.getboolean(name, 'file.extension.profile') and profileName:
			exportFileName += '.' + string.replace(profileName, ' ', '_')
	exportFileName += '.' + config.get(name, 'file.extension')
	
	if config.getboolean(name, 'gcode.penultimate.save'):
		fileNamePenultimate = fileName[: fileName.rfind('.')] + '.penultimate.gcode'
		archive.writeFileText(fileNamePenultimate, gcodeText)
		logger.info('The penultimate file is saved as %s', fileNamePenultimate)
		
	exportGcode = getCraftedText(gcodeText)

	if config.has_option(name, 'replace.filename') and config.get(name, 'replace.filename') != '':
		replaceableExportGcode = getReplaceableExportGcode(config.get(name, 'replace.filename'), exportGcode)
		archive.writeFileText(exportFileName, replaceableExportGcode)
	else:
		archive.writeFileText(exportFileName, exportGcode)
	
	if config.getboolean('export', 'debug'):
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.new.penultimate.gcode', str(gcode))
		replaceableExportGcode = getReplaceableExportGcode(config.get(name, 'replace.filename'), gcode.getGcodeText())
		archive.writeFileText(fileName[: fileName.rfind('.')] + '.new.gcode', replaceableExportGcode)
		
	logger.info('The exported file is saved as %s', archive.getSummarizedFileName(exportFileName))

def getCraftedText(text):
	'Export a gcode linear move text.'
	return ExportSkein().getCraftedGcode(text)

def getReplaceableExportGcode(nameOfReplaceFile, replaceableExportGcode):
	'Get text with strings replaced according to replace.csv file.'
	fullReplaceFilePath = os.path.join('alterations', nameOfReplaceFile)
	fullReplaceText = archive.getFileText(fullReplaceFilePath)
	replaceLines = archive.getTextLines(fullReplaceText)
	if len(replaceLines) < 1:
		return replaceableExportGcode
	for replaceLine in replaceLines:
		splitLine = replaceLine.replace('\\n', '\t').split('\t')
		if len(splitLine) > 0:
			replaceableExportGcode = replaceableExportGcode.replace(splitLine[0], '\n'.join(splitLine[1 :]))
	output = StringIO.StringIO()
	gcodec.addLinesToCString(output, archive.getTextLines(replaceableExportGcode))
	return output.getvalue()
	
class ExportSkein:
	'A class to export a skein of extrusions.'
	def __init__(self):
		self.crafting = False
		self.decimalPlacesExported = 2
		self.output = StringIO.StringIO()		
		self.deleteComments = config.getboolean(name, 'delete.comments')
		self.fileExtension = config.get(name, 'file.extension')
		self.nameOfReplaceFile = config.get(name, 'replace.filename')
		self.savePenultimateGcode = config.getboolean(name, 'gcode.penultimate.save')
		self.addProfileExtension = config.getboolean(name, 'file.extension.profile')
		

	def addLine(self, line):
		'Add a line of text and a newline to the output.'
		if line != '':
			self.output.write(line + '\n')

	def getCraftedGcode(self, gcodeText):
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
		roundedNumberString = euclidean.getRoundedToPlacesString(self.decimalPlacesExported, float(numberString))
		return gcodec.getLineWithValueString(character, line, splitLine, roundedNumberString)

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
		if self.deleteComments:
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
