[profile]
name=default

[export]
debug=false
delete.comments=true
file.extension=gcode
file.extension.profile=true
replace.filename=replace.csv
export.slicedmodel=true
export.slicedmodel.extension=slicedmodel.txt
export.pickled.slicedmodel=false
export.pickled.slicedmodel.extension=slicedmodel.pickled
overwrite.pickled.slicedmodel=false


[preface]
debug=false
start.file=start.gmc
end.file=end.gmc
positioning.absolute=true
units.millimeters=true
startup.at.home=false
startup.extruder.reset=true

[carve]
debug=false
layer.height=0.4
extrusion.width=0.6
layer.print.from=0
layer.print.to=912345678
infill.bridge.direction=true
mesh.correct=true
import.coarseness.ratio=1.0

[inset]
debug=false
; The pypy interpreter produces faster results with multiprocessing turned off.
multiprocess=false
bridge.width.multiplier.ratio=1.0
nozzle.diameter=0.5
loop.order.preferloops=true
overlap.removal.scaler=1.0

[bottom]
active=true
debug=false
additional.height.ratio=0.5
altitude=0.0

[fill]
active=true
debug=false
infill.solidity.ratio=0.35
extrusion.lines.extra.spacer.scaler=1.0
infill.overlap.over.perimeter.scaler=1.0
shells.alternating.solid=2
shells.base=2
shells.sparse=2
fully.filled.layers=2
;LowerLeft | Nearest
extrusion.sequence.start.layer=LowerLeft
extrusion.sequence.print.order=perimeter,loops,infill
diaphragm.every.n.layers=100
diaphragm.thickness=0
infill.rotation.begin=45.0
infill.rotation.repeat=1
infill.rotation.odd.layer=90.0
; LineFillStrategy
strategy.path=plugins/strategies
strategy=LineFillStrategy

[multiply]
active=true
center.x=100.0
center.y=100.0
columns=1
rows=1
sequence.reverse.odd.layers=false
separation.over.perimeter.width=15.0

[speed]
active=true
add.flow.rate=true
add.acceleration.rate=false
feed.rate=60.0
flow.rate.ratio=1.0
acceleration.rate=1300.0
feed.rate.orbiting.ratio=0.5
feed.rate.perimeter=30.0
flow.rate.perimeter.ratio=1.0
acceleration.rate.perimeter=50.0
feed.rate.bridge.ratio=1.0
flow.rate.bridge.ratio=1.0
acceleration.rate.bridge=1000.0
feed.rate.travel=130.0
feed.rate.support=15.0
flow.rate.support.ratio=1.0

[support]
active=true
debug=true
; location
; 	ExteriorOnly: 		Support material will be added only the exterior of the object.  This is the best option for most objects which require support material.
; 	EmptyLayersOnly: 	Support material will be only on the empty layers.  This is useful when making identical objects in a stack.
; 	Everywhere:			Support material will be added wherever there are overhangs, even inside the object.  Because support material inside objects is hard or impossible to remove, this option should only be chosen if the object has a cavity that needs support and there is some way to extract the support material.
location=ExteriorOnly
min.angle=40.0
crosshatch=false
gap.over.perimeter.extrusion.width.ratio=1.0
extension.percent=0.0
extension.distance=2.0
support.end.file=support_end.gmc
support.start.file=support_start.gmc
infill.overhang.ratio=3.0
interface.infill.density=0.25
interface.layer.thickness.ratio=1.0

[dimension]
active=true
filament.diameter=2.8
filament.packing.density=1.0
oozerate=75.0
extruder.retraction.speed=15.0
extrusion.units.relative=false
decimal.places=4

[comb]
active=true

[cool]
active=true
minimum.layer.time=10.0
minimum.layer.feed.rate=15.0
turn.on.fan.at.beginning=true
turn.off.fan.at.end=true
cool.start.file=cool_start.gmc
cool.end.file=cool_end.gmc
; OrbitCoolStrategy | SlowDownCoolStrategy
strategy.path=plugins/strategies
strategy=SlowDownCoolStrategy
orbital.margin=10.0
