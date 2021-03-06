# Transcode daemon
# This script monitors for downloaded video files in uTorrent or recorded video
# from NextPVR and transcodes the video files using Handbrake
# Copyright (c) 2013 Ken Sharp
# License: http://opensource.org/licenses/mit-license.php

import os
import glob
import string
import time
import re
import shutil
import sys
import subprocess
import logging
from xml.dom.minidom import parse

# CONFIGURATION
loglevel = logging.DEBUG
forceSD = True
dontDeleteSourceFiles = False
exitOnException = True
convertVideoFiles = False
maintenanceTime = 4 # hour of the day (in 24 hour format) to restart troublesome processes
if os.name == 'nt':
	handbrakePath = "C:\\Program Files\\Handbrake"
	handbrakeBin = "HandbrakeCLI.exe"
	uTorrentEnable = True
	uTorrentPath = "C:\\Program Files\\uTorrent"
	uTorrentBin = "utorrent.exe"
	btDownloadPath = "C:\\Documents and Settings\\Ken\\My Documents\\Downloads"
	npvrEnable = True
	npvrPath = "C:\\Program Files\NPVR\\"
	npvrRecordingPath = "C:\\Documents and Settings\\All Users\\Documents\\My Videos"
	xmltvPath = "C:\\Documents and Settings\\All Users\\Application Data\\NPVR\\Scripts\\xmltv.xml"
	destinationBasePath = "C:\\media\\video"
elif os.name == 'posix':
	uTorrentEnable = False
	npvrEnable = False
	handbrakePath = "/usr/bin/"
	handbrakeBin = "HandBrakeCLI"
	delugeEnable = True
	btDownloadPath = "/home/ksharp/Downloads/BTComplete"
	xmltvPath = "/home/ksharp/xmltv.xml"
	destinationBasePath = "/mnt/datadump/media/video/TV"
btInputFileExt = '.*\.avi$|.*\.mkv$|.*\.mp4$|.*\.3gp$'
outputFileExt = ".m4v"
replacementChar = " "
pollRate = 10	# in minutes
tvFilePatterns = ["[sS][0-9]+[eE][0-9]+", "[0-9]+[xX][0-9]+"]

def initDaemon():
	logging.basicConfig(filename='transcode_daemon.log', level=loglevel, format='%(asctime)s %(funcName)s:%(lineno)d %(levelname)s:%(message)s')
	
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
			destinationFilePath = os.path.join(destinationBasePath, resultingFolderName)
			dirExists = False
			for d in os.listdir(destinationBasePath):
				if os.path.isdir(os.path.join(destinationBasePath, d)):
					if d.lower() == resultingFolderName.lower():
						dirExists = True
						destinationFilePath = os.path.join(destinationBasePath, d)
						logging.debug("Found existing directory: " + destinationFilePath)
						break
			if not dirExists:
				os.mkdir(destinationFilePath)
				logging.debug("Made new directory: " + destinationFilePath)
			destinationFilePath = os.path.join(destinationFilePath, prettyFileBaseName)
			tvFound = True
			break
	if not tvFound:
		destinationFilePath = os.path.join(destinationBasePath, prettyFileBaseName)
		logging.debug("Could not calculate TV folder name")
	return destinationFilePath

def DeleteSourceFile(sourcePath):
	if dontDeleteSourceFiles:
		logging.debug("Not deleting source file since dontDeleteSourceFiles == True")
		return True
	else:
		logging.debug("Deleting source file")
		try:
			os.remove(sourcePath)
		except Exception as e:
			# log the file delete failure and continue processing other files
			logging.exception(e)
		return True

