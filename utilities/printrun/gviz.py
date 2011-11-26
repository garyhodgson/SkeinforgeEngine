"""
Gcode visualisation class extracted from Printrun application.

Credits:
    Original Author: Kliment (https://github.com/kliment/Printrun)

"""
import wx, time, sys

class window(wx.Frame):
    def __init__(self, f, title="Layer view",size=(600, 600), bedsize=(200, 200), grid=(10, 50), extrusion_width=0.5):
        wx.Frame.__init__(self, None, title="%s (Use shift+mousewheel to switch layers)"%title, size=(size[0], size[1]))
        self.p = gviz(self, size=size, bedsize=bedsize, grid=grid, extrusion_width=extrusion_width)
        s = time.time()
        for i in f:
            self.p.addgcode(i)
        self.initpos = [0, 0]
        self.p.Bind(wx.EVT_CHAR_HOOK, self.key)
        self.Bind(wx.EVT_CHAR_HOOK, self.key)
        self.p.Bind(wx.EVT_MOUSEWHEEL, self.zoom)
        self.Bind(wx.EVT_MOUSEWHEEL, self.zoom)
        self.p.Bind(wx.EVT_MOUSE_EVENTS, self.mouse)
        self.Bind(wx.EVT_MOUSE_EVENTS, self.mouse)
        
    def mouse(self, event):
        if event.ButtonUp(wx.MOUSE_BTN_LEFT):
            if(self.initpos is not None):
                self.initpos = None
        elif event.Dragging():
            e = event.GetPositionTuple()
            if self.initpos is None or not hasattr(self, "basetrans"):
                self.initpos = e
                self.basetrans = self.p.translate
            self.p.translate = [ self.basetrans[0] + (e[0] - self.initpos[0]),
                            self.basetrans[1] + (e[1] - self.initpos[1]) ]
            self.p.repaint()
            self.p.Refresh()
        
        else:
            event.Skip()
    
    def key(self, event):
        x = event.GetKeyCode()
        if x == wx.WXK_UP:
            self.p.layerup()
        if x == wx.WXK_DOWN:
            self.p.layerdown()
    
    def zoom(self, event):
        z = event.GetWheelRotation()
        if event.ShiftDown():
            if z > 0:   self.p.layerdown()
            elif z < 0: self.p.layerup()
        else:
            if z > 0:   self.p.zoom(event.GetX(), event.GetY(), 1.2)
            elif z < 0: self.p.zoom(event.GetX(), event.GetY(), 1 / 1.2)
        
