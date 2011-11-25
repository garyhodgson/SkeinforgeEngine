#!/usr/bin/env python

from threading import Thread
import ConfigParser
import logging
import os
import skeinforge_engine
import sys
import shutil
import StringIO
try:
    import wx
except:
    print "WX is not installed. This program requires WX to run."
    raise

import printrun_utilities.gviz as gviz
import printrun_utilities.SimpleEditor as SimpleEditor

guiConfig = ConfigParser.ConfigParser(allow_no_value=True)
guiConfigFilename = "skeinforge_engine_gui.cfg"
runtimeConfig = ConfigParser.ConfigParser(allow_no_value=True)
runtimeConfigFilename = "skeinforge_engine_gui.runtime"
engineConfig = ConfigParser.ConfigParser(allow_no_value=True)
engineConfigFilename = "skeinforge_engine.cfg"

class GuiFrame(wx.Frame):
    def __init__(self, *args, **kwds):
        kwds["style"] = wx.DEFAULT_DIALOG_STYLE | wx.MAXIMIZE_BOX | wx.MINIMIZE_BOX | wx.RESIZE_BORDER
        wx.Frame.__init__(self, *args, **kwds)
        self.SetIcon(wx.Icon("SkeinforgeEngine.ico", wx.BITMAP_TYPE_ICO))
        self.SetBackgroundColour(wx.WHITE)
        self.dialogs = []
        self.lastProfileName = runtimeConfig.get('runtime', 'last.profile')
        self.lastShowGcode = runtimeConfig.getboolean('runtime', 'last.show.gcode')
        self.lastFiles = runtimeConfig.get('runtime', 'last.files').split(',')
        self.openGcodeFilesVisualisation = guiConfig.getboolean('general', 'open.gcode.files.visualisation')
        self.lastProfileIndex = 0
        self.fileHistoryConfig = wx.Config("skeinforge_engine_gui", style=wx.CONFIG_USE_LOCAL_FILE)
        self.fileHistory = wx.FileHistory()
        self.fileHistory.Load(self.fileHistoryConfig)

        lastPath = runtimeConfig.get('runtime', 'last.path')
        self.fileTxt = wx.TextCtrl(self, -1, lastPath, size=(300, -1))
        
        self.logTxtCtrl = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL, size=(-1, 200))
        
        self.profilesDirectory = guiConfig.get('general', 'profiles.location')
        
        self.profilesCB = wx.ComboBox(self, -1, size=(300, -1), style=wx.CB_READONLY)
        self.profilesCB.SetSelection(self.lastProfileIndex)
        
        if not os.path.exists(self.profilesDirectory):
            self.logTxtCtrl.WriteText("Invalid profiles directory: %s" % self.profilesDirectory)
        else:
            self.updateProfileList()
                           
        self.profileLbl = wx.StaticText(self, -1, "Profile", size=(-1, -1))
        self.fileLbl = wx.StaticText(self, -1, "File", size=(-1, -1))
        self.logLbl = wx.StaticText(self, -1, "Log", size=(-1, -1))        
        
        self.fileBtn = wx.Button(self, -1, "&Open...", size=(100, -1))
        self.skeinBtn = wx.Button(self, -1, "&Skein", size=(100, -1))
        self.editProfileBtn = wx.Button(self, -1, "Edit...", size=(100, -1))
                
        self.editProfileBtn.Enable(self.profilesCB.GetSelection() > 0)
        
        self.showGcodeCheckBox = wx.CheckBox(self, -1, 'Show Gcode', (10, 10))
        self.showGcodeCheckBox.SetValue(self.lastShowGcode)
        
        self.Bind(wx.EVT_BUTTON, self.onOpenFile, self.fileBtn)
        self.Bind(wx.EVT_BUTTON, self.onEditProfile, self.editProfileBtn)
        self.Bind(wx.EVT_BUTTON, self.onSkein, self.skeinBtn)
        
        self.Bind(wx.EVT_COMBOBOX, self.onProfileChange, self.profilesCB)
        self.Bind(wx.EVT_CHECKBOX, self.onShowGcodeChange, self.showGcodeCheckBox)
        
        self.Bind(wx.EVT_CLOSE, self.onExit)
        
        skein_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.onSkein, id=skein_id)
        
        openFile_id = wx.NewId()
        self.Bind(wx.EVT_MENU, self.onOpenFile, id=openFile_id)
        
        self.accel_tbl = wx.AcceleratorTable([(wx.ACCEL_CTRL, ord('S'), skein_id), (wx.ACCEL_CTRL, ord('O'), openFile_id)])
        
        self.SetAcceleratorTable(self.accel_tbl)
        
        self.skeinforgeEngine = skeinforge_engine
        logHandler = WxLog(self.logTxtCtrl)
        logHandler.setLevel(logging.getLevelName(guiConfig.get('general', 'skeinforge.engine.log.handler.level')))
        self.skeinforgeEngine.logger.addHandler(logHandler)
        
        self.prepMenu()
        
        self.__set_properties()
        self.__do_layout()            

    def updateProfileList(self):
        self.profilesCB.Clear()
        self.profilesCB.Append("None (Default)")
        index = 1
        self.lastProfileIndex = None
        for f in os.listdir(self.profilesDirectory):
            profilePath = os.path.join(self.profilesDirectory, f)
            if os.path.isfile(profilePath):
                if f == self.lastProfileName:
                    self.lastProfileIndex = index 
                self.profilesCB.Append(f)
                index += 1      
        if self.lastProfileIndex == None:
            self.lastProfileIndex = 0
        self.profilesCB.SetSelection(self.lastProfileIndex)
                    
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
        
        
        mainSizer.Add(self.showGcodeCheckBox, pos=(3, 1), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
        mainSizer.Add(self.skeinBtn, pos=(3, 2), flag=wx.ALL | wx.ALIGN_CENTER_VERTICAL, border=5)
                
        self.SetSizer(mainSizer)
        self.SetMinSize((500, 400))
        mainSizer.Fit(self)
        self.Center()
        self.Layout()
        
    def prepMenu(self):
        self.menustrip = wx.MenuBar()

        fileMenu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.onOpenFile, fileMenu.Append(-1, "&Open...", " Opens file"))
        self.Bind(wx.EVT_MENU, self.onClearOutput, fileMenu.Append(-1, "Clear log", " Clear log"))
        self.Bind(wx.EVT_MENU, self.onExit, fileMenu.Append(wx.ID_EXIT, "E&xit", " Closes the Window"))
        fileMenu.AppendSeparator()
        recent = wx.Menu()
        self.fileHistory.UseMenu(recent)
        self.fileHistory.AddFilesToMenu()
        fileMenu.AppendMenu(wx.ID_ANY, "&Recent Files", recent)
        self.Bind(wx.EVT_MENU_RANGE, self.onFileHistory, id=wx.ID_FILE1, id2=wx.ID_FILE9)
        
        self.menustrip.Append(fileMenu, "&File")

        profilesMenu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.onEditProfile, profilesMenu.Append(-1, "&Edit...", " Edit currently selected profile"))
        self.Bind(wx.EVT_MENU, self.onCopyProfile, profilesMenu.Append(-1, "&Copy", " Make a new copy of the currently selected profile"))
        self.Bind(wx.EVT_MENU, self.onRefreshProfilesList, profilesMenu.Append(-1, "&Refresh", " Refresh list of profiles"))
        self.Bind(wx.EVT_MENU, self.onViewEffectiveProfile, profilesMenu.Append(-1, "&View effective profile", " View the complete profile the engine would use"))
        self.Bind(wx.EVT_MENU, self.onCopyEffectiveProfile, profilesMenu.Append(-1, "Copy effective profile", " Make a new copy of the currently effective profile"))
        self.menustrip.Append(profilesMenu, "&Profiles")
        
        configMenu = wx.Menu()
        self.Bind(wx.EVT_MENU, self.onEditEngineConfig, configMenu.Append(-1, "&Edit skeinforge_engine.cfg...", " Edit engine config"))
        self.Bind(wx.EVT_MENU, self.onEditEngineGuiConfig, configMenu.Append(-1, "&Edit skeinforge_engine_gui.cfg...", " Edit engine gui config"))
        self.menustrip.Append(configMenu, "&Config")

        self.SetMenuBar(self.menustrip)

    def onFileHistory(self, event):
        fileNum = event.GetId() - wx.ID_FILE1
        path = self.fileHistory.GetHistoryFile(fileNum)
        self.fileHistory.AddFileToHistory(path)  # move up the list
        self.openFile(path)
        
        
    def onViewEffectiveProfile(self, event):
        se = SimpleEditor("Effective Profile", self.getEffectiveProfileString(self.getEffectiveProfile()).getvalue(), None, True)
        self.dialogs.append(se)
    
    def getEffectiveProfileString(self, effectiveConfig):        
        effectiveConfigString = StringIO.StringIO()
        for section in effectiveConfig.sections():
            effectiveConfigString.write("[%s]\n" % section)
            for option in effectiveConfig.options(section):
                value = effectiveConfig.get(section, option) 
                effectiveConfigString.write("%s=%s\n" % (option, value))
            effectiveConfigString.write("\n")
        return effectiveConfigString
            
    def getEffectiveProfile(self):
        defaultProfile = engineConfig.get('general', 'default.profile')
        effectiveConfig = ConfigParser.ConfigParser(allow_no_value=True)
        effectiveConfig.read(defaultProfile)
        
        profileSelectionIndex = self.profilesCB.GetSelection()
        if profileSelectionIndex > 0:
            profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
            profilePath = os.path.join(self.profilesDirectory, profileName)
            effectiveConfig.read(profilePath)
        return effectiveConfig
    
    def onCopyEffectiveProfile(self, event):
        profileSelectionIndex = self.profilesCB.GetSelection()
        if profileSelectionIndex > 0:
            profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
        else:
            profileName = "default.profile"
        dlg = wx.TextEntryDialog(self, 'New profile name:', 'Copy Effective Profile', "%s.copy" % profileName)        
        txtCtrl = dlg.FindWindowById(3000)
        txtCtrl.Validator = NewFileNameValidator(self.profilesDirectory, dlg) 
        if dlg.ShowModal() == wx.ID_OK:
            newProfileName = txtCtrl.GetValue()
            newProfilePath = os.path.join(self.profilesDirectory, newProfileName)
            try:
                fd = os.open(newProfilePath, os.O_RDWR | os.O_CREAT)
                f = os.fdopen(fd, "w+")
                effectiveProfile = self.getEffectiveProfile()
                effectiveProfile.set('profile', 'name', newProfileName)
                f.write (self.getEffectiveProfileString(effectiveProfile).getvalue())
                f.close()
                self.lastProfileName = newProfileName
                self.updateProfileList()
                self.GetEventHandler().ProcessEvent(wx.PyCommandEvent(wx.EVT_COMBOBOX.typeId, self.profilesCB.GetId()))                
            except (IOError, os.error), why:
                msgDlg = wx.MessageDialog(dlg, 'Unable to copy effective profile: %s.' % str(why), 'Error', wx.OK | wx.ICON_ERROR)
                msgDlg.ShowModal()
                msgDlg.Destroy()
        dlg.Destroy()
        
    def onEditEngineGuiConfig(self, event):
        self.editFile('skeinforge_engine_gui.cfg') 
        
    def onEditEngineConfig(self, event):
        self.editFile('skeinforge_engine.cfg')
    
    def onEditProfile(self, event):
        '''Opens the profile for editing.'''
        profileSelectionIndex = self.profilesCB.GetSelection()
        if profileSelectionIndex < 1:
            return
        profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
        profilePath = os.path.join(self.profilesDirectory, profileName)
        self.editFile(profilePath)
        
    def editFile(self, filePath):
        f2 = open(filePath)
        def saveFileCallback(text):
            f = open(filePath, 'w+')
            if len(text.strip()) == 0:
                return
            f.write(text)
            f.close()
            guiConfig.read(guiConfigFilename)
        se = SimpleEditor(os.path.basename(filePath), f2.read(), saveFileCallback)
        self.dialogs.append(se)
        
    def onCopyProfile(self, event):
        profileSelectionIndex = self.profilesCB.GetSelection()
        if profileSelectionIndex < 1:
            return
        profileName = self.profilesCB.GetString(profileSelectionIndex).encode()
        profilePath = os.path.join(self.profilesDirectory, profileName)
        dlg = wx.TextEntryDialog(self, 'New profile name:', 'Copy Profile', "%s.copy" % profileName)
        
        txtCtrl = dlg.FindWindowById(3000)
        txtCtrl.Validator = NewFileNameValidator(self.profilesDirectory, dlg) 
        if dlg.ShowModal() == wx.ID_OK:
            newProfileName = txtCtrl.GetValue()
            newProfilePath = os.path.join(self.profilesDirectory, newProfileName)
            try:
                shutil.copyfile(profilePath, newProfilePath)
                self.lastProfileName = newProfileName
                self.updateProfileList()
                self.GetEventHandler().ProcessEvent(wx.PyCommandEvent(wx.EVT_COMBOBOX.typeId, self.profilesCB.GetId()))                
            except (IOError, os.error), why:
                msgDlg = wx.MessageDialog(dlg, 'Unable to copy profile: %s.' % str(why), 'Error', wx.OK | wx.ICON_ERROR)
                msgDlg.ShowModal()
                msgDlg.Destroy()
        dlg.Destroy()
    
    def onExit(self, event):
        for d in self.dialogs:
            try:
                d.Destroy()
            except:
                pass
        self.Destroy()
        
    def onRefreshProfilesList(self, event):
        self.updateProfileList()
        self.GetEventHandler().ProcessEvent(wx.PyCommandEvent(wx.EVT_COMBOBOX.typeId, self.profilesCB.GetId()))
        
    def onClearOutput(self, event):
        self.logTxtCtrl.Clear()
    
    def onSkein(self, event):
        '''Calls skeinforge_engine and optionally shows the created gcode afterwards.'''
        
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
        
        if guiConfig.getboolean('general', 'use.pypy'):
            self.pypySkein(args)
        else:
            self.skein(args)
            
            
    def pypySkein(self, args):
        '''Calls engine using system in order to use pypy.'''
        pypyLocation = guiConfig.get('general', 'pypy.location')
        
        if pypyLocation == None or pypyLocation == '':
            self.logTxtCtrl.WriteText("Pypy location not defined in %s.\n" % guiConfigFilename)
            return
        
        args.append("\"%s\"" % self.fileTxt.GetValue().encode())
        
        self.logTxtCtrl.WriteText("Skeining...\nUsing PyPy: log output is delayed until skeining is finished\n")
        
        import subprocess
        p=subprocess.Popen("%s skeinforge_engine.py %s" % (pypyLocation, ' '.join(args)), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,shell=False)
        p.wait()
        self.logTxtCtrl.write(p.communicate()[0].replace('\r',''))
        self.logTxtCtrl.WriteText("Done!\n\n")
    
    def skein(self, args):
        '''Calls the engine to skein a file.'''
        
        args.append(self.fileTxt.GetValue().encode())
        
        slicedModel = self.skeinforgeEngine.main(args)
        
        if slicedModel != None and self.showGcodeCheckBox.GetValue():
            if slicedModel.runtimeParameters == None or slicedModel.runtimeParameters.outputFilename == None:
                self.logTxtCtrl.WriteText("Unable to find output filename in sliced model. Cannot preview Gcode.\n")
            else:
                self.showGcodeVisualisation(slicedModel.runtimeParameters.outputFilename)
                
        self.logTxtCtrl.WriteText("Done!\n\n")

    def showGcodeVisualisation(self, filename):
        gwindow = gviz.window([], title=os.path.basename(filename))
        self.dialogs.append(gwindow)
        f = open(filename)
        for i in f:
            gwindow.p.addgcode(i)
        gwindow.Show()

    def onOpenFile(self, event):
        '''Shows the file choice dialog.'''
        if runtimeConfig.get('runtime', 'last.path') != None:
            startFolder = os.path.dirname(runtimeConfig.get('runtime', 'last.path'))
        else:
            startFolder = os.getcwd()
        dlg = wx.FileDialog(self, "Choose a file", startFolder, "", "*.*", wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
                path = dlg.GetPath()
                self.fileHistory.AddFileToHistory(path)
                self.fileHistory.Save(self.fileHistoryConfig)
                self.fileHistoryConfig.Flush()
                
                self.openFile(path)
        dlg.Destroy()
        
    def openFile(self, path):
        if path.endswith('.gcode') and self.openGcodeFilesVisualisation:
            self.showGcodeVisualisation(path)
        else:
            self.saveRuntimeParameter('last.path', path)
            self.fileTxt.SetValue(path)
            
    def onProfileChange(self, event):
        self.lastProfileIndex = self.profilesCB.GetSelection()
        self.editProfileBtn.Enable(self.lastProfileIndex > 0)
        self.lastProfileName = self.profilesCB.GetString(self.lastProfileIndex).encode()
        if self.lastProfileIndex > 0:
            self.saveRuntimeParameter('last.profile', self.lastProfileName)
        else:
            self.saveRuntimeParameter('last.profile', '')           

    def onShowGcodeChange(self, event):
        self.saveRuntimeParameter('last.show.gcode', self.showGcodeCheckBox.GetValue())

    def saveRuntimeParameter(self, option, value):
        '''Saves the options in the cfg file under the [runtime] section.'''
        runtimeConfig.set('runtime', option, value)
        with open(runtimeConfigFilename, 'wb') as configfile:
            runtimeConfig.write(configfile)

class WxLog(logging.Handler):
    def __init__(self, ctrl):
       logging.Handler.__init__(self)
       self.ctrl = ctrl
    def emit(self, record):
       self.ctrl.AppendText(self.format(record) + "\n")
       self.ctrl.Update()
           
class NewFileNameValidator(wx.PyValidator): 
    def __init__(self, directory, parentDialog): 
        wx.PyValidator.__init__(self)
        self.directory = directory
        self.parentDialog = parentDialog
    
    def Clone(self): 
        '''Every validator must implement Clone() method!''' 
        return NewFileNameValidator(self.directory, self.parentDialog) 
    
    def Validate(self, win): 
        txtCtrl = self.Window       
        newFilename = txtCtrl.GetValue()
        newPath = os.path.join(self.directory, newFilename)        
        if os.path.exists(newPath):
            msgDlg = wx.MessageDialog(self.parentDialog, 'File already exists: %s' % newPath, 'Error', wx.OK | wx.ICON_ERROR)
            msgDlg.ShowModal()
            msgDlg.Destroy()
            return False
        else:
            return True
            
    def TransferToWindow(self): 
        return True    
    
    def TransferFromWindow(self): 
        return True
    
class SkeinforgeEngineGui(wx.App):
    def OnInit(self):
        wx.InitAllImageHandlers()
        frame_1 = GuiFrame(None, -1, "")
        self.SetTopWindow(frame_1)
        frame_1.Show()
        return 1

if __name__ == "__main__":
    guiConfig.read(guiConfigFilename)
    runtimeConfig.read(runtimeConfigFilename)
    engineConfig.read(engineConfigFilename)
    skeinforgeEngineGui = SkeinforgeEngineGui(0)
    skeinforgeEngineGui.MainLoop()
