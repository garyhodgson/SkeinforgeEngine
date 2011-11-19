"""
Simple editor class extracted from macroed class in Printrun pronterface module.

Credits:
    Original Author: Kliment (https://github.com/kliment/Printrun)

"""

try:
    import wx
except:
    print _("WX is not installed. This program requires WX to run.")
    raise

class SimpleEditor(wx.Dialog):
    """Really simple editor"""
    def __init__(self, filename, text, callback):
        self.originalText = text
        self.filename = filename
        wx.Dialog.__init__(self, None, title=filename, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.callback = callback
        self.panel = wx.Panel(self, -1)
        topsizer = wx.BoxSizer(wx.VERTICAL)
        
        self.e = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE + wx.HSCROLL, size=(400, 300))
        self.e.SetValue(text)
        self.e.Bind(wx.EVT_TEXT, self.onTextChange)
        
        topsizer.Add(self.e, 1, wx.ALL + wx.EXPAND)
        
        commandsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okb = wx.Button(self.panel, -1, "Save")
        self.okb.Bind(wx.EVT_BUTTON, self.save)
        self.okb.Disable()
        self.Bind(wx.EVT_CLOSE, self.close)
        commandsizer.Add(self.okb)
        self.cancelb = wx.Button(self.panel, -1, "Cancel")
        self.cancelb.Bind(wx.EVT_BUTTON, self.close)
        commandsizer.Add(self.cancelb)
        topsizer.Add(commandsizer, 0, wx.EXPAND)
        
        self.panel.SetSizer(topsizer)
        topsizer.Layout()
        topsizer.Fit(self)
        self.Show()
        self.e.SetFocus()
        self.e.SetSelection(0,0)
        
    def save(self, ev):
        self.Destroy()
        self.callback(self.e.GetValue())
        
    def close(self, ev):
        self.Destroy()

    def onTextChange(self, ev):
        if self.e.GetValue() != self.originalText:
            self.SetTitle("%s*"%self.filename)
            self.okb.Enable()
        else:
            self.SetTitle(self.filename)
            self.okb.Disable()