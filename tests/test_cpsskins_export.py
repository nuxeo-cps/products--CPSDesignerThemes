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

import unittest
from Products.CPSDefault.tests.CPSTestCase import CPSTestCase

from Products.ExternalMethod.ExternalMethod import ExternalMethod
class CPSSkinsExportTestCase(CPSTestCase):

    def afterSetUp(self):
        meth = ExternalMethod('cpsskins_export', '',
                              'CPSDesignerThemes.cpsskins_export',
                              'export')
        self.portal._setObject(meth.getId(), meth)

    def test_all_default(self):
        self.portal.cpsskins_export()


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(CPSSkinsExportTestCase),
        ))
