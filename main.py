import sys
import json
import base64
import hashlib
import re
import urllib
import urllib2
import xbmc
import xbmcaddon
import bencode
from threading import Thread
import Queue
import CommonFunctions

PAYLOAD = json.loads(base64.b64decode(sys.argv[1]))

# Addon Script information
__addonID__ = str(sys.argv[0])
__addon__ = xbmcaddon.Addon(__addonID__)
__baseUrl__ = __addon__.getSetting("base_url")

# ParseDOM init
common = CommonFunctions
common.plugin = __addonID__

ACTION_SEARCH = "recherche"
ACTION_FILMS = "films/"
ACTION_SERIES = "series/"
USERAGENT = "Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11"

def search(query):
    result = []
    threads = []
    q = Queue.Queue()
    # Replace non-alphanum caracters by -, then replace the custom "5number" tags by true folder
    query = re.sub('[^0-9a-zA-Z]+', '-', query)
    query = urllib.quote_plus(query)
    query = query.replace('11111',ACTION_SERIES).replace('22222',ACTION_FILMS)
    xbmc.log("Search URL : %s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query), xbmc.LOGDEBUG)
    url = urllib2.Request("%s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query))
    url.add_header('User-Agent', USERAGENT)
    response = urllib2.urlopen(url)
    data = response.read()
    if response.headers.get("Content-Encoding", "") == "gzip":
        import zlib
        data = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(data)

    # Parse result
    liens = common.parseDOM(data, 'a', attrs = { "class": "lien-rechercher" }, ret = 'href')
    #for torrent in re.findall(r"%s\/dl-torrent\/.*\.html" % (__baseUrl__), data) :
    for torrent in liens :
        xbmc.log('Transform torrent : %s' % torrent, xbmc.LOGDEBUG)
        torrent = str(torrent).rpartition('/')[2]
        torrent = __baseUrl__ + "/_torrents/" + torrent.replace(".html",".torrent")

        # Call each individual page in parallel
        thread = Thread(target=torrent2magnet, args = (torrent, q))
        thread.start()
        threads.append(thread)
        
    # And get all the results
    for t in threads :
        t.join()
    while not q.empty():
        result.append({"uri": q.get()})
    return result

def search_episode(imdb_id, tvdb_id, name, season, episode):
    xbmc.log('Search episode : name %s, season %s, episode %s' % (name, season, episode), xbmc.LOGDEBUG)
    return search("11111%s S%02dE%02d" % (name, season, episode))

def search_movie(imdb_id, name, year):
    xbmc.log('Search movie : name %s, year %s' % (name, year), xbmc.LOGDEBUG)
    return search("22222%s %s" % (name, year))

def torrent2magnet(torrent_url, q):
    response = urllib2.urlopen(torrent_url)
    torrent = response.read()
    metadata = bencode.bdecode(torrent)
    hashcontents = bencode.bencode(metadata['info'])
    digest = hashlib.sha1(hashcontents).digest()
    b32hash = base64.b32encode(digest)
    magneturl = 'magnet:?xt=urn:btih:' + b32hash + '&dn=' + metadata['info']['name']
    xbmc.log('Put Magnet in queue : %s' % magneturl, xbmc.LOGDEBUG)
    q.put(magneturl)

urllib2.urlopen(PAYLOAD["callback_url"],
    data = json.dumps(globals()[PAYLOAD["method"]](*PAYLOAD["args"])))
