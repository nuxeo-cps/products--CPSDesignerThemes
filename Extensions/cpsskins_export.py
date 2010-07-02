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
from StringIO import StringIO
from Products.CMFCore.utils import getToolByName
from Products.CPSDesignerThemes.constants import NS_XHTML, NS_URI
from Products.CPSDesignerThemes.engine import get_engine_class
from Products.CPSDesignerThemes.engine.twophase import TwoPhaseEngine

logger = logging.getLogger('Products.CPSDesignerThemes.Extensions.cpsskins_export')

EngineClass = get_engine_class()

def cps_url_scheme(uri, cps_base_url='', **kw):
    """Convert full absolute urls to the cps:// scheme"""
    if uri == cps_base_url:
        return 'cps://' # missing trailing slash
    return uri.replace(cps_base_url, 'cps:/')

class ExportEngine(EngineClass):

    def __init__(self, html_file, cps_base_url=None):
        self.readTheme(html_file)

        self.cps_base_url = cps_base_url
        self.theme_base_uri = ''
        self.page_uri = ''
        self.uri_absolute_path_rewrite = False
        self.encoding = 'utf-8'

    def stripHeadElement(self):
        # XXX Actually expects EngineClass to subclass ElementTreeEngine
        head = self.root.find('./{%s}head' % NS_XHTML)
        # Everything that's before CPSSkins' marker is from header_lib_header
        # and must be stripped, since that's filled in by the theme rendering
        meta_tag = '{%s}meta' % NS_XHTML
        for i, elt in enumerate(head):
            if elt.tag == meta_tag and elt.attrib.get('name') == 'engine':
                break
        else:
            raise ValueError("CPSSkin's meta tag \"engine\" not found "
                             "in the generated web page")

        if 'CPSSkins' in elt.attrib['content']:
            del head[0:i]

        # now put some default elements (etreeengine API only,
        # avoid 2-phase pbms)
        if isinstance(self, TwoPhaseEngine):
            insertFragment = super(TwoPhaseEngine, self).insertFragment
        else:
            insertFragment = self.insertFragment

        insertFragment(0, head, '<meta http-equiv="Content-Type" '
                       'content="text/html; charset=UTF-8" />',
                       is_element=True)

DESIGNER_LAYER = 'cps_designer_themes_compat'
def disable_designer_themes(portal):
    """ Disable and return a dict (skin name) -> (order among layers)
    """

    stool = portal.portal_skins
    indices = {}
    for skin, path in stool.getSkinPaths():
        layers = [l.strip() for l in path.split(',')]
        try:
            indices[skin] = index = layers.index(DESIGNER_LAYER)
        except ValueError:
            continue
        logger.debug("Before disabling, layers for skin '%s': %s", skin, layers)
        del layers[index]
        stool.addSkinSelection(skin, ','.join(layers))
    if indices:
        portal.clearCurrentSkin()
        portal.setupCurrentSkin()
    return indices

def reenable_designer_themes(portal, indices):
    stool = portal.portal_skins
    for skin, index in indices.items():
        path = stool.getSkinPath(skin)
        layers = [l.strip() for l in path.split(',')]
        layers.insert(index, DESIGNER_LAYER)
        stool.addSkinSelection(skin, ','.join(layers))
        logger.debug("After reenabling, layers for skin '%s': %s", skin, layers)
    if indices:
        portal.clearCurrentSkin()
        portal.setupCurrentSkin()


def export(self):
    portal = getToolByName(self, 'portal_url').getPortalObject()

    indices = disable_designer_themes(portal)
    exporter = self.cpsskins_designer_export
    first_pass = self.cpsskins_designer_export()
    reenable_designer_themes(portal, indices)

    first_pass = first_pass.replace('xmlns="%s"' % NS_XHTML,
                                    'xmlns="%s" xmlns:cps="%s"' % (
        NS_XHTML, NS_URI))
    portal =  getToolByName(self, 'portal_url').getPortalObject()

    # see #2076
    if portal.default_charset != 'unicode':
        first_pass = first_pass.decode(portal.default_charset).encode('utf-8')
    engine = ExportEngine(StringIO(first_pass),
                          cps_base_url=portal.absolute_url())

    ## URI preparation
    # Local or absolute local urls are ok, because a tool like wget will convert
    # them in local links for a self-contained rendering from the file system
    # that's exactly what the kind of input the theme engine expects (assuming
    # they are supposed to be static).
    # For the remaining ones, we need to fall back to the cps:// scheme
    engine.rewriteUris(rewriter_func=cps_url_scheme)

    ## HEAD preparation
    engine.stripHeadElement()
    xml = engine.serializeExport()

    # formatting
    import popen2
    stdout, stdin, stderr = popen2.popen3(
            'tidy --wrap 79 --indent-attributes yes '
            '--indent yes --indent-spaces 2 -asxml -xml')
    stdin.write(xml)
    stdin.close()
    formatted = stdout.read()
    stdout.close()
    # GR this includes the possibility that tidy is not installed
    logger.error("Tidy errors and warnings: %s", stderr.read())

    return formatted or xml
