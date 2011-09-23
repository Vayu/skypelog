#!/usr/bin/env python

from skypelog import *

def dumpfile(filename, cls=SkypeDBB):
    print "-------- dumping file '%s' -----------" % filename
    data=cls(filename)
    for r in data.records():
        print r

skypedir="./username/"

dumpfile(skypedir+"profile256.dbb", cls=SkypeAccDBB)

dumpfile(skypedir+"transfer256.dbb")

dumpfile(skypedir+"call256.dbb")

dumpfile(skypedir+"callmember256.dbb")

dumpfile(skypedir+"chatmember256.dbb")

dumpfile(skypedir+"user256.dbb")
dumpfile(skypedir+"user1024.dbb")

dumpfile(skypedir+"voicemail256.dbb")
