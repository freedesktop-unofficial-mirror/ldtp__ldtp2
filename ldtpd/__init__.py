'''
LDTP v2 init file

@author: Eitan Isaacson <eitan@ascender.com>
@copyright: Copyright (c) 2009 Eitan Isaacson
@license: LGPL

http://ldtp.freedesktop.org

This file may be distributed and/or modified under the terms of the GNU General
Public License version 2 as published by the Free Software Foundation. This file
is distributed without any warranty; without even the implied warranty of 
merchantability or fitness for a particular purpose.

See "COPYING" in the source distribution for more information.

Headers in this file shall remain intact.
'''

def main(port=4118):
    import os
    os.environ['NO_GAIL'] = '1'
    os.environ['NO_AT_BRIDGE'] = '1'

    from twisted.internet import glib2reactor
    glib2reactor.install()
    from twisted.internet import reactor
    from twisted.web import server, xmlrpc
    from xmlrpc_daemon import XMLRPCLdtpd
    import twisted.internet
    import socket
    import pyatspi
    import traceback

    try:
        pyatspi.setCacheLevel(pyatspi.CACHE_PROPERTIES)
        r = XMLRPCLdtpd()
        xmlrpc.addIntrospection(r)
        reactor.listenTCP(port, server.Site(r))
        reactor.run()
    except twisted.internet.error.CannotListenError:
        if os.environ.has_key('LDTP_DEBUG'):
            print traceback.format_exc()
    except socket.error:
        if os.environ.has_key('LDTP_DEBUG'):
            print traceback.format_exc()
