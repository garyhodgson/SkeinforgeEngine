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
    def __init__(self, filename, text, callback, readonly=False):
        self.originalText = text
        self.filename = filename
        self.readonly = readonly
        
        if self.readonly:
            self.title = '%s (readonly)'%filename
        else :
            self.title = filename
        
        wx.Dialog.__init__(self, None, title=self.title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.callback = callback
        self.panel = wx.Panel(self, -1)
        topsizer = wx.BoxSizer(wx.VERTICAL)
        
        self.editorTxtCtrl = wx.TextCtrl(self.panel, style=wx.TE_MULTILINE + wx.HSCROLL, size=(400, 300))
        self.editorTxtCtrl.SetValue(text)
        self.editorTxtCtrl.SetEditable(not self.readonly)
        self.editorTxtCtrl.Bind(wx.EVT_TEXT, self.onTextChange)
        
        topsizer.Add(self.editorTxtCtrl, 1, wx.ALL + wx.EXPAND)
        
        commandsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.okBtn = wx.Button(self.panel, -1, "Save")
        self.okBtn.Bind(wx.EVT_BUTTON, self.save)
        self.okBtn.Disable()
        self.Bind(wx.EVT_CLOSE, self.close)
        self.Bind(wx.EVT_CHAR_HOOK, self.onKeyPress)
        commandsizer.Add(self.okBtn)
        self.cancelBtn = wx.Button(self.panel, -1, "Cancel")
        self.cancelBtn.Bind(wx.EVT_BUTTON, self.close)
        commandsizer.Add(self.cancelBtn)
        topsizer.Add(commandsizer, 0, wx.EXPAND)
        
        self.panel.SetSizer(topsizer)
        topsizer.Layout()
        topsizer.Fit(self)
        self.Show()
        self.editorTxtCtrl.SetFocus()
        self.editorTxtCtrl.SetSelection(0,0)
        
    def save(self, event):
        self.Destroy()
        self.callback(self.editorTxtCtrl.GetValue())
        
    def close(self, event):
        self.Destroy()

    def onKeyPress(self, event):
        x = event.GetKeyCode()
        if x == wx.WXK_ESCAPE:
            if self.editorTxtCtrl.GetValue() != self.originalText:
                msgDlg = wx.MessageDialog(self, 'Save changes?', 'Confirm', wx.YES_NO | wx.CANCEL | wx.ICON_QUESTION)
                result = msgDlg.ShowModal()
                msgDlg.Destroy()
                if result == wx.ID_YES:
                    self.save(event)
                elif result == wx.ID_NO:
                    self.close(event)
        event.Skip()
    
    def onTextChange(self, event):
        if self.editorTxtCtrl.GetValue() != self.originalText:
            self.SetTitle("%s*"%self.title)
            self.okBtn.Enable()
        else:
            self.SetTitle(self.title)
            self.okBtn.Disable()