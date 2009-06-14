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

from Products.CMFCore.DirectoryView import registerDirectory

from Products.GenericSetup import profile_registry
from Products.GenericSetup import EXTENSION

from Products.CPSCore.interfaces import ICPSSite
from Products.CPSCore.upgrade import registerUpgradeCategory

registerDirectory('skins', globals())

import compat # BBB for old page templates
import negociator

def initialize(registrar):
    """Initialize Paris Montagne Contacts content and tools.
    """

    # optional ldap; to be triggered by external method only
    profile_registry.registerProfile(
        'default',
        'CPS Designer Themes',
        "CPS Designer Themes, default configuration",
        'profiles/default',
        'CPSDesignerThemes',
        EXTENSION,
        for_=ICPSSite)


