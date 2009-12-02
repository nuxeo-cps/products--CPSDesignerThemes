
from StringIO import StringIO
from Products.CMFCore.utils import getToolByName
from Products.CPSDesignerThemes.constants import NS_XHTML, NS_URI
from Products.CPSDesignerThemes.engine import get_engine_class

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
    # that's exactly what the kind of input the theme engine expects (assuming
    # they are supposed to be static).
    # For the remaining ones, we need to fall back to the cps:// scheme
    engine.rewriteUris(rewriter_func=cps_url_scheme)

    ## HEAD preparation
    engine.stripHeadElement()
    return engine.serialize()
