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

from zope.interface import Interface

class IThemeEngine(Interface):
    """A theme engine is initiated from a theme page and does the rendering."""

    def renderCompat(self, metal_slots=None, pt_output=''):
        """Compatibility mode rendering.

        Cooks the rendering from the contents of the metal macro slots
        and the overall pt_output.
        """

class IThemeContainer(Interface):

    def getPageEngine(theme, page):
        """Return an engine for page rendering.

        Raises KeyError if page could not be found.
        """

    def invalidate(theme, page=None):
        """Invalidates the preprocessing cache for theme pages.

        if no page is specified, the whole theme is being invalidated."""


