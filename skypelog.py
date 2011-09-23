#!/usr/bin/env python
# Copyright 2011 Valery Yundin
#
# This file is free software
# project page https://github.com/Vayu/skypelog
#

"""
Read 'Skype for Linux' *.dbb files


Read and parse Skype database files + simple export of chat message history.
See README for details
"""

from __future__ import with_statement
import struct
import time
import json
import base64
import os


__all__ = ['SkypeDBB', 'SkypeMsgDBB', 'SkypeMsg', 'SkypeAccDBB', 'SkypeAcc']


class SkypeDBB:
    """Read and parse DBB files, return dictionary records"""

    def guessmaxsize(self, filename):
        """Guess maximum record size from the file name """
        k = len(filename) - 1
        while not filename[k].isdigit():
            k -= 1
        i = k
        while filename[i].isdigit():
            i -= 1
        maxsize = int(filename[i + 1:k + 1])
        return maxsize

    def read7bitnum(self, rec, pos):
        """Parse 7-bit encoded number at 'pos' in 'rec'"""
        code = 0
        shift = 0
        while True:
            char = ord(rec[pos])
            code = code + ((char & 0x7F) << shift)
            shift += 7
            pos += 1
            if char & 0x80 == 0:
                break
        return (code, pos)

    def readrecord(self, num):
        """Return num'th record in file"""
        if num >= self.rnum:
            raise IndexError("Record number %d not found" % num)
        self.f.seek(self.stride * num, os.SEEK_SET)
        return self.parserecord(self.f.read(self.stride))

    def parserecord(self, rec):
        """Parse record in string 'rec'"""
        if rec[:4] != 'l33l':
            raise RuntimeError("Invalid header magic %s" % repr(rec[:4]))
        res = {}
        recsize, recid = struct.unpack("<II", rec[4:12])
        res[-1] = recid
        pos = 17
        while pos < recsize + 8:
            ftype = rec[pos]
            pos += 1
            if ftype == '\x00':
                code, pos = self.read7bitnum(rec, pos)
                val, pos = self.read7bitnum(rec, pos)
            elif ftype == '\x03':
                code, pos = self.read7bitnum(rec, pos)
                eos = rec.find('\x00', pos)
                assert (eos != -1)
                val = rec[pos:eos]
                pos = eos + 1
            elif ftype == '\x04':
                code, pos = self.read7bitnum(rec, pos)
                bsize, pos = self.read7bitnum(rec, pos)
                val = base64.b64encode(rec[pos:pos + bsize])
                pos = pos + bsize
            else:
                raise RuntimeError("Unknown field type %s at offset %d" %
                                   (hex(ord(ftype)), pos))
            res[code] = val
        return res

    def records(self):
        """Iterate over all records in file"""
        self.f.seek(0, os.SEEK_SET)
        for rec in iter(lambda: self.f.read(self.stride), ''):
            yield self.parserecord(rec)
        raise StopIteration

    def __init__(self, filename, maxsize=0):
        """Open .dbb file with record size 'maxsize' (optional)"""
        if maxsize == 0:
            maxsize = self.guessmaxsize(filename)
        self.stride = 8 + maxsize
        self.f = open(filename, 'rb')
        self.f.seek(0, os.SEEK_END)
        self.flen = self.f.tell()
        self.f.seek(0, os.SEEK_SET)
        self.rnum = int((self.flen - 1) / self.stride + 1)

    def __del__(self):
        self.f.close()


class SkypeMsgDBB(SkypeDBB):
    """Read and parse Message DBB files chatmsgDDDDD.dbb"""

    def __init__(self, filename, maxsize=0):
        SkypeDBB.__init__(self, filename, maxsize)

    def parserecord(self, rec):
        """Wrap parserecord return in SkypeMsg class"""
        return SkypeMsg(SkypeDBB.parserecord(self, rec))


