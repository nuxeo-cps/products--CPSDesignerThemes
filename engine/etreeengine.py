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
from cStringIO import StringIO
from urlparse import urlparse

try:
    import cElementTree as ET
    C_ELEMENT_TREE = True
    # TODO this warning must appear only if cElementTree is really used
    # (not for subclasses like LxmlEngine)
    logger.warn("On cElementTree, apply cElementtree.c.patch to get rid of "
                "issues with entities.")

except ImportError:
    C_ELEMENT_TREE = False
    try:
        import elementtree.ElementTree as ET
        ELEMENT_TREE_PRESENT = True
    except ImportError:
        ELEMENT_TREE_PRESENT = False

if C_ELEMENT_TREE or ELEMENT_TREE_PRESENT:
	from elementtree import ElementInclude # XInclude support

import htmlentitydefs

from zope.interface import implements

from Products.CMFCore.utils import getToolByName

from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import (NS_URI,
                                                  NS_XHTML,
                                                  NS_XINCLUDE,
                                                  NS_XML)
from Products.CPSDesignerThemes.constants import XML_HEADER, XML_HEADER_NO_ENC
from Products.CPSDesignerThemes.constants import BOOLEAN_OPTIONS
from Products.CPSDesignerThemes.utils import rewrite_uri
from base import BaseEngine
from exceptions import FragmentParseError

import patchetree
from twophase import TwoPhaseEngine

def ns_prefix(name):
    return '{%s}%s' % (NS_URI, name)

HEAD = '{%s}head' % NS_XHTML
BODY = '{%s}body' % NS_XHTML
META = '{%s}meta' % NS_XHTML

OPTIONS = ns_prefix('options')

PORTLET_ATTR = ns_prefix('portlet')
URI_ATTR = ns_prefix('uri')
PORTLET_TITLE_I18N_ATTR = ns_prefix('translate-titles')
SLOT_ATTR = ns_prefix('slot')
ISOLATED_PORTLET_ATTR = ns_prefix('isolated-portlet')
MAIN_CONTENT_ATTR = ns_prefix('main-content')
REMOVE_ATTR = ns_prefix('remove')
METAL_HEAD_SLOTS = ( # the passed slots that end up in the <head> element
    'base', 'head_slot', 'style_slot', 'javascript_head_slot')

#TODO move to constants
LINK_HTML_DOCUMENTS = {'img' : 'src',
                       'link'    : 'href',
                       'object'  : 'data',
                       'param' : 'value',
                       'script' : 'src',
                       'a': 'href',
                       'area' : 'href',
                       }

HTML_ENTITIES = dict((n, unichr(v))
                     for n, v in htmlentitydefs.name2codepoint.items())

# GR Duplicated from themecontainer.StyleSheet
# another sign that rewriting should be handled by containers
CSS_LINKS_RE = re.compile(r'url\((.*)\)')


