"""
Multiply is a script to multiply the shape into an array of copies arranged in a table.
"""

from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText(fileName, text):
	'Multiply the fill file or text.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return MultiplySkein().getCraftedGcode(text)

class MultiplySkein:
	'A class to multiply a skein of extrusions.'
	def __init__(self):
		self.gcode = gcodec.Gcode()
		self.isExtrusionActive = False
		self.layerIndex = 0
		self.layerLines = []
		self.lineIndex = 0
		self.lines = None
		self.oldLocation = None
		self.rowIndex = 0
		self.shouldAccumulate = True

		self.activateMultiply = config.getboolean(name, 'active')
		self.centerX = config.getfloat(name, 'center.x')
		self.centerY = config.getfloat(name, 'center.y')
		self.numberOfColumns = config.getint(name, 'columns')
		self.numberOfRows = config.getint(name, 'rows')
		self.reverseSequenceEveryOddLayer = config.getboolean(name, 'sequence.reverse.odd.layers')
		self.separationOverPerimeterWidth = config.getfloat(name, 'separation.over.perimeter.width')
		

	def addElement(self, offset):
		'Add moved element to the output.'
		for line in self.layerLines:
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				movedLocation = self.getMovedLocationSetOldLocation(offset, splitLine)
				line = self.gcode.getLinearGcodeMovement(movedLocation.dropAxis(), movedLocation.z)
			elif firstWord == '(<boundaryPoint>':
				movedLocation = self.getMovedLocationSetOldLocation(offset, splitLine)
				line = self.gcode.getBoundaryLine(movedLocation)
			self.gcode.addLine(line)

	def addLayer(self):
		'Add multiplied layer to the output.'
		self.addRemoveThroughLayer()
		offset = self.centerOffset - self.arrayCenter - self.shapeCenter
		for rowIndex in xrange(self.numberOfRows):
			yRowOffset = float(rowIndex) * self.extentPlusSeparation.imag
			if self.layerIndex % 2 == 1 and self.reverseSequenceEveryOddLayer:
				yRowOffset = self.arrayExtent.imag - yRowOffset
			for columnIndex in xrange(self.numberOfColumns):
				xColumnOffset = float(columnIndex) * self.extentPlusSeparation.real
				if self.rowIndex % 2 == 1:
					xColumnOffset = self.arrayExtent.real - xColumnOffset
				elementOffset = complex(offset.real + xColumnOffset, offset.imag + yRowOffset)
				self.addElement(elementOffset)
			self.rowIndex += 1
		if len(self.layerLines) > 1:
			self.layerIndex += 1
		self.layerLines = []

	def addRemoveThroughLayer(self):
		'Parse gcode initialization and store the parameters.'
		for layerLineIndex in xrange(len(self.layerLines)):
			line = self.layerLines[layerLineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.addLine(line)
			if firstWord == '(<layer>':
				self.layerLines = self.layerLines[layerLineIndex + 1 :]
				return

	def getCraftedGcode(self, gcodeText):
		'Parse gcode text and store the multiply gcode.'
		self.centerOffset = complex(self.centerX, self.centerY)
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		self.setCorners()
		for line in self.lines[self.lineIndex :]:
			self.parseLine(line)
		return self.gcode.output.getvalue()

	def getMovedLocationSetOldLocation(self, offset, splitLine):
		'Get the moved location and set the old location.'
		location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		self.oldLocation = location
		return Vector3(location.x + offset.real, location.y + offset.imag, location.z)

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> multiply </procedureName>)')
				self.gcode.addLine(line)
				self.lineIndex += 1
				return
			elif firstWord == '(<perimeterWidth>':
				self.absolutePerimeterWidth = abs(float(splitLine[1]))
			self.gcode.addLine(line)

	def parseLine(self, line):
		'Parse a gcode line and add it to the multiply skein.'
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == '(</layer>)':
			self.addLayer()
			self.gcode.addLine(line)
			return
		elif firstWord == '(</crafting>)':
			self.shouldAccumulate = False
		if self.shouldAccumulate:
			self.layerLines.append(line)
			return
		self.gcode.addLine(line)

	def setCorners(self):
		'Set maximum and minimum corners and z.'
		cornerMaximumComplex = complex(-987654321.0, -987654321.0)
		cornerMinimumComplex = -cornerMaximumComplex
		for line in self.lines[self.lineIndex :]:
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
				if self.isExtrusionActive:
					locationComplex = location.dropAxis()
					cornerMaximumComplex = euclidean.getMaximum(locationComplex, cornerMaximumComplex)
					cornerMinimumComplex = euclidean.getMinimum(locationComplex, cornerMinimumComplex)
				self.oldLocation = location
			elif firstWord == 'M101':
				self.isExtrusionActive = True
			elif firstWord == 'M103':
				self.isExtrusionActive = False
		self.extent = cornerMaximumComplex - cornerMinimumComplex
		self.shapeCenter = 0.5 * (cornerMaximumComplex + cornerMinimumComplex)
		self.separation = self.separationOverPerimeterWidth * self.absolutePerimeterWidth
		self.extentPlusSeparation = self.extent + complex(self.separation, self.separation)
		columnsMinusOne = self.numberOfColumns - 1
		rowsMinusOne = self.numberOfRows - 1
		self.arrayExtent = complex(self.extentPlusSeparation.real * columnsMinusOne, self.extentPlusSeparation.imag * rowsMinusOne)
		self.arrayCenter = 0.5 * self.arrayExtent
