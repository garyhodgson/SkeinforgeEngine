# SkeinforgeEngine

A fork of Enrique's [Skeinforge](http://skeinforge.com), taken from ahmetcemturan's [SFACT](https://github.com/ahmetcemturan/SFACT).

## Goals
 * Simplify codebase in order to make the algorithms clearer.
 * Seperate core Skeining functions from GUI.
 * Remove dependency on TKinter.
 * Simplify and consolidate configuration and profiles.
 * Identify performance improvements.

## Caveats
  * Functionality has been removed as part of the simplification process.  For a fully developed modular system with a working GUI please refer to the original Skeinforge or SFACT derivative.
  * Only python 2.7 is supported

## Running
  * The GUI has been stripped out and so the program must be run from the command line. "python ./skeinforge_engine.py test.stl"

## Credit
  * Credit to Enrique and the original contributers in making Skeinforge available, and to Ahmet for his contributions through SFACT.

## License
[GNU Affero General Public License](http://www.gnu.org/licenses/agpl.html)
  