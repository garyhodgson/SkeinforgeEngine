[profile]
name=default

[export]
delete.comments=true
file.extension=gcode
replace.filename=replace.csv
gcode.penultimate.save=true
file.extension.profile=true

[preface]
start.file=start.gmc
end.file=end.gmc
positioning.absolute=true
units.millimeters=true
startup.at.home=false
startup.extruder.reset=true

[carve]
layer.height=0.4
extrusion.width=0.6
layer.print.from=0
layer.print.to=912345678
infill.bridge.direction=true
mesh.correct=true
mesh.unproven=false
extra.decimal.places=4.0
import.coarseness.ratio=1.0
export.svg=true
export.carving=true

[inset]
bridge.width.multiplier.ratio=1.0
nozzle.diameter=0.5
loop.order.preferloops=true
overlap.removal.scaler=1.0

[bottom]
active=true
additional.height.ratio=0.5
altitude=0.0

[fill]
active=true
infill.solidity.ratio=0.35
extrusion.lines.extra.spacer.scaler=1.0
infill.overlap.over.perimeter.scaler=1.0
shells.alternating.solid=3
shells.base=2
shells.sparse=2
fully.filled.layers=2
;LowerLeft | Nearest
extrusion.sequence.start.layer=LowerLeft
extrusion.sequence.print.order=perimeter,loops,infill
; Only line is currently supported
infill.pattern=Line
grid.extra.overlap=0.1
diaphragm.every.n.layers=100
diaphragm.thickness=0
infill.rotation.begin=45.0
infill.rotation.repeat=1
infill.rotation.odd.layer=90.0

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
flow.rate=1.0
acceleration.rate=1300.0
feed.rate.orbiting.ratio=0.5
feed.rate.perimeter=30.0
flow.rate.perimeter=1.0
acceleration.rate.perimeter=50.0
feed.rate.bridge.ratio=1.0
flow.rate.bridge=1.0
acceleration.rate.bridge=1000.0
feed.rate.travel=130.0
dc.duty.cycle.beginning=1.0
dc.duty.cycle.end=0.0

[raft]
active=true
add.raft.elevate.nozzle.orbit=true
; None | EmptyLayersOnly | Everywhere | ExteriorOnly
support.location=None
support.min.angle=50.0
support.crosshatch=false
interface.infill.density=0.25
interface.layer.thickness.ratio=1.0
support.feed.rate=15.0
support.flow.rate.ratio=1.0
support.gap.over.perimeter.extrusion.width.ratio=1.0
support.extension.percent=0.0
support.extension.distance=2.0
support.end.file=support_end.gmc
support.start.file=support_start.gmc
nozzle.clearance.ratio=0.0
firstlayer.feed.rate=35.0
firstlayer.feed.rate.perimeter=25.0
firstlayer.flow.rate.infill=1.0
firstlayer.flow.rate.perimeter=1.0
firstlayer.travel.rate=50.0
interface.layers=0
interface.feed.rate.ratio=1.0
interface.flow.rate.ratio=1.0
interface.nozzle.clearance.ratio=0.45
base.layers=0
base.feed.rate.ratio=0.5
base.flow.rate.ratio=0.5
base.infill.density.ratio=0.5
base.layer.thickness.ratio=2.0
base.nozzle.clearance.ratio=0.4
initial.circling=false
infill.overhang.ratio=3.0

[dimension]
active=true
filament.diameter=2.8
filament.packing.density=1.0
calibrating.active=false
calibrating.x.section=0.5
oozerate=75.0
extruder.retraction.speed=15.0
; relative | absolute
extrusion.units=absolute

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
; Orbit | SlowDown
cool.type=SlowDown
maximum.cool=2.0
bridge.cool=1.0
minimum.orbital.radius=10.0

[stretch]
active=true
cross.limit.distance.ratio=5.0
loop.stretch.ratio=0.11
path.stretch.ratio=0.0
perimeter.inside.stretch.ratio=0.64
perimeter.outside.stretch.ratio=0.1
stretch.from.distance.ratio=2.0