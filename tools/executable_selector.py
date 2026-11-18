# -*- coding: utf-8 -*-

import os
import platform
import stat
import sys
from glob import glob

# Return the first IdrAgra executable matching the OS and architecture
def select_model_executable(plugin_dir):
	bin_dir = os.path.join(plugin_dir, 'bin')

	if sys.platform == 'darwin':
		arch = mac_architecture()
		search_dir = os.path.join(bin_dir, 'macOS')
		pattern = 'idragra*_%s' % arch
	elif sys.platform == 'win32':
		search_dir = os.path.join(bin_dir, 'Windows')
		pattern = 'idragra*.exe'
	else:
		return ''

	matches = sorted(glob(os.path.join(search_dir, pattern)))
	return matches[0] if matches else ''

# Selects the appropriate macOS architecture (arm64 or x86_64)
def mac_architecture():
	machine = platform.machine().lower()
	if machine in ('arm64', 'aarch64'):
		return 'arm64'
	if machine in ('x86_64', 'amd64'):
		return 'x86_64'
	raise RuntimeError('Unsupported macOS architecture: %s' % machine)

# If not on Windows, ensure that the selected file is recognized as executable by the OS (chmod +x)
def ensure_is_executable(path):
	if os.name != 'nt' and os.path.isfile(path):
		mode = os.stat(path).st_mode
		if not mode & stat.S_IXUSR:
			os.chmod(path, mode | stat.S_IXUSR)
	return path
