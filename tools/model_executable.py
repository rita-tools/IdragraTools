# -*- coding: utf-8 -*-

"""Select the bundled model executable for the current platform."""

import os
import platform
import stat
import sys
from glob import glob

# Choose the default IdrAgra/CropCoef executables, located in bin/latest, based on OS and architecture
def bundled_model_executable_path(plugin_dir, model, platform_name=None, machine=None):
	platform_name = platform_name or sys.platform
	latest_dir = os.path.join(plugin_dir, 'bin', 'latest')
	if platform_name == 'darwin':
		arch = mac_architecture(machine)
		pattern = '%s*_macOS_%s' % (model, arch)
	else:
		pattern = '%s*.exe' % model

	matches = glob(os.path.join(latest_dir, pattern))
	return matches[0] if matches else ''

# Choose the correct macOS architecture (arm64/x86_64)
def mac_architecture(machine=None):
	machine = (machine or platform.machine()).lower()
	if machine in ('arm64', 'aarch64'):
		return 'arm64'
	if machine in ('x86_64', 'amd64'):
		return 'x86_64'
	raise RuntimeError('Unsupported macOS architecture: %s' % machine)

# Ensure macOS executables are actually recognized as executables
def ensure_mac_executable(path):
	if os.name != 'nt' and os.path.isfile(path):
		mode = os.stat(path).st_mode
		if not mode & stat.S_IXUSR:
			os.chmod(path, mode | stat.S_IXUSR)
	return path
