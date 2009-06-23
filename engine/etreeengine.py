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
logger = logging.getLogger(
        'Products.CPSDesignerThemes.engine.ElementTreeEngine')

import re
from copy import deepcopy
from StringIO import StringIO # use TAL's faster StringIO ?

try:
    import cElementTree as ET
    C_ELEMENT_TREE = True
    logger.warn("On cElementTree, apply cElementtree.c.patch to get rid of "
                "issues with entities.")

except ImportError:
    import elementtree.ElementTree as ET
    C_ELEMENT_TREE = False

import patchetree

import htmlentitydefs

from zope.interface import implements

from Products.CMFCore.utils import getToolByName

from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import NS_URI, NS_XHTML, ENCODING
from Products.CPSDesignerThemes.utils import rewrite_uri
from base import BaseEngine

def ns_prefix(name):
    return '{%s}%s' % (NS_URI, name)

HEAD = '{%s}head' % NS_XHTML
BODY = '{%s}body' % NS_XHTML

PORTLET_ATTR = ns_prefix('portlet')
SLOT_ATTR = ns_prefix('slot')
ISOLATED_PORTLET_ATTR = ns_prefix('isolated-portlet')
MAIN_CONTENT_ATTR = ns_prefix('main-content')
REMOVE_ATTR = ns_prefix('remove')
METAL_HEAD_SLOTS = ( # the passed slots that end up in the <head> element
    'base', 'head_slot', 'style_slot', 'javascript_head_slot')

LINK_HTML_DOCUMENTS = {'img' : 'src',
                       'link'    : 'href',
                       'object'  : 'data',
                       'param' : 'value',
                       'script' : 'src',
                       'a': 'href',
                       }

HTML_ENTITIES = dict((n, unichr(v))
                     for n, v in htmlentitydefs.name2codepoint.items())

# GR Duplicated from themecontainer.StyleSheet
CSS_LINKS_RE = re.compile(r'url\((.*)\)')