class SkypeMsg:
    """ Represent and format chat message records"""

    FIELD_NAMES = {   -1 : 'recid',
                      -2 : 'ctime',
                       3 : 'pk_id',
                       7 : 'crc',
                      11 : 'remote_id',
                     480 : 'chatname',
                     485 : 'timestamp',
                     488 : 'author',
                     492 : 'from_dispname',
                     497 : 'chatmsg_type',
                     500 : 'identities',
                     505 : 'leavereason',
                     508 : 'body_xml',
                     513 : 'chatmsg_status',
                     517 : 'body_is_rawxml',
                     818 : 'edited_by',
                     893 : 'edited_timestamp',
                    3160 : 'dialog_partner',
                    3170 : 'guid',             # binary
                   }

    __slots__ = FIELD_NAMES.values()

    def __init__(self, data):
        data[-2] = time.ctime(data[485])
        for k, v in SkypeMsg.FIELD_NAMES.iteritems():
            if k in data:
                setattr(self, v, data[k])
            else:
                setattr(self, v, None)

    def __str__(self):
        return self.__dict__.__str__()

    def json_full(self):
        return json.dumps(self.__dict__, sort_keys=True, ensure_ascii=False)

    def json_compact(self):
        """Output in JSON only fields displayed in client UI"""
        s = '''\
{\
"dialog_partner":"%(dialog_partner)s",\
"timestamp":%(timestamp)d,\
"ctime":"%(ctime)s",\
"from_dispname":"%(from_dispname)s",\
"body_xml":\
''' % self.__dict__
        s += json.dumps(self.body_xml, ensure_ascii=False) + '}'
        return s

    def html_compact(self):
        """Output in HTML only fields displayed in client UI"""
        if self.body_xml == None:
            return ""
        s = '''\
<div class=msg>\
<!-- %(dialog_partner)s %(timestamp)d -->\
<span class=time>%(ctime)s</span>\
''' % self.__dict__
        if self.dialog_partner == self.author:
            s += "<span class=from>%(from_dispname)s</span>" % self.__dict__
        else:
            s += "<span class=me>%(from_dispname)s</span>" % self.__dict__
        msgbody = self.body_xml.replace("\n", "<br>\n")
        s += msgbody + "</div>"
        return s


class SkypeAccDBB(SkypeDBB):
    """Read and parse account DBB files profileDDDDD.dbb"""

    def __init__(self, filename, maxsize=0):
        SkypeDBB.__init__(self, filename, maxsize)

    def parserecord(self, rec):
        """Wrap parserecord return in SkypeMsg class"""
        return SkypeAcc(SkypeDBB.parserecord(self, rec))


class SkypeAcc:
    """ Represent and format account records"""

    FIELD_NAMES = {   -1 : 'recid',
                      16 : 'skypename',
                      20 : 'fullname',
                      29 : 'birthday',
                      33 : 'gender',
                      36 : 'languages',
                      40 : 'country',
                      44 : 'province',
                      48 : 'city',
                      52 : 'phone_home',
                      56 : 'phone_office',
                      60 : 'phone_mobile',
                      64 : 'emails',
                      68 : 'homepage',
                      72 : 'about',
                      77 : 'profile_timestamp',
                      91 : 'profile_attachments',  # binary
                     104 : 'mood_text',
                     109 : 'timezone',
                     116 : 'ipcountry',
                     150 : 'avatar_image',         # binary
                     820 : 'rich_mood_text',
                    3205 : 'registration_timestamp',
                   }

    __slots__ = FIELD_NAMES.values()

    def __init__(self, data):
        for k, v in SkypeAcc.FIELD_NAMES.iteritems():
            if k in data:
                setattr(self, v, data[k])
            else:
                setattr(self, v, None)

    def __str__(self):
        return self.__dict__.__str__()


# -----------------------------------------------------------------------------
# End of API, local functions follow
# -----------------------------------------------------------------------------


def forskypedbbs(func, prefix):
    """Call 'func' on every 'prefix'xxx.dbb"""
    userdirs = []
    skype = os.path.join(os.environ["HOME"], ".Skype")
    for name in os.listdir(skype):
        pathname = os.path.join(skype, name)
        if os.path.isdir(pathname):
            userdirs.append( (name, pathname) )
    for user, home in userdirs:
        chatdbbs = []
        for name in os.listdir(home):
            if name.startswith(prefix) and name.endswith(".dbb"):
                chatdbbs.append(os.path.join(home, name))
        if chatdbbs:
            func(user, chatdbbs)


