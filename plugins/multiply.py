"""
Multiplies the 3D model into an array of copies arranged in a table.

Credits:
	Original Author: Enrique Perez (http://skeinforge.com)
	Contributors: Please see the documentation in Skeinforge 
	Modifed as SFACT: Ahmet Cem Turan (github.com/ahmetcemturan/SFACT)	

License: 
	GNU Affero General Public License http://www.gnu.org/licenses/agpl.html
"""

from fabmetheus_utilities.vector3 import Vector3
from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from config import config
import logging
import copy

logger = logging.getLogger(__name__)
name = 'multiply'

def performAction(gcode):
	'Multiply the 3D model.'
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is inactive", name.capitalize())
		return
	return MultiplySkein(gcode).multiply()

class MultiplySkein:
	'A class to multiply a skein of extrusions.'
	def __init__(self, gcode):
		self.gcode = gcode
		self.isExtrusionActive = False
		self.layerIndex = 0
		self.layerLines = []
		self.lineIndex = 0
		self.lines = None
		self.oldLocation = None
		self.rowIndex = 0
		self.shouldAccumulate = True

		self.centerX = config.getfloat(name, 'center.x')
		self.centerY = config.getfloat(name, 'center.y')
		self.numberOfColumns = config.getint(name, 'columns')
		self.numberOfRows = config.getint(name, 'rows')
		self.reverseSequenceEveryOddLayer = config.getboolean(name, 'sequence.reverse.odd.layers')
		self.separationOverPerimeterWidth = config.getfloat(name, 'separation.over.perimeter.width')
		self.extrusionWidth = config.getfloat('carve', 'extrusion.width')
		self.centerOffset = complex(self.centerX, self.centerY)
		cornerMaximumComplex = self.gcode.carvingCornerMaximum.dropAxis()
		cornerMinimumComplex = self.gcode.carvingCornerMinimum.dropAxis()

		self.extent = cornerMaximumComplex - cornerMinimumComplex
		self.shapeCenter = 0.5 * (cornerMaximumComplex + cornerMinimumComplex)
		self.separation = self.separationOverPerimeterWidth * abs(self.extrusionWidth)
		self.extentPlusSeparation = self.extent + complex(self.separation, self.separation)
		columnsMinusOne = self.numberOfColumns - 1
		rowsMinusOne = self.numberOfRows - 1
		self.arrayExtent = complex(self.extentPlusSeparation.real * columnsMinusOne, self.extentPlusSeparation.imag * rowsMinusOne)
		self.arrayCenter = 0.5 * self.arrayExtent
		
	def multiply(self):
		'Multiply the 3D model.'
		
		elementOffsets = self.getElementOffsets()
		elementOffsetsCount = len(elementOffsets)
		self.gcode.elementOffsets = elementOffsets
		
		for key in self.gcode.layers.iterkeys():
			layer = self.gcode.layers[key]
			offsetNestedRings = []
			for nestedRing in layer.nestedRings:
				for (index,elementOffset) in enumerate(elementOffsets):
					offsetNestedRing = copy.deepcopy(nestedRing)
					offsetNestedRing.offset(elementOffset)
					offsetNestedRings.append(offsetNestedRing)
			layer.nestedRings = offsetNestedRings
	
	def getElementOffsets(self):
		'Returns a list of coordinates for the center of each copied layer'
		elementOffsets = []
		offset = self.centerOffset - self.arrayCenter - self.shapeCenter
		for rowIndex in xrange(self.numberOfRows):
			yRowOffset = float(rowIndex) * self.extentPlusSeparation.imag
			#if self.layerIndex % 2 == 1 and self.reverseSequenceEveryOddLayer:
			#	yRowOffset = self.arrayExtent.imag - yRowOffset
			for columnIndex in xrange(self.numberOfColumns):
				xColumnOffset = float(columnIndex) * self.extentPlusSeparation.real
				if self.rowIndex % 2 == 1:
					xColumnOffset = self.arrayExtent.real - xColumnOffset
				elementOffsets.append(complex(offset.real + xColumnOffset, offset.imag + yRowOffset))
			self.rowIndex += 1
		return elementOffsets
		