#returns True if successful, False if there was an error
def ConvertVideoFile(sourceFilePath, destinationFilePath):
	# don't start Handbrake if NPVR is recording
	if IsNPVRBusy():
		return True
	# make sure we haven't already transcoded this file
	if os.path.exists(destinationFilePath) and os.path.getsize(destinationFilePath) > (1024 * 1024 * 20):
		logging.debug('File "' + destinationFilePath + '" already exists; skipping transcode')
	else:
		# Call Handbrake
		handbrakeCmdLine = handbrakeBin + " -i \"" + sourceFilePath + "\" -o \"" + destinationFilePath + "\" --preset=\"Normal\" --decomb"
		if forceSD:
			# Force standard definition resolution
			handbrakeCmdLine += " --loose-anamorphic --maxHeight 480"
		# Lower priority of handbrake process
		if os.name == 'nt':
			handbrakeCmdLine = "start /wait /low " + handbrakeCmdLine
		elif os.name == 'posix':
			handbrakeCmdLine = "nice -n 5 " + handbrakeCmdLine
		logging.debug("Handbrake Command Line: " + handbrakeCmdLine)
		os.chdir(handbrakePath)
		subprocess.call(handbrakeCmdLine, shell=True)
	# cleanup source file
	if os.path.exists(destinationFilePath):
		DeleteSourceFile(sourceFilePath)
		return True
	else:
		logging.error("Error: file " + destinationFilePath + " does not exist. Handbrake probably failed.")
		return False

def CopyVideoFile(sourceFilePath, destinationFilePath):
	logging.debug("Copying source file to destination")
	shutil.copyfile(sourceFilePath, destinationFilePath)
	DeleteSourceFile(sourceFilePath)
	return True

def BtProcessFile(sourceFilePath):
	if re.match(btInputFileExt, os.path.basename(sourceFilePath)):
		logging.debug("Found a file: " + sourceFilePath)
		# replace dots so it appears correctly on Roku
		prettyFileBaseName = btMakePrettyFileName(sourceFilePath)
		if convertVideoFiles:
			fileExt = outputFileExt
		else:
			fileExt = os.path.splitext(sourceFilePath)[1]
		# if it's a TV episode then calculate a show folder, create the folder if necessary, and calc final path
		destinationFilePath = btCalcDestinationPath(prettyFileBaseName)
		destinationFilePath = destinationFilePath + fileExt
		logging.debug("Prettified destination path: " + destinationFilePath)
		# Use Handbrake to do the transcode
		if convertVideoFiles:
			ConvertVideoFile(sourceFilePath, destinationFilePath)
		else:
			CopyVideoFile(sourceFilePath, destinationFilePath)
		#TODO: cleanup subdirs in btDownloadPath

def ScanForBtFiles(d):
	for f in os.listdir(d):
		fullpath = os.path.join(d,f)
		if os.path.isfile(fullpath):
			BtProcessFile(fullpath)
		elif os.path.isdir(fullpath):
			# recurse into subdir
			logging.debug("ScanForBtFiles: Recursing into subdir: " + f)
			ScanForBtFiles(fullpath)

def IsNPVRBusy():
	if not npvrEnable:
		return False
	os.chdir(npvrPath)
	p = subprocess.Popen('NScriptHelper.exe -isinuse', shell=True, stdout=subprocess.PIPE)
	retVal = p.stdout.read()
	#logging.debug("NScriptHelper -isinuse output: " + retVal.strip())
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
	try:
		# load up the xmltv file; reload it every time since it changes every 24 hours
		# TODO: sanity check to make sure that expected channels are present and that the xmltv file isn't otherwise invalid
		dom = parse(xmltvPath)
		for program in dom.getElementsByTagName("programme"):
			tmpShowname = program.getElementsByTagName("title")[0].childNodes[0].data
			tmpShowname = tmpShowname.replace("'","")  #Remove characters that won't be present in the file name
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
	except Exception as e:
		logging.exception(e)
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
					if convertVideoFiles:
						retVal = ConvertVideoFile(sourceFilePath, destinationFilePath)
					else:
						retVal = CopyVideoFile(sourceFilePath, destinationFilePath)
					# delete .done file
					if retVal:
						logging.debug("Removing .done file: " + doneFilePath)
						os.remove(doneFilePath)
					# Remove file from NPVR DB
					if not dontDeleteSourceFiles:
						DeleteNPVRFileFromDB(os.path.join(npvrRecordingPath, sourceFile))
	return