class ElementTreeEngine(BaseEngine):
    """An engine based on ElementTree API

    http://effbot.org/zone/element-index.htm
    GR: can't afford the effort to build lxml on my box.

    This is a starting point implementation. XML format is still
    likely to change at this point. There's room for optimisation, like
    avoiding parsing the templates all over again. Therefore, in the future
    a given engine could persist in memory and be used for several
    context/request pairs.

    On the other hand, this is already really fast.
    """

    implements(IThemeEngine)

    XML_HEADER = '<?xml version="1.0" encoding="%s"?>' % ENCODING

    def __init__(self, html_file=None, theme_base_uri='', page_uri='', **kw):
        self.tree = ET.parse(html_file)

        self.root = self.tree.getroot()
        BaseEngine.__init__(self, theme_base_uri=theme_base_uri,
                            page_uri=page_uri, **kw)

    @classmethod
    def findByAttribute(self, elt, attr_name, value=None):
        """Shameless implementation of search by attribute.

        Workaround the fact that attribute xpath expressions are supported
        with elementtree >= 1.3, which is unreleased and unavailable for me."""

        presence = value is None
        all = elt.findall('.//*')

        if presence:
            return (e for e in all if attr_name in e.keys())
        else:
            return (e for e in all if e.get(attr_name) == value)

    #
    # Internal engine API implementation. For docstrings, see BaseEngine
    #

    def styleAtImportRewriteUri(self, match_obj):
        return 'url(%s)' % rewrite_uri(uri=match_obj.group(1),
                                       absolute_base=self.theme_base_uri,
                                       referer_uri=self.page_uri,
                                       cps_base_url=self.cps_base_url)

    def rewriteUris(self):
        for tag, attr in LINK_HTML_DOCUMENTS.items():
            for elt in self.root.findall('.//{%s}%s' % (NS_XHTML, tag)):
                uri = elt.attrib[attr]
                try:
                    new_uri = rewrite_uri(uri=uri,
                                          absolute_base=self.theme_base_uri,
                                          referer_uri=self.page_uri,
                                          cps_base_url=self.cps_base_url)
                except KeyError:
                    raise ValueError(
                        "Missing attribute %s on <%s> element" % (attr, tag))
                elt.attrib[attr] = new_uri
                self.logger.debug("URI Rewrite %s -> %s" % (uri, new_uri))
        for style_elt in self.root.findall('.//{%s}%s' % (NS_XHTML, 'style')):
            if style_elt.text:
                style_elt.text = CSS_LINKS_RE.sub(self.styleAtImportRewriteUri,
                                              style_elt.text)
    def extractSlotElements(self):
        return ((slot.attrib.pop(SLOT_ATTR), slot)
                for slot in self.findByAttribute(self.root, SLOT_ATTR))

    def extractIsolatedPortletElements(self):
        return ((ptl.attrib.pop(ISOLATED_PORTLET_ATTR), ptl)
                for ptl in self.findByAttribute(self.root,
                                                ISOLATED_PORTLET_ATTR))

    @classmethod
    def parseHeadBody(self, pt_output):
        parsed = self.parseFragment(pt_output, enclosing='default-document')
        return (parsed.find('.//' + elt) for elt in (HEAD, BODY))

    @classmethod
    def parseFragment(self, content, enclosing=None):
        parser = ET.XMLParser()
        # entity declarations and voodoo to make it work
        if not C_ELEMENT_TREE:
            parser.entity = HTML_ENTITIES # avoid copying all over
            parser.parser.UseForeignDTD() # unlock entity problems (pfeew)
        else:
            parser.entity.update(HTML_ENTITIES)

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

        if remove_enclosing:
            return parsed[0]
        return parsed

    def mergeBodyElement(self, from_cps=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        body = self.tree.find(BODY)
        for k, v in from_cps.attrib.items():
            if k not in body.attrib:
                body.attrib[k] = v

    @classmethod
    def _appendTextBefore(self, offset, target, text):
        """Appends text to element before element at offset in target.

        If offset == 0, does it to target.text
        text can be None (use-case: comes from some element)
        """
        if not text:
            return

        if not offset:
            if not target.text:
                target.text = text
            else:
                target.text += text
            return

        # general case
        previous = target[offset-1]
        if not previous.tail:
            previous.tail = text
        else:
            previous.tail += text

    @classmethod
    def _mergeElement(self, offset, target, elt):
        """Insert the given element content at given offset in target.
        Takes care of subtleties with .text and .tail.
        Return a new offset for further merging."""

        if elt is None:
            return offset

        self._appendTextBefore(offset, target, elt.text)

        i = -1
        for i, child in enumerate(elt):
            target.insert(offset+i, child)
        return i+offset+1

    @classmethod
    def _accumulateJavaScript(self, src, target):
        """Move all JS script calls from src to target."""
        for i, child in enumerate(src):
            if child.tag == '{%s}script' % NS_XHTML:
                target.append(child)
                del src[i]

    def mergeHeads(self, head_content='', cps_global=None):
        """Merge the contextual head_content with cps' global and the theme's.

        For now, this is stupid concatenation.
        TODO: this should:
          - respect a natural ordering, and in particular put all
            JS scripts towards the end,
          - actually merge cps_global with the theme's head (we should first
            define a policy about this).
        """
        js_acc = ET.Element('js-acc')

        in_theme = self.tree.find(HEAD)
        self._accumulateJavaScript(in_theme, js_acc)

        parsed = self.parseFragment(head_content, enclosing='head')
        self._accumulateJavaScript(parsed, js_acc)

        if cps_global is not None:
            self._accumulateJavaScript(cps_global, js_acc)
            offset = self._mergeElement(len(in_theme), in_theme, cps_global)

        # the same ordering as what CPS header_lib_header does
        self._mergeElement(len(in_theme), in_theme, parsed)

        self._mergeElement(len(in_theme), in_theme, js_acc)

    def renderMainContent(self, main_content):
        try:
            main_elt = self.findByAttribute(self.root, MAIN_CONTENT_ATTR).next()
        except StopIteration:
            return

        # cleaning up
        del main_elt.attrib[MAIN_CONTENT_ATTR]
        for child in main_elt:
            main_elt.remove(child)

        parsed_main = self.parseFragment(main_content, enclosing='main-content')
        main_elt.text = parsed_main.text
        for child in parsed_main:
            main_elt.append(child)

    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        Sibling frames (elements bearing 'cps:frame' attribute) are tolerated
        as a convenience for web designers wanting to check their output
        with several portlets TODO: move this to general doc."""

        frame = None
        for child in slot:
            if child.get(PORTLET_ATTR) == 'frame':
                if frame is None:
                    del child.attrib[PORTLET_ATTR]
                    frame = child
                    frame_parent = slot
                slot.remove(child)
        if frame is None:
            # same below
            # XXX awful style
            for elt in slot.findall('.//*'):
                for child in elt:
                    if child.get(PORTLET_ATTR) == 'frame':
                        if frame is None:
                            frame = child
                        elt.remove(child)
                        break
                else:
                    continue
            frame_parent = elt
        return frame_parent, frame

    @classmethod
    def findIndex(self, parent, elt):
        """Return the index of elt in parent, or -1"""
        try:
            return list(parent).index(elt)
        except ValueError:
            return -1

    @classmethod
    def findParent(self, elt, inside=None):
        """Starting from 'inside', find the parent of elt, and the index.

        raise KeyError if not found.
        """
        if inside is None:
            raise ValueError("inside must be specified")

        # trying directly in the element inside, because the findall call
        # below does not yield it
        i = self.findIndex(inside, elt)
        if i != -1:
            return inside, i
        try:
            indexes = ((self.findIndex(e, elt),e)
                       for e in inside.findall('.//*'))
            return ((e, i) for i, e in indexes if i != -1).next()
        except StopIteration:
            raise KeyError

    @classmethod
    def mergePortlets(self, frame_parent, frame, portlets_rendered):
        for title, body in portlets_rendered:
            if not body:
                continue

            ptl_elt = deepcopy(frame)

            elts = tuple(self.findByAttribute(ptl_elt, PORTLET_ATTR,
                                           value='title'))
            if elts:
                title_elt = elts[0]
                del title_elt.attrib[PORTLET_ATTR]
                if not title_elt.attrib.pop(REMOVE_ATTR, None):
                    title_elt.text = title
                else:
                    parent, index = self.findParent(title_elt, inside=ptl_elt)
                    if index == 0:
                        if parent.text is None:
                            parent.text = ''
                        parent.text += title
                    else:
                        elder = parent[index-1]
                        if elder.tail is None:
                            elder.tail = ''
                        elder.tail += title
                    del parent[index]

            elts = tuple(self.findByAttribute(ptl_elt, PORTLET_ATTR,
                                             value='body'))

            if elts:
                body_elt = elts[0]
                if not body_elt.attrib.pop(REMOVE_ATTR, None):
                    del body_elt.attrib[PORTLET_ATTR]
                    body_elt.text = ''
                    for child in body_elt:
                        body_elt.remove(child)
                    body_elt.append(self.parseFragment(body))
                else:
                    parent, index = self.findParent(body_elt, inside=ptl_elt)
                    del parent[index]
                    parent.insert(index, self.parseFragment(body))

            remove = ptl_elt.attrib.pop(REMOVE_ATTR, None)
            if not remove:
                frame_parent.append(ptl_elt)
            else:
                if len(frame_parent):
                    # the frame parent already has children
                    frame_parent[-1].tail += ptl_elt.text
                else:
                    frame_parent.text += ptl_elt.text
                for elt in ptl_elt:
                    frame_parent.append(elt)
                elt.tail += ptl_elt.tail

    def protectEmptyElements(self, *tags):
        # maybe lxml can do this better
        # there's also a recent option in ElementTree, but not in my version
        for tag in tags:
            for elt in self.root.findall('.//{%s}%s' % (NS_XHTML, tag)):
                if not elt.text:
                    elt.text = ' '

    def serialize(self):
        self.protectEmptyElements('script', 'div', 'textarea')

        out = StringIO()
        self.tree.write(out, default_namespace=NS_XHTML)
        return out.getvalue()

    @classmethod
    def dumpElement(self, elt):
        tree = ET.ElementTree(elt)
        out = StringIO()
        tree.write(out, default_namespace=NS_XHTML)
        return out.getvalue()
