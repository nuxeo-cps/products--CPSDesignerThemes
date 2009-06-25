
from StringIO import StringIO
from Products.CMFCore.utils import getToolByName
from Products.CPSDesignerThemes.engine.etreeengine import ElementTreeEngine
from Products.CPSDesignerThemes.engine.etreeengine import ET
from Products.CPSDesignerThemes.constants import NS_XHTML, NS_URI


def cps_url_scheme(uri, cps_base_url='', **kw):
    """Convert full absolute urls to the cps:// scheme"""
    if uri == cps_base_url:
        return 'cps://' # missing trailing slash
    return uri.replace(cps_base_url, 'cps:/')

class ExportEngine(ElementTreeEngine):
    def __init__(self, html_file, cps_base_url=None):
        self.tree = ET.parse(html_file)
        self.root = self.tree.getroot()
        self.cps_base_url = cps_base_url

        self.theme_base_uri = ''
        self.page_uri = ''

    def stripHeadElement(self):
        head = self.root.find('./{%s}head' % NS_XHTML)
        # Everything that's before CPSSkins' marker is from header_lib_header
        # and must be stripped, since that's filled in by the theme rendering
        meta_tag = '{%s}meta' % NS_XHTML
        for i, elt in enumerate(head):
            if elt.tag == meta_tag and elt.attrib.get('name') == 'engine':
                break
        else:
            raise ValueError("CPSSkin's generator not found")

        if 'CPSSkins' in elt.attrib['content']:
            del head[0:i]


def export(self):
    first_pass = self.cpsskins_designer_export()
    first_pass = first_pass.replace('xmlns="%s"' % NS_XHTML, 'xmlns="%s" xmlns:cps="%s"' % (
        NS_XHTML, NS_URI))
    portal =  getToolByName(self, 'portal_url').getPortalObject()
    engine = ExportEngine(StringIO(first_pass),
                          cps_base_url=portal.absolute_url())

    ## URI preparation
    # Local or absolute local urls are ok, because a tool like wget will convert
    # them in local links for a self-contained rendering from the file system
    # that's exactly what the kind of input the theme engine expects.
    # For the remaining ones, we need to fall back to the cps:// scheme
    engine.rewriteUris(rewriter_func=cps_url_scheme)

    ## HEAD preparation
    engine.stripHeadElement()
    return engine.serialize()