def dumpmsg_json_full_helper(user, chatdbbs):
    """Dump full messages from 'chatdbbs' files to 'user'.js file (unsorted)"""
    fname = user + '.js'
    print "writing %s ..." % fname
    with open(fname, 'wb') as f:
        for filename in chatdbbs:
            msgdbb = SkypeMsgDBB(filename)
            for r in msgdbb.records():
                f.write(r.json_full() + ",\n")


def dumpmsg_json_full():
    """Dump full chat logs for every user"""
    forskypedbbs(dumpmsg_json_full_helper, "chatmsg")


def dumpmsg_json_compact_helper(user, chatdbbs):
    """Dump messages from 'chatdbbs' files to 'user'.js file (unsorted)"""
    fname = user + '.js'
    print "writing %s ..." % fname
    with open(fname, 'wb') as f:
        for filename in chatdbbs:
            msgdbb = SkypeMsgDBB(filename)
            for r in msgdbb.records():
                f.write(r.json_compact() + ",\n")


def dumpmsg_json_compact():
    """Dump chat logs for every user"""
    forskypedbbs(dumpmsg_json_compact_helper, "chatmsg")


def dumpmsg_html_helper(user, chatdbbs):
    """Dump messages from 'chatdbbs' files to 'user'-user.html file (sorted)"""
    HEAD = '''\
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
<html><head><meta http-equiv="content-type" content="text/html; charset=UTF-8">
<title>[TITLE]</title><style>
div.msg span.time:before { content: "["; }
div.msg span.time:after { content: "]"; }
div.msg span.time { color: #7F7F7F; margin: 0ex 0.2ex 0ex 0.2ex; }
div.msg span.me:after { content: ":"; }
div.msg span.me { font-weight: bold; color: #0063CC; margin: 0ex 0.5ex 0ex 0.5ex; }
div.msg span.from:after { content: ":"; }
div.msg span.from { font-weight: bold; color: #098DDE; margin: 0ex 0.5ex 0ex 0.5ex; }
</style></head><body>
'''
    contacts = {}
    for filename in chatdbbs:
        msgdbb = SkypeMsgDBB(filename)
        for r in msgdbb.records():
            if r.dialog_partner not in contacts:
                contacts[r.dialog_partner] = []
            contacts[r.dialog_partner].append(r.html_compact())
        for name in contacts.keys():
            fname = "%s-%s.html" % (user, name)
            print "writing %s ..." % fname
            with open(fname, 'wb') as f:
                f.write(HEAD.replace("[TITLE]",
                                     "'%s' chats with '%s'" % (user, name)))
                f.write("\n".join(sorted(contacts[name])))
                f.write("</body></html>")


def dumpmsg_html():
    """Dump chat logs for every user"""
    forskypedbbs(dumpmsg_html_helper, "chatmsg")


def usage():
    print """\
Usage: skypelog [OPTION]...
Dump Skype chat history to files in the current directory

Option:
  -h, --help                Show this help message
  -j, --json={compact,full} Save history for each user in *.js file (unsorted)
  -t, --html                Save history for user/contact pair in *.html files
"""


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hj:t",
                                   ["help", "json", "html"])
    except getopt.GetoptError, err:
        print str(err)
        usage()
        sys.exit(2)
    if not opts:
        opts = [("-h", "")]
    for op, arg in opts:
        if op in ("-h", "--help"):
            usage()
            sys.exit()
        elif op in ("-j", "--json"):
            if arg in ("compact"):
                print "Dumping chat history to JSON (compact)..."
                dumpmsg_json_compact()
            elif arg in ("full"):
                print "Dumping chat history to JSON (full)..."
                dumpmsg_json_full()
            else:
                print "JSON: unknown argument '%s'" % arg
                usage()
                sys.exit()
        elif op in ("-t", "--html"):
            print "Dumping chat history to HTML..."
            dumpmsg_html()
        else:
            assert False, "unhandled option"


if __name__ == '__main__':
    import getopt
    import sys
    main()
