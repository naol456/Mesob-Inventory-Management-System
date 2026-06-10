# -*- coding: utf-8 -*-
import os
import logging

_logger = logging.getLogger(__name__)

# Dynamically inject Odoo's local wkhtmltopdf directory into System PATH to bypass Windows permission blocks
wkhtml_path = r"C:\Program Files\Odoo 19.0.20260218\thirdparty"
if os.path.exists(wkhtml_path):
    if wkhtml_path not in os.environ.get("PATH", ""):
        os.environ["PATH"] += os.pathsep + wkhtml_path
        _logger.info("Successfully registered local wkhtmltopdf path: %s", wkhtml_path)
else:
    _logger.warning("Local wkhtmltopdf path not found: %s", wkhtml_path)

from . import models
from . import wizard
