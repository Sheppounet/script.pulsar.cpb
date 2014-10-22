import re
import CommonFunctions
from pulsar import provider

# Addon Script information
__baseUrl__ = provider.ADDON.getSetting("base_url")
__vo__ = provider.ADDON.getSetting("vo")

# ParseDOM init
common = CommonFunctions
common.plugin = str(sys.argv[0])

ACTION_SEARCH = "recherche"
ACTION_FILMS = "films/"
ACTION_SERIES = "series/"

# Raw search - query is always a string
def search(query):
    provider.log.info("QUERY : %s" % query)
    if(query['query']) : 
        query = query['query']
    # Replace non-alphanum caracters by -, then replace the custom "5number" tags by true folder
    query = re.sub('[^0-9a-zA-Z]+', '-', query)
    query = provider.quote_plus(query)
    query = query.replace('11111',ACTION_SERIES).replace('22222',ACTION_FILMS)
    provider.log.info("GET : %s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query))
    resp = provider.GET("%s/%s/%s.html" % (__baseUrl__, ACTION_SEARCH, query))

    # Parse result
    liens = common.parseDOM(resp.data, 'a', attrs = { "class": "lien-rechercher" }, ret = 'href')
    #for torrent in re.findall(r"%s\/dl-torrent\/.*\.html" % (__baseUrl__),data) :
    return [{"uri": __baseUrl__ + "/_torrents/" + torrent.rpartition('/')[2].replace(".html",".torrent")} for torrent in liens]

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
    provider.log.debug("Search episode : name %(title)s, season %(season)02d, episode %(episode)02d" % episode)
    return search({'query':"11111%(title)s S%(season)02dE%(episode)02d" % episode})

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
# "ru": "??????? ??????",
# "us": "big buck bunny short 2008"
# }
# }
def search_movie(movie):
    provider.log.info(movie['titles'])
    if(movie['titles'].has_key('fr') and __vo__ == 'false'):
        title = movie['titles']['fr']
    else :
        title = movie['title']
    provider.log.info("Search movie : title %s, year %s" % (title, movie['year']))
    return search({'query':"22222%s %s" % (title, movie['year'])})

# Registers the module in Pulsar
provider.register(search, search_movie, search_episode)