class gviz(wx.Panel):
    def __init__(self, parent, size=(200, 200), bedsize=(200, 200), grid=(10, 50), extrusion_width=0.5):
        wx.Panel.__init__(self, parent, -1, size=(size[0], size[1]))
        self.size = size
        self.bedsize = bedsize
        self.grid = grid
        self.lastpos = [0, 0, 0, 0, 0, 0, 0]
        self.hilightpos = self.lastpos[:]
        self.Bind(wx.EVT_PAINT, self.paint)
        self.Bind(wx.EVT_SIZE, lambda * e:(wx.CallAfter(self.repaint), wx.CallAfter(self.Refresh)))
        self.lines = {}
        self.pens = {}
        self.arcs = {}
        self.arcpens = {}
        self.layers = []
        self.layerindex = 0
        self.filament_width = extrusion_width # set it to 0 to disable scaling lines with zoom
        self.scale = [min(float(size[0]) / bedsize[0], float(size[1]) / bedsize[1])] * 2
        penwidth = max(1.0, self.filament_width * ((self.scale[0] + self.scale[1]) / 2.0))
        self.translate = [0.0, 0.0]
        self.mainpen = wx.Pen(wx.Colour(0, 0, 0), penwidth)
        self.arcpen = wx.Pen(wx.Colour(255, 0, 0), penwidth)
        self.travelpen = wx.Pen(wx.Colour(10, 80, 80), penwidth)
        self.hlpen = wx.Pen(wx.Colour(200, 50, 50), penwidth)
        self.fades = [wx.Pen(wx.Colour(250 - 0.6 ** i * 100, 250 - 0.6 ** i * 100, 200 - 0.4 ** i * 50), penwidth) for i in xrange(6)]
        self.penslist = [self.mainpen, self.travelpen, self.hlpen] + self.fades
        self.showall = 0
        self.hilight = []
        self.hilightarcs = []
        self.dirty = 1
        self.blitmap = wx.EmptyBitmap(self.GetClientSize()[0], self.GetClientSize()[1], -1)
        
    def clear(self):
        self.lastpos = [0, 0, 0, 0, 0, 0, 0]
        self.lines = {}
        self.pens = {}
        self.layers = []
        self.layerindex = 0
        self.showall = 0
        self.dirty = 1
  
    def layerup(self):
        if(self.layerindex + 1 < len(self.layers)):
            self.layerindex += 1
            self.repaint()
            self.Refresh()
    
    def layerdown(self):
        if(self.layerindex > 0):
            self.layerindex -= 1
            self.repaint()
            self.Refresh()
    
    def setlayer(self, layer):
        try:
            self.layerindex = self.layers.index(layer)
            self.repaint()
            wx.CallAfter(self.Refresh)
            self.showall = 0
        except:
            pass    

    def zoom(self, x, y, factor):
        self.scale = [s * factor for s in self.scale]
        self.translate = [ x - (x - self.translate[0]) * factor,
                            y - (y - self.translate[1]) * factor]
        penwidth = max(1.0, self.filament_width * ((self.scale[0] + self.scale[1]) / 2.0))
        for pen in self.penslist:
            pen.SetWidth(penwidth)
        self.repaint()
        self.Refresh()
        
    def repaint(self):
        self.blitmap = wx.EmptyBitmap(self.GetClientSize()[0], self.GetClientSize()[1], -1)
        dc = wx.MemoryDC()
        dc.SelectObject(self.blitmap)
        dc.SetBackground(wx.Brush((250, 250, 200)))
        dc.Clear()
        dc.SetPen(wx.Pen(wx.Colour(180, 180, 150)))
        for grid_unit in self.grid:
            if grid_unit > 0:
                for x in xrange(int(self.bedsize[0] / grid_unit) + 1):
                    dc.DrawLine(self.translate[0] + x * self.scale[0] * grid_unit, self.translate[1], self.translate[0] + x * self.scale[0] * grid_unit, self.translate[1] + self.scale[1] * self.bedsize[1])
                for y in xrange(int(self.bedsize[1] / grid_unit) + 1):
                    dc.DrawLine(self.translate[0], self.translate[1] + y * self.scale[1] * grid_unit, self.translate[0] + self.scale[0] * self.bedsize[0], self.translate[1] + y * self.scale[1] * grid_unit)
            dc.SetPen(wx.Pen(wx.Colour(0, 0, 0)))
        if not self.showall:
            self.size = self.GetSize()
            dc.SetBrush(wx.Brush((43, 144, 255)))
            dc.DrawRectangle(self.size[0] - 15, 0, 15, self.size[1])
            dc.SetBrush(wx.Brush((0, 255, 0)))
            if len(self.layers):
                dc.DrawRectangle(self.size[0] - 14, (1.0 - (1.0 * (self.layerindex + 1)) / len(self.layers)) * self.size[1], 13, self.size[1] - 1)
            
        def _drawlines(lines, pens):
            def _scaler(x):
                return (self.scale[0] * x[0] + self.translate[0],
                        self.scale[1] * x[1] + self.translate[1],
                        self.scale[0] * x[2] + self.translate[0],
                        self.scale[1] * x[3] + self.translate[1],)
            scaled_lines = map(_scaler, lines)
            dc.DrawLineList(scaled_lines, pens)
        
        def _drawarcs(arcs, pens):
            def _scaler(x):
                return (self.scale[0] * x[0] + self.translate[0],
                        self.scale[1] * x[1] + self.translate[1],
                        self.scale[0] * x[2] + self.translate[0],
                        self.scale[1] * x[3] + self.translate[1],
                        self.scale[0] * x[4] + self.translate[0],
                        self.scale[1] * x[5] + self.translate[1],)
            scaled_arcs = map(_scaler, arcs)
            for i in range(len(scaled_arcs)):
                dc.SetPen(pens[i] if type(pens).__name__ == 'list' else pens)
                dc.SetBrush(wx.TRANSPARENT_BRUSH)
                dc.DrawArc(*scaled_arcs[i])
        
        if self.showall:
            l = []
            for i in self.layers:
                dc.DrawLineList(l, self.fades[0])
                _drawlines(self.lines[i], self.pens[i])
                _drawarcs(self.arcs[i], self.arcpens[i])
            return
        if self.layerindex < len(self.layers) and self.layers[self.layerindex] in self.lines.keys():
            for layer_i in xrange(max(0, self.layerindex - 6), self.layerindex):
                _drawlines(self.lines[self.layers[layer_i]], self.fades[self.layerindex - layer_i - 1])
                _drawarcs(self.arcs[self.layers[layer_i]], self.fades[self.layerindex - layer_i - 1])
            _drawlines(self.lines[self.layers[self.layerindex]], self.pens[self.layers[self.layerindex]])
            _drawarcs(self.arcs[self.layers[self.layerindex]], self.arcpens[self.layers[self.layerindex]])
        
        _drawlines(self.hilight, self.hlpen)
        _drawarcs(self.hilightarcs, self.hlpen)
        
        dc.SelectObject(wx.NullBitmap)
    
    def paint(self, event):
        dc = wx.PaintDC(self)
        if(self.dirty):
            self.repaint()
        self.dirty = 0
        sz = self.GetClientSize()
        dc.DrawBitmap(self.blitmap, 0, 0)
        del dc
        
    def addgcode(self, gcode="M105", hilight=0):
        gcode = gcode.split("*")[0]
        gcode = gcode.split(";")[0]
        gcode = gcode.lower().strip().split()
        if len(gcode) == 0:
            return
        
        def _readgcode():
            target = self.lastpos[:]
            if hilight:
                target = self.hilightpos[:]
            for i in gcode:
                if i[0] == "x":
                    target[0] = float(i[1:])
                elif i[0] == "y":
                    target[1] = float(i[1:])
                elif i[0] == "z":
                    target[2] = float(i[1:])
                elif i[0] == "e":
                    target[3] = float(i[1:])
                elif i[0] == "f":
                    target[4] = float(i[1:])
                elif i[0] == "i":
                    target[5] = float(i[1:])
                elif i[0] == "j":
                    target[6] = float(i[1:])
            if not hilight:
                if not target[2] in self.lines.keys():
                    self.lines[target[2]] = []
                    self.pens[target[2]] = []
                    self.arcs[target[2]] = []
                    self.arcpens[target[2]] = []
                    self.layers += [target[2]]
            return target
        
        def _y(y):
            return self.bedsize[1] - y
        
        start_pos = self.hilightpos[:] if hilight else self.lastpos[:]
        
        if gcode[0] == "g1":
            target = _readgcode()
            line = [ start_pos[0], _y(start_pos[1]), target[0], _y(target[1]) ]
            if not hilight:
                self.lines[ target[2] ] += [line]
                self.pens[ target[2] ] += [self.mainpen if target[3] != self.lastpos[3] else self.travelpen]
                self.lastpos = target
            else:
                self.hilight += [line]
                self.hilightpos = target
            self.dirty = 1
        
        if gcode[0] in [ "g2", "g3" ]:
            target = _readgcode()
            arc = []
            arc += [ start_pos[0], _y(start_pos[1]) ]
            arc += [ target[0], _y(target[1]) ]
            arc += [ start_pos[0] + target[5], _y(start_pos[1] + target[6]) ]  # center
            if gcode[0] == "g2":  # clockwise, reverse endpoints
                arc[0], arc[1], arc[2], arc[3] = arc[2], arc[3], arc[0], arc[1]
            
            if not hilight:
                self.arcs[ target[2] ] += [arc]
                self.arcpens[ target[2] ] += [self.arcpen]
                self.lastpos = target
            else:
                self.hilightarcs += [arc]
                self.hilightpos = target
            self.dirty = 1
            
def main(argv=None):
    if argv is None: 
        argv = sys.argv[1:]
    app = wx.App(False)
    main = window(open(argv[0]))
    main.Show()
    app.MainLoop()
      
if __name__ == '__main__':
    main()
