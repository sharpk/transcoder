import os
import glob
import string
import msvcrt
import time
import re
import shutil
import sys
import subprocess
import logging
from xml.dom.minidom import parse

# Config
loglevel = logging.DEBUG
dontDeleteSourceFiles = False
handbrakePath = "C:\\Program Files\\Handbrake"
btDownloadPath = "C:\\Documents and Settings\\Ken\\My Documents\\Downloads"
btInputFileExt = '.*\.avi$|.*\.mkv$|.*\.mp4$|.*\.3gp$'
npvrEnable = True
npvrPath = "C:\\Program Files\NPVR\\"
npvrRecordingPath = "C:\\Documents and Settings\\All Users\\Documents\\My Videos"
xmltvPath = "C:\\Documents and Settings\\All Users\\Application Data\\NPVR\\Scripts\\xmltv.xml"
destinationBasePath = "C:\\media\\video"
outputFileExt = ".m4v"
replacementChar = " "
pollRate = 10	# in minutes
tvFilePatterns = ["[sS][0-9]+[eE][0-9]+", "[0-9]+[xX][0-9]+"]

def initDaemon():
	logging.basicConfig(filename='transcode_daemon.log',level=loglevel)
	
def btMakePrettyFileName(sourceFilePath):
	return string.replace(os.path.splitext(os.path.basename(sourceFilePath))[0], ".", replacementChar)

def btCalcDestinationPath(prettyFileBaseName):
	# TODO try and match filenames that use "0501" instead of "S05E01" as well
	tvFound = False
	destinationFilePath = ""
	for pattern in tvFilePatterns:
		splitArr = re.split(pattern, prettyFileBaseName)
		if len(splitArr) > 1:
			resultingFolderName = string.strip(splitArr[0])
			logging.debug("Found TV folder name: " + resultingFolderName)
			destinationFilePath = os.path.join( destinationBasePath, resultingFolderName)
			if not os.path.isdir(destinationFilePath):
				# TODO make sure that case is ignored when looking for matching directory
				os.mkdir(destinationFilePath)
				logging.debug("Made new directory: " + destinationFilePath)
			destinationFilePath = os.path.join( destinationFilePath, prettyFileBaseName + outputFileExt)
			tvFound = True
			break
	if not tvFound:
		destinationFilePath = os.path.join( destinationBasePath, prettyFileBaseName + outputFileExt)
		logging.debug("Could not calculate TV folder name")
	return destinationFilePath

#returns True if successful, False if there was an error
def ConvertVideoFile(sourceFilePath, destinationFilePath):
	# don't start Handbrake if NPVR is recording
	if IsNPVRBusy():
		return True
	# Call Handbrake
	handbrakeCmdLine = "HandbrakeCLI.exe -i \"" + sourceFilePath + "\" -o \"" + destinationFilePath + "\" --preset=\"Normal\""
	logging.debug("Handbrake Command Line: " + handbrakeCmdLine)
	os.chdir(handbrakePath)
	os.system(handbrakeCmdLine)
	# cleanup source file
	if os.path.exists(destinationFilePath):
		if dontDeleteSourceFiles:
			logging.debug("Not deleting source file since dontDeleteSourceFiles == True")
			return True
		else:
			logging.debug("Deleting source file")
			os.remove(sourceFilePath)
			return True
	else:
		logging.error("Error: file " + destinationFilePath + " does not exist. Handbrake probably failed.")
		return False
	
def ScanForBtFiles():
	os.chdir(btDownloadPath)	
	for f in os.listdir('.'):
		if re.match(btInputFileExt, f):
			sourceFilePath = os.path.join(btDownloadPath, f)
			logging.debug("Found a file: " + sourceFilePath)
			# replace dots so it appears correctly on Roku
			prettyFileBaseName = btMakePrettyFileName(sourceFilePath)
			# if it's a TV episode then calculate a show folder, create the folder if necessary, and calc final path
			destinationFilePath = btCalcDestinationPath(prettyFileBaseName)
			logging.debug("Prettified destination path: " + destinationFilePath)
			# Use Handbrake to do the transcode
			ConvertVideoFile(sourceFilePath, destinationFilePath)

def IsNPVRBusy():
	if not npvrEnable:
		return False
	os.chdir(npvrPath)
	p = subprocess.Popen('NScriptHelper.exe -isinuse', shell=True, stdout=subprocess.PIPE)
	retVal = p.stdout.read()
	logging.debug("NScriptHelper -isinuse output: " + retVal)
	if retVal.find('NOT RECORDING') >= 0:
		return False
	else:
		return True

def DeleteNPVRFileFromDB(sourceFilePath):
	os.chdir(npvrPath)
	logging.debug("Removing file from NPVR DB: " + sourceFilePath)
	subprocess.call('NScriptHelper.exe -delete ' + sourceFilePath)

