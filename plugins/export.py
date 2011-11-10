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
from fabmetheus_utilities import archive, euclidean
from utilities import memory_tracker
from gcode_writer import GcodeWriter
from StringIO import StringIO
import datetime
import logging
import os
import string
import time
try:
   import cPickle as pickle
except:
   import pickle
   
logger = logging.getLogger('export')
name = 'export'

def performAction(gcode):
	'Export a gcode linear move text.'
	e = ExportSkein(gcode)
	if gcode.runtimeParameters.profileMemory:
            memory_tracker.track_object(e)
	e.export()
	if gcode.runtimeParameters.profileMemory:
		memory_tracker.create_snapshot("After export")

class ExportSkein:
	'A class to export a skein of extrusions.'
	def __init__(self, gcode):
		self.gcode = gcode		
		self.deleteComments = config.getboolean(name, 'delete.comments')
		self.fileExtension = config.get(name, 'file.extension')
		self.nameOfReplaceFile = config.get(name, 'replace.filename')
		self.exportSlicedModel = config.getboolean(name, 'export.slicedmodel')
		self.addProfileExtension = config.getboolean(name, 'file.extension.profile')
		self.exportPickledSlicedModel = config.getboolean(name, 'export.pickled.slicedmodel')
		self.overwritePickledSlicedModel = config.getboolean(name, 'overwrite.pickled.slicedmodel')
		
	def getReplaceableExportGcode(self, nameOfReplaceFile, replaceableExportGcode):
		'Get text with strings replaced according to replace.csv file.'
		
		fullReplaceFilePath = os.path.join('alterations', nameOfReplaceFile)
		
		if self.nameOfReplaceFile == '' or not os.path.exists(fullReplaceFilePath):
			return replaceableExportGcode
					
		fullReplaceText = archive.getFileText(fullReplaceFilePath)
		replaceLines = archive.getTextLines(fullReplaceText)
		if len(replaceLines) < 1:
			return replaceableExportGcode
		for replaceLine in replaceLines:
			splitLine = replaceLine.replace('\\n', '\t').split('\t')
			if len(splitLine) > 0:
				replaceableExportGcode = replaceableExportGcode.replace(splitLine[0], '\n'.join(splitLine[1 :]))
		output = StringIO()
		
		for line in archive.getTextLines(replaceableExportGcode):
			if line != '':
				output.write(line + '\n')
			
		return output.getvalue()

	def export(self):
		'Perform final modifications to gcode and performs export.'
		
		filename = self.gcode.runtimeParameters.inputFilename
		filenamePrefix = os.path.splitext(filename)[0]
		
		if self.gcode.runtimeParameters.outputFilename != None:
			exportFileName = self.gcode.runtimeParameters.outputFilename
		else :
			exportFileName = filenamePrefix
			profileName = self.gcode.runtimeParameters.profileName
	
			if self.addProfileExtension and profileName:
				exportFileName += '.' + string.replace(profileName, ' ', '_')
				exportFileName += '.' + self.fileExtension
		
		replaceableExportGcode = self.getReplaceableExportGcode(self.nameOfReplaceFile, GcodeWriter(self.gcode).getSlicedModelAsGcode())		
		archive.writeFileText(exportFileName, replaceableExportGcode)
		
		if self.exportSlicedModel:
			fileNamePenultimate = filenamePrefix + '.slicedmodel'
			archive.writeFileText(fileNamePenultimate, str(self.gcode))
			logger.info('Sliced Model gcode exported to: %s', fileNamePenultimate)
		
		if self.exportPickledSlicedModel:
			fileNamePickled = filenamePrefix + '.pickled_slicedmodel'
			if os.path.exists(fileNamePickled) and not self.overwritePickledSlicedModel:
				backupFilename = '%s.%s.bak' % (fileNamePickled, datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
				os.rename(fileNamePickled, backupFilename)
				logger.info('Existing slicedmodel file backed up to: %s', backupFilename)
			logger.info('Pickled slicedmodel exported to: %s', fileNamePickled)
			archive.writeFileText(fileNamePickled, pickle.dumps(self.gcode))
			
		logger.info('Gcode exported to: %s', archive.getSummarizedFileName(exportFileName))
