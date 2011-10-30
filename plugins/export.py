"""
Exports the gcode to a file.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from config import config
from datetime import timedelta
from fabmetheus_utilities import archive, euclidean, gcodec
import StringIO
import logging
import os
import string
import time

logger = logging.getLogger('export')
name = 'export'

def performAction(gcode):
	'Export a gcode linear move text.'
	ExportSkein(gcode).export()

class ExportSkein:
	'A class to export a skein of extrusions.'
	def __init__(self, gcode):
		self.gcode = gcode		
		self.deleteComments = config.getboolean(name, 'delete.comments')
		self.fileExtension = config.get(name, 'file.extension')
		self.nameOfReplaceFile = config.get(name, 'replace.filename')
		self.savePenultimateGcode = config.getboolean(name, 'gcode.penultimate.save')
		self.addProfileExtension = config.getboolean(name, 'file.extension.profile')
		
	def getReplaceableExportGcode(self, nameOfReplaceFile, replaceableExportGcode):
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
		
		for line in archive.getTextLines(replaceableExportGcode):
			if line != '':
				output.write(line + '\n')
			
		return output.getvalue()

	def export(self):
		'Perform final modifications to final gcode and export.'
		
		filename = self.gcode.runtimeParameters.inputFilename
		exportFileName = filename[: filename.rfind('.')]
		profileName = self.gcode.runtimeParameters.profileName
	
		if config.getboolean(name, 'file.extension.profile') and profileName:
				exportFileName += '.' + string.replace(profileName, ' ', '_')
		exportFileName += '.' + config.get(name, 'file.extension')
		
		if self.savePenultimateGcode:
			fileNamePenultimate = filename[: filename.rfind('.')] + '.penultimate.gcode'
			archive.writeFileText(fileNamePenultimate, str(self.gcode))
			logger.info('Penultimate gcode exported to: %s', fileNamePenultimate)

		replaceableExportGcode = self.getReplaceableExportGcode(self.nameOfReplaceFile, self.gcode.getGcodeText())
		archive.writeFileText(exportFileName, replaceableExportGcode)
			
		logger.info('Gcode exported to: %s', archive.getSummarizedFileName(exportFileName))
