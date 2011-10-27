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
import re

from copy import deepcopy
from cStringIO import StringIO

from zope.interface import implements

from Products.CMFCore.utils import getToolByName

from Products.CPSUtil.crashshield import shield_apply
from Products.CPSUtil.crashshield import CrashShieldException
from Products.CPSUtil import resourceregistry
from Products.CPSCore.utils import bhasattr
from Products.CPSPortlets.CPSPortlet import PORTLET_RESOURCE_CATEGORY
from Products.CPSDesignerThemes.interfaces import IThemeEngine
from Products.CPSDesignerThemes.constants import NS_XHTML
from Products.CPSDesignerThemes.utils import rewrite_uri

METAL_HEAD_SLOTS = ( # the passed slots that end up in the <head> element
    'base', 'head_slot', 'style_slot', 'javascript_head_slot')

class MainContentPortlet(object):
    """Simulates the Main Content Portlet for CPSSkins exported themes."""

    def __init__(self, portlet, main_content):
        self.portlet = portlet
        self.content = main_content

    def getId(self):
        return self.portlet.getId()

    def Title(self):
        return self.portlet.Title()

    def title_or_id(self):
        return self.portlet.title_or_id()

    def render_cache(self, **kw):
        return '<div id="%s">%s</div>' % (self.getId(), self.content)

def find_by_attribute(elt, attr_name, value=None):
    """For subclass."""

    raise NotImplementedError

def render_shield_portlet(portlet, context_obj=None):
    """Render the portlet within the crash shield.
    Take javascript needs into account.
    """
    try:
        __traceback_info__="portlet id: " + portlet.getId()
        rendered = shield_apply(portlet, 'render_cache',
                                context_obj=context_obj)
    except CrashShieldException:
        rendered = '<blink>!!!</blink>'
    return rendered.strip()

