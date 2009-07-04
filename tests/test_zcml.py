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
# $Id: __init__.py 53718 2009-06-30 17:13:43Z gracinet $

import unittest
from Products.Five import zcml

import Products.CPSDesignerThemes
from Products.CPSDesignerThemes import engine
from Products.CPSDesignerThemes.engine.lxmlengine import LxmlEngine

class TestZcml(unittest.TestCase):
    def setUp(self):
        zcml.load_config('meta.zcml', Products.CPSDesignerThemes)

    def test_engine_class(self):
        zcml.load_string("""
          <theme:engine
            class="Products.CPSDesignerThemes.engine.lxmlengine.LxmlEngine"
            xmlns:theme="http://xmlns.racinet.org/zcml/designer-themes"/>""")
        self.assertEquals(engine.get_engine_class(), LxmlEngine)

def test_suite():
    return unittest.makeSuite(TestZcml)
