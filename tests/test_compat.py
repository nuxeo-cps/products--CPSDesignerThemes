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
from Testing import ZopeTestCase

ZopeTestCase.installProduct('CPSDesignerThemes')

class TestCompat(ZopeTestCase.ZopeTestCase):
    """High level compatibility test.

    This test checks that the compatibility mode is working, without referring
    to any Zope version specific code.
    """
    pass


def test_suite():
    return unittest.TestSuite((
        unittest.makeSuite(TestCompat),
        ))
