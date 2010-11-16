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
from Products.CPSDesignerThemes.engine.lxmlengine import (
    LxmlEngine,
    TwoPhaseLxmlEngine)
from Products.CPSDesignerThemes.constants import NS_XHTML
from Products.CPSDesignerThemes.engine.exceptions import FragmentParseError
from Products.CPSDesignerThemes.themecontainer import FSThemeContainer

THEMES_PATH = os.path.join(INSTANCE_HOME, 'Products', 'CPSDesignerThemes',
                           'tests')
def getThemesPath():
    return THEMES_PATH

PORTLET1 = ('portlet1', '<ul id="portlet1"><li>foo</li></ul>')

WT_REGEXP = re.compile(r'[\n ]*')

def get_engine(EngineClass, theme, page='index.html', cps_base_url=None):
    container = FSThemeContainer('cont_id')
    container.getFSPath = getThemesPath
    f = open(os.path.join(THEMES_PATH, theme, page), 'r')
    return EngineClass(html_file=f, container=container,
                       theme_base_uri='/thm_base', encoding='iso-8859-15',
                       theme_name=theme, page_name=page,
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

    def test_srcHref(self):
        # See #1972
        engine = self.getEngine('theme1', 'no-src-href.html')

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
        if not hasattr(self.EngineClass, 'secondPhase'):
            expected = expected.replace('&nbsp;', '\xa0')
        # skip declaration: not what is being tested
        rendered = re.sub(r'<\?xml.*\?>', '', rendered)
        self.assertEquals(rendered, expected)

    def test_uri_rewrite(self):
        # engine must accept a missing cps:portlet="body"
        engine = self.getEngine('theme1', page='uris.html')
        img = self.findTag(engine, 'img')
        self.assertEquals(img.attrib['src'], '/thm_base/pretty.png')

    def test_parseFragment_invalid(self):
        # engine must not barf on invalid fragments but raise a proper exception
        engine = self.getEngine('theme1', page='uris.html')
        self.assertRaises(FragmentParseError, engine.parseFragment, '<div>')
        self.assertRaises(FragmentParseError, engine.parseFragment, '<div>',
                          enclosing='enclosing')

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

    def test_fixMetaElements(self):
        engine = self.getEngine('theme1', 'simple_slot.html')

        # don't break on other meta than http-equiv
        head = engine.parseFragment('<head> <meta generator="Me"/></head>')
        engine.fixMetaElements(head)


class TestLxmlEngine(TestElementTreeEngine):

    EngineClass = LxmlEngine

    def test_entities(self):
        """DISABLING:

        lxml has no support for entities in the absence of a DTD.
        serialized fragments with the DTD could be a problem.

        Two-phase engines don't mind, and the most critical source of entities
        is the dynamical content.

        TODO it seems that serializing a tree dumps the DTD,
        but that serializing its root does not, so that it wouldn't be a
        problem in theory. Now a strange thing happens with XMLParser API
        parsing a whole (DTD + fragment) works and lets the entity through,
        using feed() line by line does not. This is so erratic that I fear it
        to be system-dependent.
        """

    def test_entities_in_theme(self):
        """Not supported by ElementTree based engines yet."""
        engine = self.getEngine('theme1', 'entities.html')

class TestTwoPhaseElementTreeEngine(TestElementTreeEngine):

    EngineClass = TwoPhaseElementTreeEngine


class TestTwoPhaseLxmlEngine(TestLxmlEngine):

    EngineClass = TwoPhaseLxmlEngine


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

    for PageEngine in (ElementTreeEngine, TwoPhaseElementTreeEngine,
                       LxmlEngine, TwoPhaseLxmlEngine):
        suite.addTest(unittest.makeSuite(engines2test_case()[PageEngine]))
        for test_file in ('engine/portlets_merging.txt',
                          'engine/heads_merging.txt',
                          'engine/isolated_portlet.txt',
                          'engine/options.txt',
                          'engine/main_content_merging.txt',
                          'engine/xinclude.txt',
                          ):
            suite.addTest(
                doctest.DocFileTest(test_file,
                                    package='Products.CPSDesignerThemes',
                                    optionflags=doctest.ELLIPSIS,
                                    globs=dict(PageEngine=PageEngine)))

    suite.addTest(doctest.DocFileTest('engine/heads_merging_lxml.txt',
                                      package='Products.CPSDesignerThemes',
                                      optionflags=doctest.ELLIPSIS,
                                      globs=dict(PageEngine=LxmlEngine)))
    return suite
