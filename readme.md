# SkeinforgeEngine

A fork of Enrique's [Skeinforge](http://skeinforge.com), taken from ahmetcemturan's [SFACT](https://github.com/ahmetcemturan/SFACT).  **This is currently a work in progress, see the caveats below**

## Goals
 * Simplify codebase in order to make the algorithms clearer.
 * Seperate core Skeining functions from GUI.
 * Remove dependency on TKinter.
 * Simplify and consolidate configuration and profiles.
 * Identify performance improvements.

## Caveats
  * Currently a work in progress - no guarantee the program will work nor produce identical results to Skeinforge/SFACT.
  * Functionality has been removed as part of the simplification process.  For a fully developed modular system with a working GUI please refer to the original Skeinforge or SFACT derivative.
    * The following plugins are currently available: carve,bottom,preface,inset,fill,multiply,speed,raft,stretch,comb,cool,dimension,export
  * Only python 2.7 is supported.
  * No GUI.
  * Supports only stepper extruders and volumetric extrusion.
  * Currently the retraction is hardcoded to 0.7mm until I work out how to get the next coordinate from the dat structure
  * Fill option extrusion.sequence.print.order are currently inactive

## Running
  * python ./skeinforge_engine.py [-h] [-c config] [-p profile] file

## Configuration
  * Configuration is divided into two files: skeinforge_engine.cfg for core program settings and a profile for the runtime plugin settings.
  * If no profile is given on the command line then a default profile is used: fallback.profile.  The default profile can be specified in skeinforge_engine.cfg.
  * Profile settings are cummulative, that is the default profile is always read first, and then the given profile.  Any settings not defined in the given profile will be picked up from the default.


## Credit
  * Credit to Enrique and the original contributers in making Skeinforge available, and to Ahmet for his contributions through SFACT.

## License
[GNU Affero General Public License](http://www.gnu.org/licenses/agpl.html)
  