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

from themecontainer import FSThemeContainer

_marker = object()

NAME = 'designer_themes'

ROOT_THEMES = '.cps_themes'

def importRootThemesContainer(context):
    """Create the root themes container.

    TODO: also import it (not important yet)
    """
    site = context.getSite()
    if ROOT_THEMES in site.objectIds():
        return

    logger = context.getLogger(NAME)
    logger.info("Creating the root themes container")
    thc = FSThemeContainer(ROOT_THEMES)
    thc.manage_changeProperties(title='Root themes')
    site._setObject(ROOT_THEMES, thc)

