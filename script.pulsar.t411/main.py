import unicodedata
import re
import json
import xbmc
import xbmcaddon
from pulsar import provider

import base64
import hashlib
import bencode
from threading import Thread
import Queue

# TODO
# - Trouver le bon encodage avec l'API : Les espaces et surement d'autres caractères ne sont pas bien reconnus

# Addon Script information
__addonID__ = provider.ADDON.getAddonInfo('id')
API_URL = provider.ADDON.getSetting("base_url")
username = provider.ADDON.getSetting("username")
password = provider.ADDON.getSetting("password")
titreVF = provider.ADDON.getSetting("titreVF")
limit = 10 #provider.ADDON.getSetting("limit")

USER_CREDENTIALS_FILE = xbmc.translatePath("special://profile/addon_data/%s/token.txt" % __addonID__)

user_credentials = {}

tmdbUrl = 'http://api.themoviedb.org/3'
tmdbKey = '8d0e4dca86c779f4157fc2c469c372ca'    # mancuniancol's API Key.

# Categories ID /categories/tree
CAT_VIDEO = 210
CAT_MOVIE = 631
CAT_TV = 433
CAT_ANIME = 637

def _init() :
    global user_credentials
    provider.log.info("Get user credentials and authentificate it, if any credentials defined use token stored in user file")
    try :
        with open(USER_CREDENTIALS_FILE) as user_cred_file:
            user_credentials = json.loads(user_cred_file.read())
            provider.log.info("Get local credentials")
            provider.log.debug(user_credentials)
        if 'uid' not in user_credentials or 'token' not in user_credentials:
            raise Exception('Wrong data found in user file')
        # Get user details & check if token still valid
        #response = call('/users/profile/' + user_credentials['uid'])
        #provider.log.debug(response)
        #else:
        # we have to ask the user for its credentials and get the token from
        # the API
        #self._auth(user, password)
    except IOError as e:
        # Try to auth user from credentials in parameters
        _auth(username, password)
    #except Exception as e:
    #    raise Exception('Error while reading user credentials: %s.' %
    #    e.message)
def _auth(username, password) :
    global user_credentials
    provider.log.info("Authentificate user and store token")
    user_credentials = call('/auth', {'username': username, 'password': password})
    print(user_credentials)
    if 'error' in user_credentials:
        raise Exception('Error while fetching authentication token: %s' % user_credentials['error'])
    # Create or update user file
    provider.log.info('file %s' % USER_CREDENTIALS_FILE)
    user_data = json.dumps({'uid': '%s' % user_credentials['uid'], 'token': '%s' % user_credentials['token']})
    with open(USER_CREDENTIALS_FILE, 'w') as user_cred_file:
        user_cred_file.write(user_data)
    return True

def call(method='', params=None) :
    provider.log.info("Call T411 API: %s%s" % (API_URL, method))
    if method != '/auth' :
        token = user_credentials['token']
        provider.log.info('token %s' % token)
        req = provider.POST('%s%s' % (API_URL, method), headers={'Authorization': token})
    else:
        req = provider.POST('%s%s' % (API_URL, method), data=provider.urlencode(params))
    if req.getcode() == 200:
        return req.json()
    else :
        raise Exception('Error while sending %s request: HTTP %s' % (method, req.getcode()))

# Default Search
def search(query, cat_id=CAT_VIDEO, terms=None):
    result = []
    threads = []
    q = Queue.Queue()
    provider.log.debug("QUERY : %s" % query)
    query_normalize = unicodedata.normalize('NFKD',query)
    query = ''.join(c for c in query_normalize if (not unicodedata.combining(c)))
    response = call('/torrents/search/%s&cid=%s%s' % (provider.quote_plus(query), cat_id, terms))
    provider.log.debug("Search results : %s" % response)
    # Pulsar send GET requests & t411 api needs POST
    # Must use the bencode tool :(
    
    for t in response['torrents'] :

        # Call each individual page in parallel
        thread = Thread(target=torrent2magnet, args = (t, q, user_credentials['token']))
        thread.start()
        threads.append(thread)

    # And get all the results
    for t in threads :
        t.join()
    while not q.empty():
        item = q.get()
        result.append({
                       "size": item["size"], 
                       "seeds": item["seeds"], 
                       "peers": item["peers"], 
                       "name": item["name"],
                       "trackers": item["trackers"],
                       "info_hash": item["info_hash"],
                       "is_private": True})
    return result

    #return [{'uri' : provider.append_headers('%s/torrents/download/%s' % (API_URL, t["id"]), {"Authorization": user_credentials['token']})} for t in response['torrents']]
    
