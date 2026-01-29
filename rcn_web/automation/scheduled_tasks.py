import asyncio
import re
import datetime

import rcn_core.globals

from rcn_core.utils import storage_automation_md_get_create, time_str_to_secs

from rcn_core.data_access import storage
from rcn_core.log import rlog
from rcn_core import rcn_event

@rcn_event
async def example_scheduled_task(event, scheduled_md):
    rlog(f"Running example task: {event.get('name')}")