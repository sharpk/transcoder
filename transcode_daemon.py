import os
import glob
import string
import msvcrt
import time
import re
import shutil
import sys

# Config
debugFlag = False
handbrakePath = "C:\\Program Files\\Handbrake\\"
btDownloadPath = "C:\\Documents and Settings\\Ken\\My Documents\\Downloads"
btbtInputFileExt = '.*\.avi$|.*\.mkv$|.*\.mp4$|.*\.3gp$'
npvrRecordingPath = ""
destinationBasePath = "C:\\media\\video"
outputFileExt = ".m4v"
replacementChar = " "
pollRate = 10	# in minutes
tvFilePatterns = ["[sS][0-9]+[eE][0-9]+", "[0-9]+[xX][0-9]+"]

def btMakePrettyFileName(sourceFilePath):
	return string.replace(os.path.splitext(os.path.basename(sourceFilePath))[0], ".", replacementChar)

def CalcDestinationPath(prettyFileBaseName):
	# TODO try and match filenames that use "0501" instead of "S05E01" as well
	tvFound = False
	destinationFilePath = ""
	for pattern in tvFilePatterns:
		splitArr = re.split(pattern, prettyFileBaseName)
		if len(splitArr) > 1:
			resultingFolderName = string.strip(splitArr[0])
			print "Found folder name: " + resultingFolderName
			destinationFilePath = os.path.join( destinationBasePath, resultingFolderName)
			if not os.path.isdir(destinationFilePath):
				# TODO make sure that case is ignored when looking for matching directory
				os.mkdir(destinationFilePath)
				print "Made new directory: " + destinationFilePath
			destinationFilePath = os.path.join( destinationFilePath, prettyFileBaseName + outputFileExt)
			tvFound = True
			break
	if not tvFound:
		destinationFilePath = os.path.join( destinationBasePath, prettyFileBaseName + outputFileExt)
		print "Could not calculate folder name"
	return destinationFilePath

def ConvertVideoFile(sourceFilePath, destinationFilePath):
	# Call Handbrake
	handbrakeCmdLine = "HandbrakeCLI.exe -i \"" + sourceFilePath + "\" -o \"" + destinationFilePath + "\" --preset=\"Normal\" > hb.log"
	print "Handbrake Command Line: " + handbrakeCmdLine
	os.chdir(handbrakePath)
	if debugFlag:
		shutil.copy(sourceFilePath, destinationFilePath)
	else:
		os.system(handbrakeCmdLine)
	# cleanup source file
	if os.path.exists(destinationFilePath):
		if debugFlag:
			print "Not deleting source file since debugFlag = true"
		else:
			print "Deleting source file"
			os.remove(sourceFilePath)
	else:
		print "Error: file " + destinationFilePath + " does not exist. Handbrake probably failed."
	
def ScanForBtFiles():
	os.chdir(btDownloadPath)	
	for f in os.listdir('.'):
		if re.match(btInputFileExt, f):
			sourceFilePath = os.path.join(btDownloadPath, f)
			print "Found a file: " + sourceFilePath
			# replace dots so it appears correctly on Roku
			prettyFileBaseName = btMakePrettyFileName(sourceFilePath)
			# if it's a TV episode then calculate a show folder, create the folder if necessary, and calc final path
			destinationFilePath = CalcDestinationPath(prettyFileBaseName)
			print "Prettified destination path: " + destinationFilePath
			# Use Handbrake to do the transcode
			ConvertVideoFile(sourceFilePath, destinationFilePath)

def ScanForNPVRFiles():
	os.chdir(npvrRecordingPath)
	for f in os.listdir('.'):
		if re.match('.*\.done$', f):
			doneFilePath = os.path.join(npvrRecordingPath, f)
			print "Found a file: " + sourceFilePath
			# get rid of *.done to get actual movie file path
			sourceFilePath = os.path.join(npvrRecordingPath, os.path.splitext(f)[0])
			# run comskip and comclean(2|3) to remove commercials
			# run handbrake to convert file (and delete source)
			# delete .done file
			# do additional NextPVR cleanup?  like remove entry from NPVR DB
	return

def SanityCheck():
	# check that directories exist
	if not os.path.exists(handbrakePath):
		print "Error: Handbrake path does not exist: " + handbrakePath
		return false
	if not os.path.exists(btDownloadPath):
		print "Error: bittorrent download path does not exist: " + btDownloadPath
		return false
	if not os.path.exists(npvrRecordingPath):
		print "Error: NextPVR path does not exist: " + npvrRecordingPath
		return false
	if not os.path.exists(destinationBasePath):
		print "Error: Destination path does not exist: " + destinationBasePath
		return false
		
	# check that PostProcessing.bat is installed and contains code to create *.done files
	
	# check that uTorrent is set to use .!ut extension until download is complete, or that it uses a separate "completed download" directory
	
	return true

if __name__ == "__main__":
	print "Starting transcode daemon, hit Ctrl-C to exit"
	while True:
		try:
			sane = SanityCheck()
			if not sane:
				sys.exit()
				
			ScanForBtFiles()
			ScanForNPVRFiles()
			time.sleep(pollRate*60)
		except KeyboardInterrupt:
			print "Received Ctrl-C! Exiting..."
			break

