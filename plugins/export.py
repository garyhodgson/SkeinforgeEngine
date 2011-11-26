"""
Exports the slicedModel to a file.

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
from writers.gcode_writer import GcodeWriter
from StringIO import StringIO
import datetime
import logging
import os
import string
import time
import sys
try: 
	import cPickle as pickle
except:
	import pickle
	
name = 'export'
logger = logging.getLogger(name)

def performAction(slicedModel):
	'Export a slicedModel linear move text.'
	e = ExportSkein(slicedModel)
	if slicedModel.runtimeParameters.profileMemory:
            memory_tracker.track_object(e)
	e.export()
	if slicedModel.runtimeParameters.profileMemory:
		memory_tracker.create_snapshot("After export")

class ExportSkein:
	'A class to export a skein of extrusions.'
	def __init__(self, slicedModel):
		self.slicedModel = slicedModel
		self.debug = config.getboolean(name, 'debug')
		self.deleteComments = config.getboolean(name, 'delete.comments')
		self.fileExtension = config.get(name, 'file.extension')
		self.nameOfReplaceFile = config.get(name, 'replace.filename')
		self.exportSlicedModel = config.getboolean(name, 'export.slicedmodel')
		self.exportSlicedModelExtension = config.get(name, 'export.slicedmodel.extension')
		self.addProfileExtension = config.getboolean(name, 'file.extension.profile')
		self.overwriteExportedSlicedModel = config.getboolean(name, 'overwrite.exported.slicedmodel')
		
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
		'Perform final modifications to slicedModel and performs export.'
		
		filename = self.slicedModel.runtimeParameters.inputFilename
		filenamePrefix = os.path.splitext(filename)[0]
		profileName = self.slicedModel.runtimeParameters.profileName
		
		if self.slicedModel.runtimeParameters.outputFilename != None:
			exportFileName = self.slicedModel.runtimeParameters.outputFilename
		else :
			exportFileName = filenamePrefix
			if self.addProfileExtension and profileName:
				exportFileName += '.' + string.replace(profileName, ' ', '_')
			exportFileName += '.' + self.fileExtension
			self.slicedModel.runtimeParameters.outputFilename = exportFileName
		
		replaceableExportGcode = self.getReplaceableExportGcode(self.nameOfReplaceFile, GcodeWriter(self.slicedModel).getSlicedModel())		
		archive.writeFileText(exportFileName, replaceableExportGcode)
		logger.info('Gcode exported to: %s', os.path.basename(exportFileName))
		
		if self.debug:
			slicedModelTextFilename = filenamePrefix
			if self.addProfileExtension and profileName:
				slicedModelTextFilename += '.' + string.replace(profileName, ' ', '_')
			slicedModelTextFilename += '.slicedmodel.txt'
			archive.writeFileText(slicedModelTextFilename, str(self.slicedModel))
			logger.info('Sliced Model Text exported to: %s', slicedModelTextFilename)
		
		if self.exportSlicedModel:
			slicedModelExportFilename = filenamePrefix
			if self.addProfileExtension and profileName:
				slicedModelExportFilename += '.' + string.replace(profileName, ' ', '_')
			slicedModelExportFilename += '.' + self.exportSlicedModelExtension
			if os.path.exists(slicedModelExportFilename) and not self.overwriteExportedSlicedModel:
				backupFilename = '%s.%s.bak' % (slicedModelExportFilename, datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
				os.rename(slicedModelExportFilename, backupFilename)
				logger.info('Existing slicedmodel file backed up to: %s', backupFilename)
			logger.info('Sliced Model exported to: %s', slicedModelExportFilename)
			archive.writeFileText(slicedModelExportFilename, pickle.dumps(self.slicedModel))
		