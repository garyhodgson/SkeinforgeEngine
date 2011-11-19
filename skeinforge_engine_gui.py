#!/usr/bin/env python

from threading import Thread
import ConfigParser
import logging
import os
import skeinforge_engine
import sys
try:
    import wx
except:
    print "WX is not installed. This program requires WX to run."
    raise

config = ConfigParser.ConfigParser(allow_no_value=True)

class RedirectText:
    def __init__(self, aWxTextCtrl):
        self.out = aWxTextCtrl

    def write(self, string):
        self.out.WriteText(string)

class MyFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX | wx.RESIZE_BORDER
        wx.Frame.__init__(self, *args, **kwds)
        self.SetIcon(wx.Icon("SkeinforgeEngine.ico", wx.BITMAP_TYPE_ICO))
        self.SetBackgroundColour(wx.WHITE)
        self.profiles = ["None (Default)"]
        lastProfileName = config.get('runtime', 'last.profile')
        lastProfileIndex = 0
        
        self.profilesDirectory = config.get('general', 'profiles.location')        
        if not os.path.exists(self.profilesDirectory):
            self.logTxtCtrl.WriteText("Invalid profiles directory: %s" % self.profilesDirectory)
        else:
            index = 1
            for f in os.listdir(self.profilesDirectory):
                profilePath = os.path.join(self.profilesDirectory, f)
                if os.path.isfile(profilePath):
                    if f == lastProfileName:
                        lastProfileIndex = index 
                    self.profiles.append(f)
                    index += 1
                           
        self.profileLbl = wx.StaticText(self, -1, "Profile", size=(-1, -1))
        self.fileLbl = wx.StaticText(self, -1, "File", size=(-1, -1))
        self.logLbl = wx.StaticText(self, -1, "Log", size=(-1, -1))        
        
        
        self.fileBtn = wx.Button(self, -1, "Open...", size=(100, -1))
        self.skeinBtn = wx.Button(self, -1, "Skein", size=(100, -1))
        self.editProfileBtn = wx.Button(self, -1, "Edit...", size=(100, -1))
        
        self.profilesCB = wx.ComboBox(self, -1, size=(300, -1), choices=self.profiles, style=wx.CB_READONLY)
        self.profilesCB.SetSelection(lastProfileIndex)
        self.editProfileBtn.Enable(self.profilesCB.GetSelection() > 0)
        
        self.fileTxt = wx.TextCtrl(self, -1, "", size=(300, -1))
        self.logTxtCtrl = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 200))
        self.logLogTxtCtrl = RedirectText(self.logTxtCtrl)

        self.Bind(wx.EVT_BUTTON, self.chooseFile, self.fileBtn)
        self.Bind(wx.EVT_BUTTON, self.editProfile, self.editProfileBtn)
        self.Bind(wx.EVT_BUTTON, self.skein, self.skeinBtn)
        
        self.Bind(wx.EVT_COMBOBOX, self.profileChange, self.profilesCB)
        
        ch = logging.StreamHandler(self.logLogTxtCtrl)
        ch.setLevel(logging.INFO)
        self.skeinforgeEngine = skeinforge_engine
        self.skeinforgeEngine.logger.addHandler(ch)
                
        self.__set_properties()
        self.__do_layout()            

    def __set_properties(self):
        self.SetTitle("SkeinforgeEngine")

    def __do_layout(self):
        mainSizer = wx.GridBagSizer(hgap=5, vgap=5)
        mainSizer.AddGrowableCol(1, 0)
        mainSizer.AddGrowableRow(2, 0)
        mainSizer.Add(self.fileLbl, pos=(0, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(self.fileTxt, pos=(0, 1), flag=wx.ALL | wx.EXPAND, border=5)
        mainSizer.Add(self.fileBtn, pos=(0, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        
        mainSizer.Add(self.profileLbl, pos=(1, 0), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(self.profilesCB, pos=(1, 1), flag=wx.ALL | wx.EXPAND, border=5)
        mainSizer.Add(self.editProfileBtn, pos=(1, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        
        mainSizer.Add(self.logLbl, pos=(2, 0), flag=wx.ALL | wx.ALIGN_TOP, border=5)
        mainSizer.Add(self.logTxtCtrl, pos=(2, 1), span=wx.GBSpan(1, 2), flag=wx.EXPAND | wx.ALL, border=5)
        
        mainSizer.Add(self.skeinBtn, pos=(3, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        
        self.SetSizer(mainSizer)
        self.SetMinSize((500, 400))
        mainSizer.Fit(self)
        self.Center()
        self.Layout()

    def skein(self, event):
        
        if self.fileTxt.GetValue() == "":
            self.logTxtCtrl.WriteText("No file given.\n")
            return
        
        args = []
        
        profileSelectionIndex = self.profilesCB.GetSelection()
        
        if profileSelectionIndex > 0:
            profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
            profilePath = os.path.join(self.profilesDirectory, profileName)
            args.append("-p")
            args.append(profilePath)
            config.set('runtime', 'last.profile', profileName)
        else:
            config.set('runtime', 'last.profile', '')
        with open("skeinforge_engine_gui.cfg", 'wb') as configfile:
            config.write(configfile)
        
        args.append(self.fileTxt.GetValue().encode())
        
        Thread(target=self.skeinforgeEngine.main, args=[args]).start()

    def chooseFile(self, event):
        if config.get('runtime', 'last.path') != None:
            startFolder = os.path.dirname(config.get('runtime', 'last.path'))
        else:
            startFolder = os.getcwd()
        dlg = wx.FileDialog(self, "Choose a file", startFolder, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                config.set('runtime', 'last.path', path)
                with open("skeinforge_engine_gui.cfg", 'wb') as configfile:
                    config.write(configfile)
                self.fileTxt.SetValue(path)
        dlg.Destroy()
    
    def editProfile(self, event):
        profileSelectionIndex = self.profilesCB.GetSelection()
        if profileSelectionIndex < 1:
            return
        profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
        profilePath = os.path.join(self.profilesDirectory, profileName)
        import webbrowser
        webbrowser.open(profilePath)
    
    def profileChange(self, event):
        self.editProfileBtn.Enable(self.profilesCB.GetSelection() > 0)

class SkeinforgeEngineGui(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        frame_1 = MyFrame(None, -1, "")
        self.SetTopWindow(frame_1)
        frame_1.Show()
        return 1

if __name__ == "__main__":
    config.read("skeinforge_engine_gui.cfg")
    skeinforgeEngineGui = SkeinforgeEngineGui(0)
    skeinforgeEngineGui.MainLoop()
