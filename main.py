import re
import unicodedata
from pulsar import provider

# Addon Script information
__baseUrl__ = provider.ADDON.getSetting("base_url")

tmdbUrl = 'http://api.themoviedb.org/3'
tmdbKey = '8d0e4dca86c779f4157fc2c469c372ca'    # mancuniancol's API Key.
ACTION_SEARCH = "recherche"
ACTION_FILMS = "films/"
ACTION_SERIES = "series/"

# Raw search - query is always a string
def search(query):
    provider.log.info("QUERY : %s" % query)
    query_normalize = unicodedata.normalize('NFKD',query)
    query = ''.join(c for c in query_normalize if (not unicodedata.combining(c)))
    # Replace non-alphanum caracters by -, then replace the custom "5number" tags by true folder
    query = re.sub('[^0-9a-zA-Z]+', '-', query)
    query = provider.quote_plus(query)
    query = query.replace('11111',ACTION_SERIES).replace('22222',ACTION_FILMS)
    provider.log.info("GET : %s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query))
    resp = provider.GET("%s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query))
    # REGEX to find wanted links - 2 capturing groups
    # - (?:films|series) : match only films or series, ?: is to exclude this group from capturing, which generate a tuple as return
    # - Use the class to exclude ads "top downloaded" links
    # - >(.*?)< to get the media name
    # It brings back a tuple : torrent[0] = uri, torrent[1] = name
    p = re.compile(ur'(/dl-torrent/(?:films|series)/\S*\.html).*?class="titre">(.*?)<')
    # Uncomment if needed to get optimal perfs
    #for torrent in re.findall(p, resp.data) :
    #    provider.log.debug("REGEX FOUND %s" % torrent[0]) 
    return [{"name": torrent[1], "uri": __baseUrl__ + "/telechargement/" + torrent[0].rpartition('/')[2].replace(".html",".torrent")} for torrent in re.findall(p, resp.data)]

# Episode Payload Sample
# {
# "imdb_id": "tt0092400",
# "tvdb_id": "76385",
# "title": "married with children",
# "season": 1,
# "episode": 1,
# "titles": null
# }
def search_episode(episode):
    provider.log.info("Search episode : name %(title)s, season %(season)02d, episode %(episode)02d, imdb_id %(imdb_id)s" % episode)
    if episode['imdb_id']!= 'tt0436992' and episode['imdb_id']!='tt0944947' :
        # Disable french title for Doctor Who 'tt0436992' (return "Dr Who") and 
        # Game of thrones 'tt0944947' (Le trone de fer). May be some other are bad with their FR title :/
        response = provider.GET("%s/find/%s?api_key=%s&language=fr&external_source=imdb_id" % (tmdbUrl, episode['imdb_id'], tmdbKey))
        provider.log.debug(response)
        if response != (None, None):
            name_normalize = unicodedata.normalize('NFKD',response.json()['tv_results'][0]['name'])
            episode['title'] = ''.join(c for c in name_normalize if (not unicodedata.combining(c)))
            provider.log.debug('FRENCH title :  %s' % episode['title'])
        else :
            provider.log.error('Error when calling TMDB. Use Pulsar movie data.')
    return search("11111%(title)s S%(season)02dE%(episode)02d" % episode)

# Movie Payload Sample
# Note that "titles" keys are countries, not languages
# The titles are also normalized (accents removed, lower case etc...)
# {
# "imdb_id": "tt1254207",
# "title": "big buck bunny",
# "year": 2008,
# "titles": {
# "es": "el gran conejo",
# "nl": "peach open movie project",
# "ru": "???????  ??????",
# "us": "big buck bunny short 2008"
# }
# }
def search_movie(movie):
    # Pulsar 0.2 doesn't work well with foreing title.  Get the FRENCH title from TMDB
    provider.log.debug('Get FRENCH title from TMDB for %s' % movie['imdb_id'])
    response = provider.GET("%s/movie/%s?api_key=%s&language=fr&external_source=imdb_id&append_to_response=alternative_titles" % (tmdbUrl, movie['imdb_id'], tmdbKey))
    if response != (None, None):
        title_normalize = unicodedata.normalize('NFKD',response.json()['title'])
        movie['title'] = ''.join(c for c in title_normalize if (not unicodedata.combining(c)))
        provider.log.info('FRENCH title :  %s' % movie['title'])
    else :
        provider.log.error('Error when calling TMDB. Use Pulsar movie data.')
    provider.log.info("Search movie : title %s, year %s" % (movie['title'], movie['year']))
    return search("22222%s %s" % (movie['title'], movie['year']))

# Registers the module in Pulsar
provider.register(search, search_movie, search_episode)