def SanityCheck():
	# check that directories exist
	if not os.path.exists(os.path.join(handbrakePath, handbrakeBin)):
		logging.error("Handbrake path does not exist: " + handbrakePath)
		return False
	if not os.access(os.path.join(handbrakePath, handbrakeBin), os.X_OK):
		logging.error("Handbrake binary is not executable: " + os.path.join(handbrakePath, handbrakeBin))
		return False
	if not os.path.exists(btDownloadPath):
		logging.error("bittorrent download path does not exist: " + btDownloadPath)
		return False
	if not os.access(btDownloadPath, os.R_OK):
		logging.error("Current user does not have read permissions on bittorrent download path: " + btDownloadPath)
		return False		
	if not os.path.exists(destinationBasePath):
		logging.error("Destination path does not exist: " + destinationBasePath)
		return False
	if not os.access(destinationBasePath, os.W_OK):
		logging.error("Current user does not have write permissions on destination path: " + destinationBasePath)
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

class Watchdog( object ):
	def __init__(self, restartTime):
		self.lastCheckedDay = time.localtime(time.time()).tm_yday
		self.restartTime = restartTime
	
	def check(self):
		currentTime = time.localtime(time.time())
		if currentTime.tm_hour >= self.restartTime and currentTime.tm_yday != self.lastCheckedDay:
			logging.debug("Start watchdog maintenance time")
			# restart NextPVR since it sometimes gets in a bad state
			self.restartNPVR()
			# restart uTorrent also
			self.restartUTorrent()
			self.lastCheckedDay = currentTime.tm_yday
	
	def restartNPVR(self):
		if npvrEnable:
			logging.debug("Stopping NPVR Recording Service")
			p = subprocess.Popen('net stop "NPVR Recording Service"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			retVal = p.stdout.read()
			if retVal.find('successfully') < 0:
				logging.error("NPVR service stop failed")
				logging.error("net stop output: " + retVal.strip())
			logging.debug("Restarting NPVR Recording Service")
			p = subprocess.Popen('net start "NPVR Recording Service"', shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
			retVal = p.stdout.read()
			if retVal.find('successfully') < 0:
				logging.error("NPVR service start failed")
				logging.error("net start output: " + retVal.strip())
			
	def restartUTorrent(self):
		if uTorrentEnable:
			if os.path.exists(os.path.join(os.environ['WINDIR'], 'System32', 'taskkill.exe')):
				options = [ '/im', '/f /im' ]
				for op in options:
					killCmd = 'taskkill ' + op + ' ' + uTorrentBin
					logging.debug("Killing uTorrent cmd line: " + killCmd)
					p = subprocess.Popen(killCmd, shell=True, stdout=subprocess.PIPE)
					retVal = p.stdout.read()
					logging.debug("Killing uTorrent output: " + retVal.strip())
					if retVal.find('SUCCESS') >= 0:
						os.chdir(uTorrentPath)
						logging.debug("Restarting uTorrent")
						subprocess.Popen(uTorrentBin)
						return
			else:
				# Windows XP Home Edition does not have taskkill
				# use tskill util instead
				killCmd = 'tskill /v utorrent'
				logging.debug("Killing uTorrent cmd line: " + killCmd)
				p = subprocess.Popen(killCmd, shell=True, stdout=subprocess.PIPE)
				retVal = p.stdout.read()
				logging.debug("Killing uTorrent output: " + retVal.strip())
				if retVal.find('End Process') >= 0:
					os.chdir(uTorrentPath)
					logging.debug("Restarting uTorrent")
					subprocess.Popen(uTorrentBin)
					return
			logging.error("Unable to restart uTorrent")

if __name__ == "__main__":
	print "Starting transcode daemon, hit Ctrl-C to exit"
	initDaemon()
	logging.debug('Starting transcode daemon')
	sane = SanityCheck()
	if not sane:
		sys.exit()
	w = Watchdog(maintenanceTime)
	while True:
		try:
			w.check()
			ScanForBtFiles(btDownloadPath)
			ScanForNPVRFiles()
			time.sleep(pollRate*60)
		except KeyboardInterrupt:
			print "Received Ctrl-C! Exiting..."
			break
		except WindowsError as e:
			# this sometimes happens when the file is still locked by uTorrent
			logging.exception(e)
			continue
		except Exception as e:
			logging.error("Unexpected exception encountered")
			logging.exception(e)
			if exitOnException:
				sys.exit()