class BaseEngine(object):
    """Abstract base engine class

    All calls to XML libraries should be done from subclasses (engine actual
    implementations).
    Conversely, all CPS calls should come from here. An immediate benefit is
    that the subclasses can be tested with plain old unittest.
    """

    implements(IThemeEngine)

    logger = logging.getLogger(
        'Products.CPSDesignerThemes.engine.BaseEngine')

    def __init__(self, html_file=None, theme_base_uri='', page_uri='',
                 cps_base_url=None, encoding=None, container=None, lang='',
                 theme_name='', page_name=''):
        """Does all preprocessing that's independent from context & request.

        A freshly constructed IThemeEngine instance is a good candidate for
        caching : it can serve as template to be deepcopied for each request.
        TODO: refactor attributes that can be read on container
        """
        self.logger.debug("Engine : %s", self.__class__)
        self.container = container
        self.theme_base_uri = theme_base_uri
        self.page_uri = page_uri
        self.cps_base_url = cps_base_url
        # The engine object will be carried along, storing corresponding
        # theme and page names for various logging and/or user feedback.
        # theme names can also be used in XInclude URI rewriting
        self.page_name = page_name
        self.theme_name = theme_name
        if bhasattr(html_file, 'seek'):
            html_file.seek(0)
        self.readTheme(html_file)
        # this is from this class point of view both input (portlets) and
        # output (rendered html) encoding
        self.encoding = encoding
        self.options = options = self.parseOptions()
        self.uri_absolute_path_rewrite = options.get(
            'uri-absolute-path-rewrite', True)
        self.rewriteUris()
        if lang:
            self.setLanguageAttrs(lang)

    def renderCompat(self, metal_slots=None, pt_output='',
                     context=None, request=None):
        """Rendering method for compat mode.

        Receives the what the callers page templates of the main_template's
        master macro have put in the slots, and the main output of said macro.

        pt_output is supposed to be xml looking like this:
          <cpsdesigner-themes-compat>
            <head>...</head>
            <body onload="..."/>
          </cpsdesigner-themes-compat>

        This is used to reproduced what CPSSkins main template used to do
        (simplified extract):
          <head>
            <metal:block use-macro="here/header_lib_header/macros/header">
              <metal:block fill-slot="head_slot">
                <metal:block define-slot="head_slot"</metal:block>
              </metal:block>
            </metal:block>
          </head>

        The slot recording hack does not work for these nested macro calls,
        and it would be much trickier to do so.
        Therefore we have our main template render the part that's supposed to
        be called from there directly in the output, define the slots in the
        simplest manner near top level, and this method merges all of this."""

        head_element, body_element = self.parseHeadBody(pt_output,
                                                        self.encoding)
        head_content = '\n'.join((metal_slots.get(slot, '')
                                  for slot in METAL_HEAD_SLOTS))

        body_content = metal_slots.get('body')
        if body_content is not None:
            # caller of main_template writes directly in <body>
            # This would typically be a popup. Apply body directly.
            return self.renderSimpleBody(body_content=body_content,
                                         head_content=head_content,
                                         head_element=head_element,
                                         body_element=body_element,
                                         context=context, request=None)

        main_content = ''
        for slot in ('header', 'main', 'sub'):
            main_content += metal_slots.get(slot, '')

        return self.render(main_content=main_content,
                           head_element=head_element,
                           head_content=head_content,
                           body_element=body_element,
                           context=context, request=None)

    @classmethod
    def parseHeadBody(self, pt_output, encoding):
        """Return the head and body elements from an XML string fragment"""
        raise NotImplementedError

    @classmethod
    def parseFragment(self, content, enclosing=None):
        """Convert a string fragment to an xml tree

        If enclosing is None, it is assumed that the fragment has a root element
        otherwise one will be produced, as specified by 'enclosing'
        This is useful for some ZPT outputs.
        """
        raise NotImplementedError

    @classmethod
    def renderPortlets(self, portlets, context=None, request=None, i18n=False):
        if not i18n or context is None:
            def titleI18n(portlet):
                return portlet.title_or_id()
        else:
            mcat = getToolByName(context, 'translation_service')
            def titleI18n(portlet):
               return mcat(portlet.title_or_id())

        return ( (titleI18n(portlet),
                  render_shield_portlet(portlet, context_obj=context))
                 for portlet in portlets if portlet is not None)

    def renderSimpleBody(self, body_content='', head_content='',
                         body_element=None, head_element=None,
                         context=None, request=None):
        if body_element is not None:
            self.mergeBodyElement(from_cps=body_element,
                                  body_content=body_content)
        self.mergeHeads(head_content=head_content,
                        cps_global=head_element)

        return self.serialize()

    def mergeSlot(self, slot_elt, portlets, context=None, request=None,
                  additional_css=True, main_content=''):
        # in themes exported from CPSSkins, the main content
        # is supposed to be in a special portlet
        portlets = (portlet.portal_type == 'Main Content Portlet' and \
                    MainContentPortlet(portlet, main_content) or portlet
                    for portlet in portlets)

        frame_parent, frame = self.extractSlotFrame(slot_elt)
        rendered = self.renderPortlets(portlets,
                                       context=context, request=request,
                                       i18n=self.isPortletTitleI18n(slot_elt
                                                                    ))
        # dropping portlets with empty rendering
        rendered = [(title, body) for title, body in rendered if body]
        if not rendered:
            self.removeElement(slot_elt)
            return

        if frame is not None:
            self.mergePortlets(frame_parent, frame, rendered,
                               additional_css=additional_css)
        else:
            self.mergePortletsNoFrame(slot_elt, rendered,
                                      additional_css=additional_css)


    def render(self, main_content='', head_content='',
               body_element=None, head_element=None,
               context=None, request=None):
        """General rendering method.

        Supposed to be used for compat mode and direct mode."""

        ptool = getToolByName(context, 'portal_cpsportlets')

        # portlet slots
        for slot_name, slot_elt in self.extractSlotElements():
            portlets = ptool.getPortlets(context, slot_name)
            self.mergeSlot(slot_elt, portlets, main_content=main_content,
                           context=context, request=request)

        # isolated portlets
        for ptl_id, elt, parent in self.extractIsolatedPortletElements():
            portlet = ptool.getPortletById(ptl_id)
            portlet_rendered = self.renderPortlets([portlet], context=context,
                                                   request=request)
            try:
                self.mergeIsolatedPortlet(elt, portlet_rendered.next(), parent)
            except StopIteration:
                self.logger.warn("Could not find isolated portlet with id='%s'",
                                 ptl_id)
                parent.remove(elt)

        if body_element is not None:
            self.mergeBodyElement(from_cps=body_element)
        if main_content is not None:
            self.renderMainContent(main_content)
        head_content += resourceregistry.dump_category(
            context, PORTLET_RESOURCE_CATEGORY, base_url=self.cps_base_url)
        self.mergeHeads(head_content=head_content,
                        cps_global=head_element)

        return self.serialize()

    # Human translation: any amount of whitespace, 'xmlns', possibly followed
    # by ":prefix", equal sign,  simple or double quote, attribute value
    # (any sequence of char, non greedy), same quote as the first one.
    xmlns_re = re.compile(r'''\s*xmlns:?\w*=(?P<quote>['"]).*?(?P=quote)''')

    @classmethod
    def stripNameSpaces(cls, serialized):
        """Remove all unwanted namespace declarations.

        Problem found in the context of XInclude support (see #2152)
        Most XML processing libraries don't provide an easy way to do that
        because redundant xmlns declarations are valid and do no harm in the
        XML world. But in XHTML, the only  element that can have an xmlns
        declaration is the <html> document itself.

        Note that this also breaks XHTML potential for extensibility. We'll
        see for a smarter stripping if someone has a use-case someday.
        """

        i = serialized.find(NS_XHTML)
        if i == -1:
            # almost impossible at this point, except in the most stripped
            # unit tests : we have relied so much on it already in the process
            return serialized
        cut = i + len(NS_XHTML)
        return serialized[:cut] + cls.xmlns_re.sub('', serialized[cut:])

    #
    # Internal subclass API
    #


    def readTheme(self, html_file):
        """Read the theme page from an open file.
        Does no actual treatment, in particular no Uri rewriting."""
        raise NotImplementedError

    def parseOptions(self):
        """Parse the options element.
        See doc/themes_specifications.txt for detail"""
        raise NotImplementedError

    @classmethod
    def parseOptionsFile(self, xml_file):
        """Parse a separate xml_file holding options.
        This must stay a classmethod, in order to be called directly with no
        need to instantiate a whole engine. Use case : options for URI
        rewriting within stylesheets
        """
        raise NotImplementedError

    def rewriteUris(self, rewriter_func=None):
        """Rewrite all URIs in the meaningful elements.

        The optional rewriter function allows different treatments to be made
        while keeping exactly the same selection logic of URIs to be treated.
        This is useful for automatic theme preparation procedures, like the
        current final stages of the CPSSkins export process
        """
        raise NotImplementedError

    def serialize(self):
        """Produce the final page to be sent over HTTP."""
        raise NotImplementedError

    def serializeExport(self):
        """Serialization for CPSSkins export.

        Might have different requirements in some cases."""
        return self.serialize()

    def extractSlotElements(self):
        """Return an iterable over pairs (slot name, slot xml element)
        Side effect: cleanup the slot element to make it xhtml compliant
        """
        raise NotImplementedError

    def extractIsolatedPortletsElements(self):
        """Return an iterable of triples (portlet id, xml element, parent)
        Side effect: cleanup the element of the cps:isolatedPortlet attribute
        """
        raise NotImplementedError

    def mergeBodyElement(self, from_cps=None):
        """Merge the body element issued by CPS' ZPTs in the theme's

        This processes attributes only. Typically, these are onload, class, and
        style. Any attribute defined by the theme takes precedence.
        """
        raise NotImplementedError

    def mergeHeads(self, head_content='', cps_global=None):
        """Merge the contextual head_content with cps' global and the theme's.

        To illustrate, in the case of the traditional CPS rendering, namely
        a call to main_template with slot filling, then
        head_content would be what comes from the slot filling
        while cps_global would be what comes from the main_template

        The base logic is that the theme's <head> elements go first,
        then cps_global and finally head_content.
        It is wishable (not mandatory) to put scripts inclusions at the end,
        but inner ordering of them must be preserved.

        There are special rules for MS IE conditional statements (if possible)
        <title> element, etc.
        """
        raise NotImplementedError

    def renderMainContent(self, main_content):
        """Insert the main content where it should."""
        raise NotImplementedError

    @classmethod
    def extractSlotFrame(self, slot):
        """Find the frame part in the slot and remove it from the tree.

        Sibling frames (elements bearing 'cps:frame' attribute) are tolerated
        as a convenience for web designers wanting to check their output
        with several portlets TODO: move this to general doc."""

        raise NotImplementedError

    @classmethod
    def isPortletTitleI18n(self, slot):
        raise NotImplementedError

    @classmethod
    def mergePortlets(self, frame_parent, frame, portlets_rendered):
        """Merge the portlets in their frame.

        portlets_rendered is a pair (title, body)
        frame's parent is passed because it's needed for frame repetition"""
        raise NotImplementedError

    def mergePortletsNoFrame(self, slot_elt, portlets_rendered, **kw):
        """Merge the portlets in the slot, without frames

        portlets_rendered is a pair (title, body)."""
        raise NotImplementedError

    @classmethod
    def mergeIsolatedPortlet(self, element, portlet_rendered, parent):
        """Merge an isolated portlet where appropriate.
        Uses cps:remove attribute on the element to make the proper decision.
        """
        raise NotImplementedError

    def removeElement(self, elt):
        """Remove an element from the tree.

        subclasses should try and avoid using this method. The implementation
        might indeed be expensive because of lack of context about the element.
        In cases where a "parent" is known, there is usually
        a natural and fast way of doing this.
        """
        raise NotImplementedError

    def getHtmlElementsByName(self, name):
        """Uniform access to elements from the XHTML namespace by tag name."""
        raise NotImplementedError

    @classmethod
    def dumpElement(self, elt):
        """Mostly Useful for unit tests"""
        raise NotImplementedError

