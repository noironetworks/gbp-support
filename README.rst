=======
Gbp-support
=======

Support information collection framework for GBP

Install
=======

    git clone https://github.com/noironetworks/gbp-support.git
    cd gbp-support
    python setup.py install


Running
=======

Run command 'gbp-support' to collect support information like logs,
configuration files, output of various commands etc in to a support
bundle (zipped tarball). Information to be collected is specified
through a set of "support-information files"; by default the framework
uses files that have the extension '.gbp' in directory '/etc/gbp-support'
as support-information files. Use '--help' to list supported options.


Support-information file format
===============================

Each support-information file lists actions that need to be taken.

   # comment1
   # comment2
   # ...
   # action options file/command
   copy   recursive                /var/log/neutron/*
   exec   -                        ip addr
   exec   have_systemd=true        journalctl --no-pager -u agent-ovs
   ...

Supported commands:
   copy
      Copies the specified files into the bundle. File names may contain
      wildcards. Directories are not copied recursively unless the 'recursive'
      option is specified.

   exec
      Runs the specified command and puts the output into the bundle. Output
      must be to stdout. Both stdout and stderr are redirected to the same file.

Command options:
   recursive
      recursively copy directories.

   have_systemd=true|false
      Do the specified action only if systemd is found/not found.


Support-bundle contents
=======================
support.log : File containing log messages generated while collecting
              support information
commands/   : Output of various commands
<other>     : Files copied with the 'copy' command
