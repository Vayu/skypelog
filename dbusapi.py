#!/usr/bin/env python
import dbus
import sys
try:
    skype = dbus.SystemBus().get_object('com.Skype.API', '/com/Skype')
except:
    try:
        skype = dbus.SessionBus().get_object('com.Skype.API', '/com/Skype')
    except:
        print "Can't find Skype API"
        sys.exit()

print skype.Invoke("NAME python")
print skype.Invoke("PROTOCOL 9999")
print skype.Invoke("SEARCH CHATS")
