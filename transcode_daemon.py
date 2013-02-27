import os
import glob
import string
import msvcrt
import time
import re
import shutil

# Config
debugFlag = False
handbrakePath = "C:\\Program Files\\Handbrake\\"
downloadPath = "C:\\Documents and Settings\\Ken\\My Documents\\Downloads"
destinationPath = "C:\\media\\video"
inputFileExt = '.*\.avi$|.*\.mkv$|.*\.mp4$|.*\.3gp$'
outputFileExt = ".m4v"
replacementChar = " "
pollRate = 10	# in minutes
tvFilePatterns = ["[sS][0-9]+[eE][0-9]+", "[0-9]+[xX][0-9]+"]

print "Starting transcode daemon, hit Ctrl-C to exit"
while True:
	try:
		os.chdir(downloadPath)	
		for f in os.listdir('.'):
			if re.match(inputFileExt, f):
				sourceFilePath = os.path.join(downloadPath, f)
				print "Found a file: " + sourceFilePath
				# replace dots so it appears correctly on Roku
				resultingFileBaseName = string.replace(os.path.splitext(os.path.basename(sourceFilePath))[0], ".", replacementChar)
				# if it's a TV episode then calculate a show folder, create the folder if necessary, and calc final path
				# TODO try and match filenames that use "0501" instead of "S05E01" as well
				tvFound = False
				for pattern in tvFilePatterns:
					splitArr = re.split(pattern, resultingFileBaseName)
					if len(splitArr) > 1:
						resultingFolderName = string.strip(splitArr[0])
						print "Found folder name: " + resultingFolderName
						resultingFilePath = os.path.join( destinationPath, resultingFolderName)
						if not os.path.isdir(resultingFilePath):
							# TODO make sure that case is ignored when looking for matching directory
							os.mkdir(resultingFilePath)
							print "Made new directory: " + resultingFilePath
						resultingFilePath = os.path.join( resultingFilePath, resultingFileBaseName + outputFileExt)
						tvFound = True
						break
				if not tvFound:
					resultingFilePath = os.path.join( destinationPath, resultingFileBaseName + outputFileExt)
					print "Could not calculate folder name"
				print "Resulting file: " + resultingFilePath
				# Call Handbrake
				handbrakeCmdLine = "HandbrakeCLI.exe -i \"" + sourceFilePath + "\" -o \"" + resultingFilePath + "\" --preset=\"Normal\" > hb.log"
				print "Handbrake Command Line: " + handbrakeCmdLine
				os.chdir( handbrakePath)
				if debugFlag:
					shutil.copy(sourceFilePath, resultingFilePath)
				else:
					os.system( handbrakeCmdLine)
				# cleanup source file
				if os.path.exists(resultingFilePath):
					print "Deleting source file"
					os.remove(sourceFilePath)
				else:
					print "Error: file " + resultingFilePath + " does not exist. Handbrake probably failed."
		time.sleep(pollRate*60)
	except KeyboardInterrupt:
		print "Received Ctrl-C! Exiting..."
		break

