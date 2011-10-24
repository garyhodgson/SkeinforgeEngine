"""
Stretch is a script to stretch the threads to partially compensate for filament shrinkage when extruded.
"""

from fabmetheus_utilities import archive
from fabmetheus_utilities import euclidean
from fabmetheus_utilities import gcodec
from config import config
import logging

__originalauthor__ = 'Enrique Perez (perez_enrique@yahoo.com) modifed as SFACT by Ahmet Cem Turan (ahmetcemturan@gmail.com)'
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'

logger = logging.getLogger(__name__)
name = __name__

def getCraftedText( fileName, text):
	"Stretch a gcode linear move text."
	if not config.getboolean(name, 'active'):
		logger.info("%s plugin is not active", name.capitalize())
		return text
	return StretchSkein().getCraftedGcode( text)


class LineIteratorBackward:
	"Backward line iterator class."
	def __init__( self, isLoop, lineIndex, lines ):
		self.firstLineIndex = None
		self.isLoop = isLoop
		self.lineIndex = lineIndex
		self.lines = lines

	def getIndexBeforeNextDeactivate(self):
		"Get index two lines before the deactivate command."
		for lineIndex in xrange( self.lineIndex + 1, len(self.lines) ):
			line = self.lines[lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'M103':
				return lineIndex - 2
		print('This should never happen in stretch, no deactivate command was found for this thread.')
		raise StopIteration, "You've reached the end of the line."

	def getNext(self):
		"Get next line going backward or raise exception."
		while self.lineIndex > 3:
			if self.lineIndex == self.firstLineIndex:
				raise StopIteration, "You've reached the end of the line."
			if self.firstLineIndex == None:
				self.firstLineIndex = self.lineIndex
			nextLineIndex = self.lineIndex - 1
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'M103':
				if self.isLoop:
					nextLineIndex = self.getIndexBeforeNextDeactivate()
				else:
					raise StopIteration, "You've reached the end of the line."
			if firstWord == 'G1':
				if self.isBeforeExtrusion():
					if self.isLoop:
						nextLineIndex = self.getIndexBeforeNextDeactivate()
					else:
						raise StopIteration, "You've reached the end of the line."
				else:
					self.lineIndex = nextLineIndex
					return line
			self.lineIndex = nextLineIndex
		raise StopIteration, "You've reached the end of the line."

	def isBeforeExtrusion(self):
		"Determine if index is two or more before activate command."
		linearMoves = 0
		for lineIndex in xrange( self.lineIndex + 1, len(self.lines) ):
			line = self.lines[lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1':
				linearMoves += 1
			if firstWord == 'M101':
				return linearMoves > 0
			if firstWord == 'M103':
				return False
		print('This should never happen in isBeforeExtrusion in stretch, no activate command was found for this thread.')
		return False


class LineIteratorForward:
	"Forward line iterator class."
	def __init__( self, isLoop, lineIndex, lines ):
		self.firstLineIndex = None
		self.isLoop = isLoop
		self.lineIndex = lineIndex
		self.lines = lines

	def getIndexJustAfterActivate(self):
		"Get index just after the activate command."
		for lineIndex in xrange( self.lineIndex - 1, 3, - 1 ):
			line = self.lines[lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'M101':
				return lineIndex + 1
		print('This should never happen in stretch, no activate command was found for this thread.')
		raise StopIteration, "You've reached the end of the line."

	def getNext(self):
		"Get next line or raise exception."
		while self.lineIndex < len(self.lines):
			if self.lineIndex == self.firstLineIndex:
				raise StopIteration, "You've reached the end of the line."
			if self.firstLineIndex == None:
				self.firstLineIndex = self.lineIndex
			nextLineIndex = self.lineIndex + 1
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'M103':
				if self.isLoop:
					nextLineIndex = self.getIndexJustAfterActivate()
				else:
					raise StopIteration, "You've reached the end of the line."
			self.lineIndex = nextLineIndex
			if firstWord == 'G1':
				return line
		raise StopIteration, "You've reached the end of the line."

class StretchSkein:
	"A class to stretch a skein of extrusions."
	def __init__(self):
		self.gcode = gcodec.Gcode()
		self.extruderActive = False
		self.feedRateMinute = 959.0
		self.isLoop = False
		self.lineIndex = 0
		self.lines = None
		self.oldLocation = None
		self.perimeterWidth = 0.4
		
		self.activateStretch = config.getboolean(name, 'active')
		self.crossLimitDistanceOverPerimeterWidth = config.getfloat(name, 'cross.limit.distance.ratio')
		self.loopStretchOverPerimeterWidth = config.getfloat(name, 'loop.stretch.ratio')
		self.pathStretchOverPerimeterWidth = config.getfloat(name, 'path.stretch.ratio')
		self.perimeterInsideStretchOverPerimeterWidth = config.getfloat(name, 'perimeter.inside.stretch.ratio')
		self.perimeterOutsideStretchOverPerimeterWidth = config.getfloat(name, 'perimeter.outside.stretch.ratio')
		self.stretchFromDistanceOverPerimeterWidth = config.getfloat(name, 'stretch.from.distance.ratio')

	def getCraftedGcode( self, gcodeText):
		"Parse gcode text and store the stretch gcode."
		self.lines = archive.getTextLines(gcodeText)
		self.parseInitialization()
		for self.lineIndex in xrange(self.lineIndex, len(self.lines)):
			line = self.lines[self.lineIndex]
			self.parseStretch(line)
		return self.gcode.output.getvalue()

	def getCrossLimitedStretch( self, crossLimitedStretch, crossLineIterator, locationComplex ):
		"Get cross limited relative stretch for a location."
		try:
			line = crossLineIterator.getNext()
		except StopIteration:
			return crossLimitedStretch
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		pointComplex = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine).dropAxis()
		pointMinusLocation = locationComplex - pointComplex
		pointMinusLocationLength = abs( pointMinusLocation )
		if pointMinusLocationLength <= self.crossLimitDistanceFraction:
			return crossLimitedStretch
		parallelNormal = pointMinusLocation / pointMinusLocationLength
		parallelStretch = euclidean.getDotProduct( parallelNormal, crossLimitedStretch ) * parallelNormal
		if pointMinusLocationLength > self.crossLimitDistance:
			return parallelStretch
		crossNormal = complex( parallelNormal.imag, - parallelNormal.real )
		crossStretch = euclidean.getDotProduct( crossNormal, crossLimitedStretch ) * crossNormal
		crossPortion = ( self.crossLimitDistance - pointMinusLocationLength ) / self.crossLimitDistanceRemainder
		return parallelStretch + crossStretch * crossPortion

	def getRelativeStretch( self, locationComplex, lineIterator ):
		"Get relative stretch for a location."
		lastLocationComplex = locationComplex
		oldTotalLength = 0.0
		pointComplex = locationComplex
		totalLength = 0.0
		while 1:
			try:
				line = lineIterator.getNext()
			except StopIteration:
				locationMinusPoint = locationComplex - pointComplex
				locationMinusPointLength = abs( locationMinusPoint )
				if locationMinusPointLength > 0.0:
					return locationMinusPoint / locationMinusPointLength
				return complex()
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = splitLine[0]
			pointComplex = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine).dropAxis()
			locationMinusPoint = lastLocationComplex - pointComplex
			locationMinusPointLength = abs( locationMinusPoint )
			totalLength += locationMinusPointLength
			if totalLength >= self.stretchFromDistance:
				distanceFromRatio = ( self.stretchFromDistance - oldTotalLength ) / locationMinusPointLength
				totalPoint = distanceFromRatio * pointComplex + ( 1.0 - distanceFromRatio ) * lastLocationComplex
				locationMinusTotalPoint = locationComplex - totalPoint
				return locationMinusTotalPoint / self.stretchFromDistance
			lastLocationComplex = pointComplex
			oldTotalLength = totalLength

	def getStretchedLine( self, splitLine ):
		"Get stretched gcode line."
		location = gcodec.getLocationFromSplitLine(self.oldLocation, splitLine)
		self.feedRateMinute = gcodec.getFeedRateMinute( self.feedRateMinute, splitLine )
		self.oldLocation = location
		if self.extruderActive and self.threadMaximumAbsoluteStretch > 0.0:
			return self.getStretchedLineFromIndexLocation( self.lineIndex - 1, self.lineIndex + 1, location )
		if self.isJustBeforeExtrusion() and self.threadMaximumAbsoluteStretch > 0.0:
			return self.getStretchedLineFromIndexLocation( self.lineIndex - 1, self.lineIndex + 1, location )
		return self.lines[self.lineIndex]

	def getStretchedLineFromIndexLocation( self, indexPreviousStart, indexNextStart, location ):
		"Get stretched gcode line from line index and location."
		crossIteratorForward = LineIteratorForward( self.isLoop, indexNextStart, self.lines )
		crossIteratorBackward = LineIteratorBackward( self.isLoop, indexPreviousStart, self.lines )
		iteratorForward = LineIteratorForward( self.isLoop, indexNextStart, self.lines )
		iteratorBackward = LineIteratorBackward( self.isLoop, indexPreviousStart, self.lines )
		locationComplex = location.dropAxis()
		relativeStretch = self.getRelativeStretch( locationComplex, iteratorForward ) + self.getRelativeStretch( locationComplex, iteratorBackward )
		relativeStretch *= 0.8
		relativeStretch = self.getCrossLimitedStretch( relativeStretch, crossIteratorForward, locationComplex )
		relativeStretch = self.getCrossLimitedStretch( relativeStretch, crossIteratorBackward, locationComplex )
		relativeStretchLength = abs( relativeStretch )
		if relativeStretchLength > 1.0:
			relativeStretch /= relativeStretchLength
		absoluteStretch = relativeStretch * self.threadMaximumAbsoluteStretch
		stretchedPoint = location.dropAxis() + absoluteStretch
		return self.gcode.getLinearGcodeMovementWithFeedRate( self.feedRateMinute, stretchedPoint, location.z )

	def isJustBeforeExtrusion(self):
		"Determine if activate command is before linear move command."
		for lineIndex in xrange( self.lineIndex + 1, len(self.lines) ):
			line = self.lines[lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			if firstWord == 'G1' or firstWord == 'M103':
				return False
			if firstWord == 'M101':
				return True
		return False

	def parseInitialization(self):
		'Parse gcode initialization and store the parameters.'
		for self.lineIndex in xrange(len(self.lines)):
			line = self.lines[self.lineIndex]
			splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
			firstWord = gcodec.getFirstWord(splitLine)
			self.gcode.parseSplitLine(firstWord, splitLine)
			if firstWord == '(</extruderInitialization>)':
				self.gcode.addLine('(<procedureName> stretch </procedureName>)')
				return
			elif firstWord == '(<perimeterWidth>':
				perimeterWidth = float(splitLine[1])
				self.crossLimitDistance = self.perimeterWidth * self.crossLimitDistanceOverPerimeterWidth
				self.loopMaximumAbsoluteStretch = self.perimeterWidth * self.loopStretchOverPerimeterWidth
				self.pathAbsoluteStretch = self.perimeterWidth * self.pathStretchOverPerimeterWidth
				self.perimeterInsideAbsoluteStretch = self.perimeterWidth * self.perimeterInsideStretchOverPerimeterWidth
				self.perimeterOutsideAbsoluteStretch = self.perimeterWidth * self.perimeterOutsideStretchOverPerimeterWidth
				self.stretchFromDistance = self.stretchFromDistanceOverPerimeterWidth * perimeterWidth
				self.threadMaximumAbsoluteStretch = self.pathAbsoluteStretch
				self.crossLimitDistanceFraction = 0.333333333 * self.crossLimitDistance
				self.crossLimitDistanceRemainder = self.crossLimitDistance - self.crossLimitDistanceFraction
			self.gcode.addLine(line)

	def parseStretch(self, line):
		"Parse a gcode line and add it to the stretch skein."
		splitLine = gcodec.getSplitLineBeforeBracketSemicolon(line)
		if len(splitLine) < 1:
			return
		firstWord = splitLine[0]
		if firstWord == 'G1':
			line = self.getStretchedLine(splitLine)
		elif firstWord == 'M101':
			self.extruderActive = True
		elif firstWord == 'M103':
			self.extruderActive = False
			self.setStretchToPath()
		elif firstWord == '(<loop>':
			self.isLoop = True
			self.threadMaximumAbsoluteStretch = self.loopMaximumAbsoluteStretch
		elif firstWord == '(</loop>)':
			self.setStretchToPath()
		elif firstWord == '(<perimeter>':
			self.isLoop = True
			self.threadMaximumAbsoluteStretch = self.perimeterInsideAbsoluteStretch
			if splitLine[1] == 'outer':
				self.threadMaximumAbsoluteStretch = self.perimeterOutsideAbsoluteStretch
		elif firstWord == '(</perimeter>)':
			self.setStretchToPath()
		self.gcode.addLine(line)

	def setStretchToPath(self):
		"Set the thread stretch to path stretch and is loop false."
		self.isLoop = False
		self.threadMaximumAbsoluteStretch = self.pathAbsoluteStretch