def npvrCalculateDestinationPath(sourceFile):
	# sample NPVR output filename: 'Woodsmith Shop_20130303_09000930.ts'
	# extract show name, date, start time, and end time
	endtime = sourceFile[-7:]
	endtime = endtime[:-3]
	logging.debug("endtime: " + endtime)
	starttime = sourceFile[-11:]
	starttime = starttime[:-7]
	logging.debug("starttime: " + starttime)
	recorddate = sourceFile[-20:]
	recorddate = recorddate[:-12]
	logging.debug("date: " + recorddate)
	showname = sourceFile[:-21]
	logging.debug("show name: " + showname)
	# load up the xmltv file; reload it every time since it changes every 24 hours
	dom = parse(xmltvPath)
	for program in dom.getElementsByTagName("programme"):
		tmpShowname = program.getElementsByTagName("title")[0].childNodes[0].data
		tmpRecorddate = program.attributes["start"].value[:8]
		tmpStarttime = program.attributes["start"].value[8:12]
		tmpEndtime = program.attributes["stop"].value[8:12]
		if tmpShowname == showname and tmpRecorddate == recorddate and tmpStarttime == starttime and tmpEndtime == endtime:
			epnum = program.getElementsByTagName("episode-num")[0].childNodes[0].data
			subtitle = tmpShowName = program.getElementsByTagName("sub-title")[0].childNodes[0].data
			destinationDir = os.path.join(destinationBasePath, showname)
			if not os.path.exists(destinationDir):
				os.mkdir(destinationDir)
			return os.path.join(destinationDir, showname + " - " + epnum + " - " + subtitle + outputFileExt)
	# xmltv parsing probably failed; just use original filename
	logging.error("XMLTV file parsing failed; calculating alternate file name")
	destinationDir = os.path.join(destinationBasePath, showname)
	if not os.path.exists(destinationDir):
		os.mkdir(destinationDir)
	return os.path.join(destinationDir, os.path.splitext(sourceFile)[0] + outputFileExt) 

def ScanForNPVRFiles():
	if not npvrEnable:
		return
	if IsNPVRBusy():
		return
	os.chdir(npvrRecordingPath)
	# NPVR puts shows in their own folders
	for d in os.listdir('.'):
		if os.path.isdir(d):
			for f in os.listdir(d):
				if re.match('.*\.done$', f):
					doneFilePath = os.path.join(npvrRecordingPath, d, f)
					logging.debug("Found a .done file: " + doneFilePath)
					# get rid of *.done to get actual movie file path
					sourceFile = os.path.splitext(f)[0]
					logging.debug("Found a video file: " + sourceFile)
					# calculate dest file path
					destinationFilePath = npvrCalculateDestinationPath(sourceFile)
					logging.debug("Calculated destination path: " + destinationFilePath)
					# TODO: run comskip and comclean(2|3) to remove commercials
					# run handbrake to convert file (and delete source)
					sourceFilePath = os.path.join(npvrRecordingPath, d, sourceFile)
					retVal = ConvertVideoFile(sourceFilePath, destinationFilePath)
					# delete .done file
					if retVal:
						logging.debug("Removing .done file: " + doneFilePath)
						os.remove(doneFilePath)
					# do additional NextPVR cleanup?  like remove entry from NPVR DB
					if not dontDeleteSourceFiles:
						DeleteNPVRFileFromDB(os.path.join(npvrRecordingPath, sourceFile))
	return

def SanityCheck():
	# check that directories exist
	if not os.path.exists(handbrakePath):
		logging.error("Handbrake path does not exist: " + handbrakePath)
		return False
	if not os.path.exists(btDownloadPath):
		logging.error("bittorrent download path does not exist: " + btDownloadPath)
		return False
	if not os.path.exists(destinationBasePath):
		logging.error("Destination path does not exist: " + destinationBasePath)
		return False
	if npvrEnable:
		if not os.path.exists(npvrPath):
			logging.error("NextPVR path does not exist: " + npvrPath)
			return False
		if not os.path.exists(npvrRecordingPath):
			logging.error("NextPVR recording path does not exist: " + npvrRecordingPath)
			return False
		if not os.path.exists(xmltvPath):
			logging.error("XMLTV file doesn't exist: " + xmltvPath)
			return False
		
	# TODO: check that PostProcessing.bat is installed and contains code to create *.done files
	
	# TODO: check that uTorrent is set to use .!ut extension until download is complete, or that it uses a separate "completed download" directory
	
	return True

if __name__ == "__main__":
	print "Starting transcode daemon, hit Ctrl-C to exit"
	initDaemon()
	logging.debug('Starting transcode daemon')
	sane = SanityCheck()
	if not sane:
		sys.exit()
	while True:
		try:
			ScanForBtFiles()
			ScanForNPVRFiles()
			# Add watchdog function to restart NPVR service and possibly uTorrent server
			time.sleep(pollRate*60)
		except KeyboardInterrupt:
			print "Received Ctrl-C! Exiting..."
			break

