#!/usr/bin/python

import glob
import logging
import os
import os.path
import re
from optparse import OptionParser
import tarfile
import socket
import datetime
import tempfile
import shlex
import subprocess

GBP_SUPPORT_INFO_DIRECTORY = "/etc/gbp-support/"
GBP_SUPPORT_INFO_EXT = "*.gbp"
gSystemdFound = False

class ActionInfo(object):
	def __init__(self, oper, opt, args):
		self._operation = oper
		self._args = args
		self._parseOptions(opt)
	
	def do(self, tarobj):
		if not self._shouldExecute():
			return
		if self._operation == "copy":
			self._doCopy(tarobj)
		elif self._operation == "exec":
			self._doExec(tarobj)
		else:
			logging.info("Ignoring unknown operation: %s" % self._operation)
	
	def _parseOptions(self, optstr):
		self._options = {}
		for optval in optstr.split(","):
			opt = optval
			val = None
			if '=' in optval:
				(opt, val) = tuple(optval.split("=", 1))
			if opt != "-":
				self._options[opt] = val
	
	def _hasOption(self, optionKey):
		return self._options.has_key(optionKey)
	
	def _getOption(self, optionKey, defValue):
		return (self._hasOption(optionKey) and self._options[optionKey] or defValue)
	
	def _shouldExecute(self):
		optSystemd = self._getOption("have_systemd", None)
		if optSystemd != None and optSystemd.lower() in ["true", "false"]:
			return ((optSystemd.lower() == "true") == gSystemdFound)
		return True
	
	def _doCopy(self, tarobj):
		rec = self._hasOption("recursive")
		logging.debug("Copying file(s) %s (recursive=%s)" % (self._args, rec))
		files = glob.glob(self._args)
		for f in files:
			if not rec and os.path.isdir(f):
				continue
			realFile = os.path.realpath(f)
			tarobj.add(realFile, arcname=f, recursive=rec)
		
	def _doExec(self, tarobj):
		if not self._args:
			return
		(tmpFd, tmpFilename) = tempfile.mkstemp()
		try:
			logging.debug("Executing command: %s, tempfile=%s" % (self._args, tmpFilename))
			cmdArgs = shlex.split(self._args)
			retcode = subprocess.call(cmdArgs, stdout=tmpFd, stderr=tmpFd)
			if retcode != 0:
				logging.warning("Command '%s' exited with non-zero return code %d" %
					(self._args, retcode))
			n = os.path.join("commands", self._args.replace(" ", "_").replace("/", "_"))
			tarobj.add(tmpFilename, arcname=n)
		except Exception, e:
			logging.warning("Could not run command '%s': %s" % (self._args, e))
		finally:
			os.close(tmpFd)
			os.remove(tmpFilename)

def parseSupportInfoFile(filename):
	logging.debug("Parsing support info file: %s" % filename)

	reComment = re.compile(r'^\s*#.*$')
	reBlank = re.compile(r'^\s*$')
	reAction = re.compile(r'^\s*(?P<operation>\S+)\s+(?P<options>\S+)\s+(?P<args>.+)')
	
	actions = []
	with open(filename, "r") as fd:
		for l in fd.readlines():
			if reComment.match(l) or reBlank.match(l):
				continue
			m = reAction.match(l)
			if m:
				actions.append(
					ActionInfo(m.group("operation"), m.group("options"), m.group("args")))
			else:
				logging.debug("Ignoring unknown line: %s" % l)
	logging.debug("Found %d actions in file %s" % (len(actions), filename))
	return actions

def loadSupportInfo(supportDir):
	logging.debug("Looking for support info files in %s" % supportDir)
	actions = []
	filenames = glob.glob(os.path.join(supportDir, GBP_SUPPORT_INFO_EXT))
	for f in filenames:
		try:
			actions.extend(parseSupportInfoFile(f))
		except Exception,e:
			logging.warning("Error while parsing file %s: %s" % (f, e))
	return actions

def executeActions(actions, tarobj):
	logging.debug("Number of actions to execute: %d" % len(actions))
	for a in actions:
		a.do(tarobj)

def createTarFile(outputDir, outputFilename):
	if not outputFilename:
		timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M");
		outputFilename = "gbp_%s_%s.tar.gz" % (socket.gethostname(), timestamp)

	filename = os.path.join(outputDir, outputFilename)
	try:
		tar = tarfile.open(filename, "w:gz")
		return (tar, filename)
	except Exception, te:
		logging.error("Unable to open tar file %s: %s" % (filename, te))
		return (None, None)

def checkSystemdPresence():
	global gSystemdFound
	try:
		retcode = subprocess.call(["pidof", "systemd"], stdout=subprocess.PIPE)
		gSystemdFound = (retcode == 0)
	except Exception, e:
		logging.warning("Unable to determine if systemd is present: %s" % e)
	logging.debug("Systemd present: %s" % gSystemdFound)

def setupLogging(verbose):
	consoleLevel = logging.ERROR
	fileLevel = logging.INFO
	if verbose:
		consoleLevel = logging.DEBUG
		fileLevel = logging.DEBUG
	
	f = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
	
	h1 = logging.StreamHandler()
	h1.setLevel(consoleLevel)
	h1.setFormatter(f)

	tempLogFile = tempfile.NamedTemporaryFile()
	h2 = logging.FileHandler(tempLogFile.name)
	h2.setLevel(fileLevel)
	h2.setFormatter(f)
	
	rootLogger = logging.getLogger()
	rootLogger.setLevel(logging.NOTSET)
	rootLogger.addHandler(h1)
	rootLogger.addHandler(h2)
	return tempLogFile
	
def parseOptions():
	parser = OptionParser()
	parser.add_option("-i", "--inputdir",
	                  dest = "inputDir", default = GBP_SUPPORT_INFO_DIRECTORY,
		              help = "Directory to read support information files from")
	parser.add_option("-o", "--outputdir",
	                  dest = "outputDir", default = "/tmp",
		              help = "Directory to create the support bundle in")
	parser.add_option("-f", "--filename",
	                  dest = "outputFilename", default = None,
		              help = "Use specified name for the bundle file instead of generating one")
	parser.add_option("--verbose", dest = "logverbose", default = False,
	                  action = "store_true",
		              help = "Use verbose logging while creating the bundle")
	return parser.parse_args()

def main():
	(options, _) = parseOptions()
	logfile = setupLogging(options.logverbose)
	actions = loadSupportInfo(options.inputDir)
	(tarobj, tarfilename) = createTarFile(options.outputDir, options.outputFilename)
	if tarobj:
		checkSystemdPresence()
		executeActions(actions, tarobj)
		tarobj.add(logfile.name, arcname="support.log")
		tarobj.close()
		print "GBP support information collected in file %s" % tarfilename
	logfile.close()
	
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("Ctrl-c pressed, exiting")

