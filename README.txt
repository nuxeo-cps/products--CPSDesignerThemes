========================
CPSDesignerThemes README
========================

:Author: Georges Racinet

:Revision: $Id: howto-virtual_hosts.txt 52890 2008-06-27 12:58:37Z madarche $

.. sectnum::    :depth: 4
.. contents::   :depth: 4


See INSTALL.txt for installing and testing instructions

CPSDesignerThemes
=================

CPSDesignerTheme allows web designers to work on themes
like they are used to do in the majority of popular web applications,
including wordpress and dotclear2.

This product is meant as a replacement of CPSSkins for projects that
can hire a web designer or satisfy themselves with one of the themes
available online.  Being much simpler, it also improves vastly the
average
rendering time.

CPSSkins is an through-the-web theme editor for CPS that provides easy skinning
facilities for functional administrators, and can let users set up a
portal with corporate identity in a very short time.

CPSDesignerThemes is provided under the GPL license by Georges Racinet
Online resources at http://www.racinet.org/cps/designer-themes


Basic concepts
==============

A theme is a directory made of several html templates and various
resources, e.g, images, stylesheets and javascript.

Portlets
--------

CPS' dynamical rendering is structured in logical called
portlets. These range to content listing boxes and menus to the "main
content" portlet where the user does her contribution/applicative
work. A portlet is supposed to include very few styling information.

Slots
-----

A slot is a logical area on your theme page. Each portlet is assigned
to a slot. The rendering engine simply looks for slot declarations in your page
and fills them with the portlets from that slot that should be
rendered according to context.

The slot concept provides another level of separation between content
and presentation. You can use it to shuffle stuff around the pages or
simply to hide portlets that are irrelevant to your page (extreme
example: printer-friendly page)

This concept is identical to the one from CPSSkins' Portal Box Groups
and was actually directly taken from it.

Stylesheets
-----------

CPS will add to the head section of the page the links to the
stylesheets it specifically needs (e.g, document.css).


.. Local Variables:
.. mode: rst
.. End:
.. vim: set filetype=rst:
