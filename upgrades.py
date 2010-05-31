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
from Acquisition import aq_base
from negociator import CPSDESIGNER_LOCAL_THEME_ID, CPSSKINS_LOCAL_THEME_ID

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

def check_method_themes(portal):
    logger = logging.getLogger(LOGGER_BASE + '#check_method_themes')
    thmtool = getattr(portal, 'portal_themes', None)
    if thmtool is None:
        logger.info("No CPSSkins themes tool")
        return False
    if getattr(aq_base(portal), CPSDESIGNER_LOCAL_THEME_ID, None) is not None:
        logger.info("Found existing attribute or property %s", CPSDESIGNER_LOCAL_THEME_ID)
        return False
    return True

def upgrade_method_themes(portal):
    logger = logging.getLogger(LOGGER_BASE + '#upgrade_method_themes')
    thmtool = getattr(portal, 'portal_themes', None)
    if thmtool is None:
        logger.info("No CPSSkins tool. Nothing to do.""")
        return

    # Reading existing themes specifications on portal
    thms = getattr(aq_base(portal), CPSDESIGNER_LOCAL_THEME_ID, None)
    if thms is not None:
        # should be very rare, no need to automate further
        raise RuntimeError("%s property or attribute found on portal. "
                           "You should remove it, keeping the values, "
                           "run the upgrade step again "
                           "and merge previous values afterwards.")

    script_based = False
    thms = portal.getProperty(CPSSKINS_LOCAL_THEME_ID, None)
    if thms is not None:
        logger.info("Found existing CPSSkins themes specification prop.")
        portal.manage_delProperties((CPSSKINS_LOCAL_THEME_ID,))
    else:
        # retry in case there is an attr that is no prop
        thms = getattr(aq_base(portal), CPSSKINS_LOCAL_THEME_ID, None)
        if thms is not None:
            if (not isinstance(thms, basestring) and not isinstance(thms, tuple)
                and not isinstance(thms, list)):
                script_based = True
                script = thms
                thms = None
            else: # would be rollbacked if not in else statement, but well
                logger.info("Found existing themes specification attribute.")
                delattr(portal, CPSSKINS_LOCAL_THEME_ID)

    if thms is None:
        thms = []
    if isinstance(thms, basestring):
        thms = [thms]
    thms = list(thms)

    # Now translating Method Themes in a specification
    for meth, thm in getattr(thmtool, 'method_themes', {}).items():
        v = '%s:0-0:%s' % (meth, thm)
        logger.info("New themes spec in property: %s", v)
        thms.insert(0, v)

    if script_based:
        raise RuntimeError(
                ("Unapplicable existing CPSSkins theme specification %s" +
                 "Upgrade manually (check INFO log)") % script)

    if thms:
        portal.manage_addProperty(CPSDESIGNER_LOCAL_THEME_ID, thms, 'lines')
