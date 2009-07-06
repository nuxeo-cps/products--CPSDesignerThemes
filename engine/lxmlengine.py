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

import logging
from copy import deepcopy
from StringIO import StringIO # use TAL's faster StringIO ?

from lxml import html, etree

from zope.interface import implements

from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import NS_URI, NS_XHTML, ENCODING
from Products.CPSDesignerThemes.utils import rewrite_uri
from base import BaseEngine
from twophase import TwoPhaseEngine
from etreeengine import ElementTreeEngine
from etreeengine import PORTLET_ATTR
from etreeengine import LINK_HTML_DOCUMENTS
from etreeengine import CSS_LINKS_RE

NAMESPACES = dict(cps=NS_URI, xhtml=NS_XHTML)

class LxmlEngine(ElementTreeEngine):
    """An engine based on lxml.html
    """

    implements(IThemeEngine)

    logger = logging.getLogger(
        'Products.CPSDesignerThemes.engine.LxmlEtreeEngine')

    XML_HEADER = '<?xml version="1.0" encoding="%s"?>' % ENCODING

    def __init__(self, html_file=None, theme_base_uri='', page_uri='',
                 cps_base_url=''):
        self.tree = etree.parse(html_file)
        self.root = self.tree.getroot()
        BaseEngine.__init__(self, theme_base_uri=theme_base_uri,
                            page_uri=page_uri, cps_base_url=cps_base_url)


    #
    # Internal engine API implementation. For docstrings, see BaseEngine
    #

    @classmethod
    def findByAttribute(self, elt, attr_name, value=None):
        if value is None:
            # need an iterable, iterfind misses slot
            return (e for e in elt.findall('.//*[@%s]' % attr_name))
        return (e for e in elt.iterfind('.//*[@%s]' % attr_name)
                if e.get(attr_name) == value)

    @classmethod
    def parseFragment(self, content, enclosing=None):
        parser = etree.XMLParser()
        parser.feed(self.XML_HEADER)

        # We always need an enclosing tag to bear the xhtml namespace
        if enclosing is None:
            enclosing = 'default-document'
            remove_enclosing = True
        else:
            remove_enclosing = False
        parser.feed('<%s xmlns="%s">' % (enclosing, NS_XHTML))
        parser.feed(content)
        parser.feed("</%s>" % enclosing)

        try:
            parsed = parser.close()
        except SyntaxError, e:
            self.logger.error("Problematic xml snippet:\n", content)

        # avoid 'and/or' notation (gives a future warning because of bool eval)
        if remove_enclosing:
            return parsed[0]
        return parsed

    def _rewriteElementUris(self, from_elt, rewriter_func):
        for tag, attr in LINK_HTML_DOCUMENTS.items():
            for elt in from_elt.iterfind('.//{%s}%s' % (NS_XHTML, tag)):
                uri = elt.attrib[attr]
                try:
                    new_uri = rewriter_func(uri=uri,
                        absolute_base=self.theme_base_uri,
                        referer_uri=self.page_uri,
                        cps_base_url=self.cps_base_url)
                except KeyError:
                    raise ValueError(
                        "Missing attribute %s on <%s> element" % (attr, tag))
                elt.attrib[attr] = new_uri
                self.logger.debug("URI Rewrite %s -> %s" % (uri, new_uri))
        for style_elt in from_elt.iterfind('.//{%s}%s' % (NS_XHTML, 'style')):
            if style_elt.text:
                style_elt.text = CSS_LINKS_RE.sub(self.styleAtImportRewriteUri,
                                                  style_elt.text)

    def rewriteUris(self, rewriter_func=None):
        """implementation: lxml.html has helpers for this.

        For now the only difference with ET is the use of iterfind.
        findall() on lxml returns a list. Is that really a big matter for perf?
        """
        if rewriter_func is None:
            rewriter_func=rewrite_uri
        self._rewriteElementUris(self.root, rewriter_func)

        for comment in self.root.iter(tag=etree.Comment):
            if comment.text.startswith('[if'):
                t = comment.text
                # TODO: error handling
                start_cond_index = t.find(']')+2
                end_cond_index = t.find('<![endif]')
                fragment = t[start_cond_index:end_cond_index]
                elt = self.parseFragment(fragment, enclosing='msie-cond')
                self._rewriteElementUris(elt, rewriter_func)
                s = elt.text
                for e in elt:
                    s += etree.tostring(e).replace('xmlns="%s"' % NS_XHTML, '')
                    if e.tail:
                        s += e.tail
                comment.text = t[:start_cond_index] + s + t[end_cond_index:]


    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        lxml implementation leverages reference to parent any element has
        """

        frames = tuple(self.findByAttribute(slot, PORTLET_ATTR, value='frame'))
        if not frames:
            raise ValueError("No frame in the slot")

        frame = frames[0]
        frame_parent = frame.getparent()
        del frame.attrib[PORTLET_ATTR]

        for elt in frames:
            elt.getparent().remove(frame)

        return frame_parent, frame

    @classmethod
    def _accumulateJavaScript(self, src, target):
        """Move all JS script calls from src to target."""
        for i, child in enumerate(src):
            if child.tag == '{%s}script' % NS_XHTML:
                target.append(child) # will remove from source

    def serialize(self):
        self.protectEmptyElements('script', 'div', 'textarea')

        out = StringIO()
        self.tree.write(out)
        # XXX GR couldn't find a way to change the nsmap
        # to prevent now useless declaration
        return out.getvalue().replace('xmlns:cps="%s"' % NS_URI, '', 1)

    @classmethod
    def makeSimpleElement(self, tag, content=None):
        element = etree.Element(tag)
        if content:
            element.text = content
        return element

class TwoPhaseLxmlEngine(TwoPhaseEngine, LxmlEngine):
    """Two phase version"""

