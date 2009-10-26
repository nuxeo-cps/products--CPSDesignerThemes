# (C) Copyright 2008 Georges Racinet
# Author: Georges Racinet <georges@racinet.fr>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#
# $Id: __init__.py 53654 2009-06-14 13:18:41Z gracinet $

"""CPS Designer themes related upgrades steps."""

import logging

LOGGER_BASE = 'Products.CPSDesignerThemes.upgrades'

def upgrade_trac_ticket_2045(portal):
    logger = logging.getLogger(LOGGER_BASE + '#upgrade_trac_ticket_2045')
    for container in portal.objectValues(["Filesystem Theme Container"]):
        container = container.aq_base
        try:
            delattr(container, 'path') # this is now dynamic
            logger.info(
                "Successfully removed persistent absolute path reference "
                "from root container '%s'", container.getId())
        except AttributeError:
            logger.info("No persistent absolute path to clean out "
                        "in root containe '%s'", container.getId())