def search_episode(episode): 
    provider.log.debug("Search episode : name %(title)s, season %(season)02d, episode %(episode)02d" % episode)
    if(titreVF == 'true') :
        # Pulsar 0.2 doesn't work well with foreing title. Get the FRENCH title from TMDB
        provider.log.debug('Get FRENCH title from TMDB for %s' % episode['imdb_id'])
        response = provider.GET("%s/find/%s?api_key=%s&language=fr&external_source=imdb_id" % (tmdbUrl, episode['imdb_id'], tmdbKey))
        provider.log.debug(response)
        if response != (None, None):
            name_normalize = unicodedata.normalize('NFKD',response.json()['tv_results'][0]['name'])
            episode['title'] = episode['title'].join('|').join(c for c in name_normalize if (not unicodedata.combining(c)))
            provider.log.info('FRENCH title :  %s' % episode['title'])
        else :
            provider.log.error('Error when calling TMDB. Use Pulsar movie data.')
    
    # Get settings for TVShows
    terms = pref_terms

    if(episode['season']):
        terms += '&term[45][]=%(season)02d' % episode

    if(episode['episode']):
        terms += '&term[46][]=%(episode)02d' % episode
    
    return search(episode['title'], CAT_TV, terms)

def search_movie(movie):
    if(titreVF == 'true') :
        #Pulsar 0.2 doesn't work well with foreing title. Get the FRENCH title from TMDB
        provider.log.debug('Get FRENCH title from TMDB for %s' % movie['imdb_id'])
        response = provider.GET("%s/movie/%s?api_key=%s&language=fr&external_source=imdb_id&append_to_response=alternative_titles" % (tmdbUrl, movie['imdb_id'], tmdbKey))
        if response != (None, None):
            title_normalize = unicodedata.normalize('NFKD',response.json()['title'])
            movie['title'] = movie['title'].join('|').join(c for c in title_normalize if (not unicodedata.combining(c)))
            provider.log.info('FRENCH title :  %s' % movie['title'])
        else :
            provider.log.error('Error when calling TMDB. Use Pulsar movie data.')

    return search(provider.quote_plus(movie['title']), CAT_MOVIE, pref_terms)

# Get preference search from settings
def setTerms():
    global pref_terms
    pref_terms = '' 
    termList = [[]] * 18
    # 7 : Video - Qualite
    termList[7] = [8,9,10,11,12,13,14,15,16,17,18,19,1162,1171,1174,1175,1182]
    # 9 : Video - Type
    termList[9] = [22,23,24,1045]
    # 17 : Video - Langue
    termList[17] = [540,541,542,719,720,721,722,1160]

    # Get all settings correspondance
    for idx, term in enumerate(termList):
        for iTerm in term:
            if provider.ADDON.getSetting('%s' % iTerm) == 'true':
               pref_terms += '&term[%s][]=%s' % (idx, iTerm)

def torrent2magnet(t, q, token):
    torrentdl = '/torrents/download/%s' % t["id"]
    response = provider.POST('%s%s' % (API_URL, torrentdl), headers={'Authorization': token})
    torrent = response.data
    metadata = bencode.bdecode(torrent)
    hashcontents = bencode.bencode(metadata['info'])
    digest = hashlib.sha1(hashcontents).hexdigest()
    trackers = [metadata["announce"]]
    
    xbmc.log('Put Magnet in queue : name %s, size %s, seeds %s, peers %s' % (t["name"], t["size"], t["seeders"], t["leechers"]), xbmc.LOGDEBUG)
    q.put({"size": int(t["size"]), "seeds": int(t["seeders"]), "peers": int(t["leechers"]), "name": t["name"], "trackers": trackers, "info_hash": digest})

# Initialize account
_init()
#_auth()
setTerms()

# Registers the module in Pulsar
provider.register(search, search_movie, search_episode)
