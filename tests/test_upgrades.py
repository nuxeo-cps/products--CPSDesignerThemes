# (C) Copyright 2010 Georges Racinet
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

#$Id$

# testing module and harness

import unittest
from Testing import ZopeTestCase
from Products.PythonScripts.PythonScript import PythonScript
from Products.CPSDesignerThemes import upgrades
from Products.CPSDesignerThemes.negociator import CPSDESIGNER_LOCAL_THEME_ID
from Products.CPSDesignerThemes.negociator import CPSSKINS_LOCAL_THEME_ID

try:
    from Products.CPSSkins.PortalThemesTool import PortalThemesTool
    ZopeTestCase.installProduct('CPSSkins')
    CPSSKINS_PRESENT = True
except ImportError:
    CPSSKINS_PRESENT = False

ZopeTestCase.installProduct('PythonScripts')
ZopeTestCase.installProduct('CPSDesignerThemes')


class TestCPSSkinsUpgrades(ZopeTestCase.ZopeTestCase):
    """Upgrade tests related to CPSSkins."""

    def afterSetUp(self):
        portal = self.portal = self.folder
        portal._setObject('portal_themes', PortalThemesTool())
        self.thm_tool = portal.portal_themes

    def assertNone(self, x):
        self.assertTrue(x is None)

    def getPortalThemesSpec(self):
        return self.portal.getProperty(CPSDESIGNER_LOCAL_THEME_ID, None)

    def test_method_themes_0(self):
        # Empty method themes
        self.thm_tool.method_themes = dict()
        upgrades.upgrade_method_themes(self.portal)
        self.assertNone(self.getPortalThemesSpec())

    def test_method_themes_1(self):
        # The most common case.
        self.thm_tool.method_themes = dict(index_html='default+Front')
        upgrades.upgrade_method_themes(self.portal)
        # CPSSkins Method Themes apply portal-wide, hence 0-0
        self.assertEquals(self.getPortalThemesSpec(),
                          ('index_html:0-0:default+Front',))

    def test_method_themes_2(self):
        self.thm_tool.method_themes = dict(index_html='default+Front',
                                           folder_view='other')
        upgrades.upgrade_method_themes(self.portal)
        spec = set(self.getPortalThemesSpec())
        self.assertEquals(spec, set((
            'folder_view:0-0:other',
            'index_html:0-0:default+Front')))

    def test_method_themes_existing_spec_prop_lines(self):
        # Existing CPSSkins themes spec lines property
        self.thm_tool.method_themes = dict(index_html='default+Front')
        self.portal.manage_addProperty(CPSSKINS_LOCAL_THEME_ID,
                                       ('1-1:predefined',), 'lines')
        upgrades.upgrade_method_themes(self.portal)
        spec = set(self.getPortalThemesSpec())
        self.assertEquals(spec, set((
            'index_html:0-0:default+Front',
            '1-1:predefined')))
        self.assertNone(getattr(self.portal, CPSSKINS_LOCAL_THEME_ID, None))

    def test_method_themes_existing_spec_prop_lines_no_meth(self):
        # Existing CPSSkins themes spec lines property
        self.thm_tool.method_themes = dict()
        self.portal.manage_addProperty(CPSSKINS_LOCAL_THEME_ID,
                                       ('1-1:predefined',), 'lines')
        upgrades.upgrade_method_themes(self.portal)
        spec = self.getPortalThemesSpec()
        self.assertEquals(spec, ('1-1:predefined',))
        self.assertNone(getattr(self.portal, CPSSKINS_LOCAL_THEME_ID, None))

    def test_method_themes_existing_spec_prop_string(self):
        # Existing CPSSkins themes spec string property
        self.thm_tool.method_themes = dict(index_html='default+Front')
        self.portal.manage_addProperty(CPSSKINS_LOCAL_THEME_ID,
                                       '1-1:predefined', 'string')
        upgrades.upgrade_method_themes(self.portal)
        spec = set(self.getPortalThemesSpec())
        self.assertEquals(spec, set((
            'index_html:0-0:default+Front',
            '1-1:predefined')))
        self.assertNone(getattr(self.portal, CPSSKINS_LOCAL_THEME_ID, None))

    def test_method_themes_existing_spec_attr(self):
        # Existing CPSSkins themes spec, as an attribute
        self.thm_tool.method_themes = dict(index_html='default+Front')
        setattr(self.portal, CPSSKINS_LOCAL_THEME_ID, ('1-1:predefined',))
        upgrades.upgrade_method_themes(self.portal)
        spec = set(self.getPortalThemesSpec())
        self.assertEquals(spec, set((
            'index_html:0-0:default+Front',
            '1-1:predefined')))
        self.assertNone(getattr(self.portal, CPSSKINS_LOCAL_THEME_ID, None))

    def test_method_themes_existing_spec_prog(self):
        # Existing CPSSkins themes spec, programmatic
        self.portal._setObject(CPSSKINS_LOCAL_THEME_ID,
                               PythonScript(CPSSKINS_LOCAL_THEME_ID))
        self.assertRaises(RuntimeError,
                          upgrades.upgrade_method_themes, self.portal)

    def test_method_themes_existing_spec_prog(self):
        # Existing CPSDesigner themes spec
        setattr(self.portal, CPSDESIGNER_LOCAL_THEME_ID, ('0-0:default',))
        self.assertRaises(RuntimeError,
                          upgrades.upgrade_method_themes, self.portal)

def test_suite():
    suite = unittest.TestSuite()
    if CPSSKINS_PRESENT:
        suite.addTest(unittest.makeSuite(TestCPSSkinsUpgrades))
    return suite