class ElementTreeEngine(BaseEngine):
    """An engine based on ElementTree API

    http://effbot.org/zone/element-index.htm

    There's room for optimisation, like
    avoiding parsing the templates all over again. Therefore, in the future
    a given engine could persist in memory and be used for several
    context/request pairs.
    """

    implements(IThemeEngine)

    def readTheme(self, html_file):
        """Parse the theme and inits the 'tree' and 'root' attributes"""
        tree = self.tree = ET.parse(html_file)
        root = self.root = self.tree.getroot()
	self.rewriteXiUris()
	ElementInclude.include(root)
        self.cleanXmlBaseAttrs()

    #
    # Internal engine API implementation. For docstrings, see BaseEngine
    #

    def parseOptions(self):
        return self._parseOptions(self.root)

    @classmethod
    def _parseOptions(self, root):
        for elt in root.getchildren():
            if elt.tag == OPTIONS:
                break
            if elt.tag == HEAD:
                return {}
        else:
            return {}

        root.remove(elt)
        options = dict(elt.attrib)
        for k in options:
            if k in BOOLEAN_OPTIONS:
                v = options[k].strip().upper()
                if v == 'TRUE':
                    options[k] = True
                elif v == 'FALSE':
                    options[k] = False
                else:
                    raise ValueError("Invalid option : '%s'" % options[k])

        return options

    @classmethod
    def parseOptionsFile(cls, xml_file):
        tree = ET.parse(xml_file)
        return cls._parseOptions(tree.getroot())

    def removeElement(self, elt):
        # In plain ElementTree, one cannot access parent from element.
        for parent in self.root.findall('.//*'):
            if elt in parent:
                parent.remove(elt)
                break

    def getHtmlElementsByName(self, name):
        return self.root.findall('.//{%s}%s' % (NS_XHTML, name))

    @classmethod
    def findByAttribute(self, elt, attr_name, value=None, with_parent=False):
        """Shameless implementation of search by attribute.

        Workaround the fact that attribute xpath expressions are supported
        with elementtree >= 1.3, which is unreleased and unavailable for me."""

        presence = value is None
        all = elt.findall('.//*')

        if not with_parent:
            if presence:
                return (e for e in all if attr_name in e.keys())
            else:
                return (e for e in all if e.get(attr_name) == value)

        return self._findByAttributeWithParent(all, attr_name,
                                               value=value, presence=presence)

    @classmethod
    def _findByAttributeWithParent(self, elts, attr_name,
                                   value=None, presence=False):
        # XXX unsatisfying complexity, not so easy to fix
        for parent in elts:
            for child in parent:
                if presence:
                    if attr_name in child.keys():
                        yield (parent, child)
                elif child.get(attr_name) == value:
                    yield (parent, child)

    #
    # Inclusion methods for dynamical content (main content and portlets)
    #

    def appendFragment(self, elt, fragment, is_element=False):
        """Include a fragment in some element.
        If is_element is True, the fragment is assumed to be a unique, parseable
        XML element."""
        if is_element:
            enclosing = None
        else:
            enclosing = 'include-fragment'

        try:
            parsed = self.parseFragment(fragment, enclosing=enclosing,
                                        encoding=self.encoding)
        except FragmentParseError:
            return
        elt.text = parsed.text
        for child in parsed:
            elt.append(child)

    def insertFragment(self, index, elt, fragment, is_element=False):
        """Include a fragment in some element.
        If is_element is True, the fragment is assumed to be a unique, parseable
        XML element."""
        if is_element:
            enclosing = None
        else:
            enclosing = 'include-fragment'
            raise NotImplementedError

        try:
            elt.insert(index, self.parseFragment(fragment, enclosing=enclosing,
                                                 encoding=self.encoding))
        except FragmentParseError:
            pass

    #
    # Internal engine API implementation. For docstrings, see BaseEngine
    #

    def styleAtImportRewriteUri(self, match_obj):
        abs_rewrite = self.uri_absolute_path_rewrite
        return 'url(%s)' % rewrite_uri(uri=match_obj.group(1),
                                       absolute_base=self.theme_base_uri,
                                       referer_uri=self.page_uri,
                                       cps_base_url=self.cps_base_url,
                                       absolute_rewrite=abs_rewrite)

    def _rewriteElementUri(self, elt, attr, rewriter_func):
        """Rewrite the URI for an attribute of an element."""
        uri = elt.attrib.get(attr)
        keep = elt.attrib.pop(URI_ATTR, '').strip().lower()
        if uri is None or keep == 'keep':
            return
        try:
            new_uri = rewriter_func(uri=uri,
                absolute_base=self.theme_base_uri,
                referer_uri=self.page_uri,
                cps_base_url=self.cps_base_url,
                absolute_rewrite= self.uri_absolute_path_rewrite)
        except KeyError:
            raise ValueError(
                "Missing attribute %s on <%s> element" % (attr, tag))
        elt.attrib[attr] = new_uri

    def rewriteUris(self, rewriter_func=None):
        if rewriter_func is None:
            rewriter_func=rewrite_uri
        abs_rewrite = self.uri_absolute_path_rewrite
        for tag, attr in LINK_HTML_DOCUMENTS.items():
            for elt in self.root.findall('.//{%s}%s' % (NS_XHTML, tag)):
                self._rewriteElementUri(elt, attr, rewriter_func)
        for style_elt in self.root.findall('.//{%s}%s' % (NS_XHTML, 'style')):
            if style_elt.text:
                style_elt.text = CSS_LINKS_RE.sub(self.styleAtImportRewriteUri,
                                              style_elt.text)

    def getStyleSheetUris(self, kind='rel_abs_path'):
        """Get stylesheet URIs, filtered by kind

        kind can be:
           - 'rel_abs_path'
           - 'rel_rel_path'
           - 'all'
        For the first two kinds, only path relative URIs (no authority, see
        RFC2396) are selected. The difference lies in the path being absolute
        or relative.
        """

        res = []
        for link_elt in self.root.findall(
            './{%s}head/{%s}link' % (NS_XHTML, NS_XHTML)):
            attr = link_elt.attrib
            if attr.get('rel', '').lower() == 'stylesheet':
                uri = attr['href']
                scheme, authority, path  = urlparse(uri)[:3]
                if kind.startswith('rel_'):
                    if scheme or authority:
                        continue
                    if (kind != 'rel_rel_path') ^ path.startswith('/'):
                        continue
                res.append(uri)
        return res

    def rewriteXiUris(self):
        for elt in self.root.findall('.//{%s}include' % NS_XINCLUDE):
            uri = elt.attrib.get('href')
            if uri is not None:
                elt.attrib['href'] = self.container.rewriteXincludeUri(
                    uri, self.page_uri, absolute_for=self.theme_name)

    def cleanXmlBaseAttrs(self):
        base_attr = '{%s}base' % NS_XML
        for elt in self.findByAttribute(self.root, base_attr):
            del elt.attrib[base_attr]

    def extractSlotElements(self):
        return ((slot.attrib.pop(SLOT_ATTR), slot)
                for slot in self.findByAttribute(self.root, SLOT_ATTR))

    def extractIsolatedPortletElements(self):
        return ((ptl.attrib.pop(ISOLATED_PORTLET_ATTR), ptl, parent)
                for parent, ptl in self.findByAttribute(self.root,
                                                        ISOLATED_PORTLET_ATTR,
                                                        with_parent=True))
    @classmethod
    def parseHeadBody(self, pt_output, encoding):
        parsed = self.parseFragment(pt_output, enclosing='default-document',
                                    encoding=encoding)
        return (parsed.find('.//' + elt) for elt in (HEAD, BODY))

    @classmethod
    def parseFragment(self, content, enclosing=None, encoding=None):
        parser = ET.XMLParser()
        # entity declarations and voodoo to make it work
        if not C_ELEMENT_TREE:
            parser.entity = HTML_ENTITIES # avoid copying all over
            # unlock entity problems (pfeew)
            # important: relies on the provided patch for celementree
            parser.parser.UseForeignDTD()
        else:
            parser.entity.update(HTML_ENTITIES)

        if encoding is None:
            parser.feed(XML_HEADER_NO_ENC)
        else:
            parser.feed(XML_HEADER % encoding)

        # We always need an enclosing tag to bear the xhtml namespace
        if enclosing is None:
            enclosing = 'default-document'
            remove_enclosing = True
        else:
            remove_enclosing = False
        try:
            parser.feed('<%s xmlns="%s">' % (enclosing, NS_XHTML))
            parser.feed(content)
            parser.feed("</%s>" % enclosing)
            parsed = parser.close()
        except SyntaxError, e:
            self.logger.error("Problematic xml fragment:\n%s\n", content)
            raise FragmentParseError()

        if remove_enclosing:
            return parsed[0]
        return parsed

    def mergeBodyElement(self, from_cps=None, body_content=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        body = self.tree.find(BODY)
        for k, v in from_cps.attrib.items():
            if k not in body.attrib:
                body.attrib[k] = v
        if body_content is not None:
            # writing directly in body, meaning to override it !
            # keeping the merged attributes, though
            attrib = dict(body.attrib)
            body.clear()
            body.attrib.update(attrib)
            self.appendFragment(body, body_content)

    def setLanguageAttrs(self, lang):
        attrib = self.root.attrib
        attrib['lang'] = attrib['{%s}%s' % (NS_XML, 'lang')] = lang

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

    @classmethod
    def _cutMsieConditionals(self, elt, keep=False):
        """Extract MSIE conditional statements from given element's toplevel.

        Return the conditional statements, as a bunch of comments in an
        enclosing <msie-cond> element."""

        # no support for comments parsing in ElementTree. Subclasses can do
        # better
        return

    def fixMetaElements(self, head):
        encoding = self.encoding.upper()
        ctype = None
        for meta in head.findall(META):
            attrib = meta.attrib
            heq = attrib.get('http-equiv')
            if heq is not None and heq.lower() == 'content-type':
                if ctype is not None: # not the first one, drop it
                    head.remove(meta)
                else:
                    ctype = meta

        # content-type
        if ctype is None:
            ctype = self.parseFragment('<meta http-equiv="Content-Type" />')
            head.insert(0, ctype)

        ctype.attrib['content'] = 'text/html; charset=%s' % encoding

        # engine
        head.insert(0, self.parseFragment(
            '<meta name="generator" content="CPSDesignerThemes" />'))

    @classmethod
    def mergeTitle(self, theme_head, head_elts=()):
        """Replace the <title> from theme_head by the first found in head_elts.

        If no <title> is found in theme_head, nothing is done.
        If a <title> is found in one of head_elts, it is removed.
        """

        # implementation avoids xpath and cut/paste of elements
        # to work the same in elementtree and lxml
        tag = '{%s}%s' % (NS_XHTML, 'title')

        for title_elt in theme_head.getchildren():
            if title_elt.tag == tag:
                break
        else:
            return

        for helt in head_elts:
            if helt is None:
                continue

            # find <title> in helt, and don't stay in a loop, for we'll remove
            # the one we may find.
            for elt in helt:
                if elt.tag == tag:
                    title_elt.text = elt.text
                    helt.remove(elt)
                    return


    def mergeHeads(self, head_content='', cps_global=None):
        """See base class for docstring."""

        in_theme = self.tree.find(HEAD)
        parsed = self.parseFragment(head_content, enclosing='head',
                                    encoding=self.encoding)

        self.mergeTitle(in_theme, (parsed, cps_global))

        js_acc = self.makeSimpleElement('js-acc')
        self._accumulateJavaScript(in_theme, js_acc)
        msie_cond = self._cutMsieConditionals(in_theme)

        if cps_global is not None:
            self._accumulateJavaScript(cps_global, js_acc)
            if msie_cond is not None:
                self._cutMsieConditionals(cps_global)
            offset = self._mergeElement(len(in_theme), in_theme, cps_global)

        self._accumulateJavaScript(parsed, js_acc)
        if msie_cond is not None:
            self._cutMsieConditionals(parsed)

        # the same ordering as what CPS header_lib_header does
        self._mergeElement(len(in_theme), in_theme, parsed)

        self._mergeElement(len(in_theme), in_theme, js_acc)
        # Put theme MSIE conditionals at the end for precedence
        if msie_cond is not None:
            self._mergeElement(len(in_theme), in_theme, msie_cond)

        self.fixMetaElements(in_theme)

    def renderMainContent(self, main_content):
        try:
            main_elt = self.findByAttribute(self.root, MAIN_CONTENT_ATTR).next()
        except StopIteration:
            return

        if not main_content:
            self.removeElement(main_elt)
            return

        # cleaning up
        del main_elt.attrib[MAIN_CONTENT_ATTR]
        for child in main_elt:
            main_elt.remove(child)

        self.appendFragment(main_elt, main_content, is_element=False)

    @classmethod
    def isPortletTitleI18n(self, slot):
        return bool(slot.attrib.pop(PORTLET_TITLE_I18N_ATTR, None))

    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        Sibling frames (sibling elements bearing 'cps:frame' attribute)
        are tolerated as a convenience for web designers wanting to check
        their output with several portlets TODO: move this to general doc."""

        frame = None
        for child in slot:
            if child.get(PORTLET_ATTR) == 'frame':
                if frame is None:
                    del child.attrib[PORTLET_ATTR]
                    frame = child
                    frame_parent = slot
                slot.remove(child)

        if frame is None:
            # 
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

    def mergePortlets(self, frame_parent, frame, portlets_rendered,
                      additional_css=True):
        one_done = False
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
                    self.insertFragment(0, body_elt, body, is_element=True)
                else:
                    parent, index = self.findParent(body_elt, inside=ptl_elt)
                    del parent[index]
                    self.insertFragment(index, parent, body, is_element=True)

            remove = ptl_elt.attrib.pop(REMOVE_ATTR, None)
            if not remove:
                frame_parent.append(ptl_elt)
            else: # XXX couldn't this leverage insertFragment, too ?
                if len(frame_parent):
                    # the frame parent already has children
                    last = frame_parent[-1]
                    if last.tail is None:
                        last.tail = ''
                    last.tail += ptl_elt.text
                else:
                    frame_parent.text += ptl_elt.text
                for elt in ptl_elt:
                    frame_parent.append(elt)
                if ptl_elt.tail is not None:
                    if elt.tail is None:
                        elt.tail = ptl_elt.tail
                    else:
                        elt.tail += ptl_elt.tail
            if not one_done:
                if additional_css:
                    self.addCssClass(ptl_elt, 'first_in_slot')
                one_done = True

        if one_done and additional_css:
            self.addCssClass(ptl_elt, 'last_in_slot')

    def mergePortletsNoFrame(self, slot_elt, portlets_rendered, **kw):
        """Merge the portlets in the slot, without frames

        portlets_rendered is a pair (title, body).
        Implementation detail: insertion of a frame element in the tree, with
        the slot contents copied in there. Since the lack of frame is expected
        to be actually the most common case, it may be better for performance
        to do it the other way round and have mergePortlets (with frames) call
        this method.
        """

        # Do as if there had been a frame (with cps:remove=true)
        frame = self.makeSimpleElement('temp')
        frame.attrib[PORTLET_ATTR] = 'frame'
        frame.attrib[REMOVE_ATTR] = 'true'
        frame.tail = frame.text = ''

        for child in slot_elt.getchildren():
            slot_elt.remove(child)
            frame.append(child)
        self.mergePortlets(slot_elt, frame, portlets_rendered, **kw)



    @classmethod
    def addCssClass(cls, elt, css_class):
        if 'class' in elt.attrib:
            elt.attrib['class'] += ' ' + css_class
        else:
            elt.attrib['class'] = css_class

    def mergeIsolatedPortlet(self, elt, portlet_rendered, parent):
        frame_parent, frame = self.extractSlotFrame(elt)
        frame_remove = frame.get(REMOVE_ATTR) # now to avoid side-effects
        self.mergePortlets(frame_parent, frame, (portlet_rendered,),
                           additional_css=False)
        if elt.attrib.pop(REMOVE_ATTR, False):
            # XXX make this a generic skipElement method
            i = parent.getchildren().index(elt)
            parent.remove(elt)
            if i == 0:
                parent.text = elt.text
            else:
                prev = parent[i-1]
                s = prev.text or '' # could be None
                s += elt.text
                prev.text = s
            for j, child in enumerate(elt.getchildren()):
                parent.insert(i+j, child)

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
        self.tree.write(out, default_namespace=NS_XHTML,
                        encoding=self.encoding)
        ser = self.stripNameSpaces(out.getvalue())
	if ser.startswith('<?xml'): # no need to strip, lib produces valid XML
	    end = ser.find('?>')
            ser = ser[end+2:].strip()	
	return ser

    def dumpElement(self, elt, encoding=None):
        tree = ET.ElementTree(elt)
        out = StringIO()
        tree.write(out, default_namespace=NS_XHTML, encoding=self.encoding)
        return out.getvalue()

    @classmethod
    def makeSimpleElement(self, tag, content=None):
        """Useful to avoid code duplication and over-complicated inheritances.
        """
        element = ET.Element(tag)
        if content:
            element.text = content
        return element

class TwoPhaseElementTreeEngine(TwoPhaseEngine, ElementTreeEngine):
    """Two phase version"""



