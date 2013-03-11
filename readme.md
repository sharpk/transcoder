Transcoder

This project consists of a daemon in the form of a python script which monitors for downloaded video and transcodes them using Handbrake.  More specifically it monitors for downloaded video files from uTorrent and for recorded video from NextPVR.

Note: This script has only been tested on Windows and will likely require modification to run correctly on other OSes.

Installation:
Copy transcode_daemon.py to desired location and modify the variables in the CONFIGURATION section of the script (especially update all of the path variables).  Then simply run the script.

Debugging:
After the transcode_daemon is run it shoudl create a file called transcode_daemon.log with logging information.
