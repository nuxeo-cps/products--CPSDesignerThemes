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
# $Id$

from zope.component import adapts
from zope.interface import implements

from themecontainer import FSThemeContainer
from Products.GenericSetup.utils import XMLAdapterBase
from Products.GenericSetup.utils import PropertyManagerHelpers
from Products.GenericSetup.utils import exportObjects
from Products.GenericSetup.utils import importObjects

from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.interfaces import ISetupEnviron
from interfaces import IThemeContainer
_marker = object()

NAME = 'designer_themes'

ROOT_THEMES = '.cps_themes'

def importRootThemesContainer(context):
    """Create the root themes container.
    """
    logger = context.getLogger(NAME)
    logger.info("Creating the root themes container")

    site = context.getSite()
    thc = getattr(site, ROOT_THEMES, None)
    if thc is None:
        thc = FSThemeContainer(ROOT_THEMES)
        thc.manage_changeProperties(title='Root themes')
        site._setObject(ROOT_THEMES, thc)
        thc = getattr(site, ROOT_THEMES)
    importObjects(thc, '', context)


def exportRootThemesContainer(context):
    """Export the root themes container
    """
    site = context.getSite()
    thc = getattr(site, ROOT_THEMES)
    if thc is None:
        logger = context.getLogger(NAME)
        logger.info("Nothing to export.")
        return
    exportObjects(thc, '', context)

class ThemeContainerXMLAdapter(XMLAdapterBase, PropertyManagerHelpers):
    """XML importer and exporter for theme containers
    """

    adapts(IThemeContainer, ISetupEnviron)
    implements(IBody)

    _LOGGER_ID = NAME
    name = NAME

    def _exportNode(self):
        """Export the object as a DOM node.
        """
        node = self._getObjectNode('object')
        node.appendChild(self._extractProperties())
        self._logger.info("Root themes container exported.")
        return node

    def _importNode(self, node):
        """Import the object from the DOM node.
        """
        if self.environ.shouldPurge():
            self._purgeProperties()
        self._initProperties(node)
        self._logger.info("Root theme container imported.")

