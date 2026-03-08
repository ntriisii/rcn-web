
import os

from rcn_web.viewers.emacs import *
from rcn_web.scanning import *
from rcn_web.flows import *
from rcn_web.storage import *
from rcn_web.core.scope import * 
from rcn_core.acp_processor import process_acp_event

import rcn_core.globals

# print("before setting the freaking Base_server_config_path ", rcn_core.globals.BASE_SERVER_CONFIG_PATH)
# rcn_core.globals.BASE_SERVER_CONFIG_PATH = os.path.expanduser("~/.config/rcn-server/server-config.yaml")
