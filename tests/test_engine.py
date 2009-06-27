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
from zope.testing import doctest
import os
import re

from Products.CPSDesignerThemes.engine.etreeengine import (
    ElementTreeEngine,
    TwoPhaseElementTreeEngine,
    )
from Products.CPSDesignerThemes.engine.lxmlengine import LxmlEngine
from Products.CPSDesignerThemes.constants import NS_XHTML

THEMES_PATH = os.path.join(INSTANCE_HOME, 'Products', 'CPSDesignerThemes',
                           'tests')

PORTLET1 = ('portlet1', '<ul id="portlet1"><li>foo</li></ul>')

WT_REGEXP = re.compile(r'[\n ]*')

def get_engine(EngineClass, theme, page='index.html', cps_base_url=None):
    f = open(os.path.join(THEMES_PATH, theme, page), 'r')
    return EngineClass(html_file=f,
                       theme_base_uri='/thm_base',
                       page_uri='/'+page, cps_base_url=cps_base_url)

class EngineTestCase(unittest.TestCase):
    """Base test case for all engines."""

    EngineClass = None

    def getEngine(self, theme, page='index.html'):
        return get_engine(self.EngineClass, theme, page=page)

    def findTag(self, engine, tag):
        raise NotImplementedError

    def assertXhtmlTagEquals(self, element, tag):
        raise NotImplementedError

    def getChild(self, element, i):
        raise NotImplementedError

    @classmethod
    def getAttribs(self, element):
        raise NotImplementedError

    def test_extractSlotFrame(self):
        engine = self.getEngine('theme1', 'simple_slot.html')
        slot_name, slot = engine.extractSlotElements().next()
        frame_parent, frame = engine.extractSlotFrame(slot)
        self.assertXhtmlTagEquals(frame, 'p')
        self.assertEquals(self.getAttribs(frame), {})

    def test_entities(self):
        engine = self.getEngine('theme1', 'simple_slot.html')
        slot_name, slot = engine.extractSlotElements().next()
        frame_parent, frame = engine.extractSlotFrame(slot)
        portlet = ('entity_portlet', '<spoon>&nbsp;</spoon>')
        engine.mergePortlets(frame_parent, frame, [portlet])

        rendered = WT_REGEXP.sub('', engine.dumpElement(slot))
        expected = WT_REGEXP.sub(
            '', '<div xmlns="%s"><p>'
            '<span>%s</span><div>%s</div>'
            '</p></div>' % (NS_XHTML, portlet[0], portlet[1]))
        expected = expected.replace('&nbsp;', '&#160;')
        self.assertEquals(rendered, expected)

    def test_uri_rewrite(self):
        # engine must accept a missing cps:portlet="body"
        engine = self.getEngine('theme1', page='uris.html')
        img = self.findTag(engine, 'img')
        self.assertEquals(img.attrib['src'], '/thm_base/pretty.png')


class TestElementTreeEngine(EngineTestCase):

    EngineClass = ElementTreeEngine

    @classmethod
    def findTag(self, engine, tag):
        return engine.root.find('.//{%s}%s' % (NS_XHTML, tag))

    def assertXhtmlTagEquals(self, element, tag):
        self.assertEquals(element.tag, '{%s}%s' % (NS_XHTML, tag))

    @classmethod
    def getChild(self, element, i):
        return element[i]

    @classmethod
    def getAttribs(self, element):
        return element.attrib

class TestLxmlEngine(TestElementTreeEngine):

    EngineClass = LxmlEngine

class TestTwoPhaseElementTreeEngine(TestElementTreeEngine):

    EngineClass = TwoPhaseElementTreeEngine


def engines2test_case():
    res = dict()
    for klass in globals().values():
        if type(klass) != type(EngineTestCase):
            continue
        engine_class = getattr(klass, 'EngineClass', None)
        if engine_class is not None:
            res[engine_class] = klass
    return res


def test_suite():
    suite = unittest.TestSuite()

    for PageEngine in (ElementTreeEngine, TwoPhaseElementTreeEngine):#, LxmlEngine):
        suite.addTest(unittest.makeSuite(engines2test_case()[PageEngine]))
        for test_file in ('engine/portlets_merging.txt',
                          'engine/heads_merging.txt'):
            suite.addTest(
                doctest.DocFileTest(test_file,
                                    package='Products.CPSDesignerThemes',
                                    optionflags=doctest.ELLIPSIS,
                                    globs=dict(PageEngine=PageEngine)))
    return suite
