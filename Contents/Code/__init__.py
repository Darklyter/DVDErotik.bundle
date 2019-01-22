# DVDErotik
# Update: 19 January 2019
# Description: New updates from a lot of diffrent forks and people. Please read README.md for more details.
import re
import datetime
import random

# preferences
preference = Prefs
DEBUG = preference['debug']
if DEBUG:
  Log('Agent debug logging is enabled!')
else:
  Log('Agent debug logging is disabled!')


if len(preference['searchtype']) and preference['searchtype'] != 'all':
  searchzone = None;
  switcher = {
    "all":"0",
    "dvd":"1",
    "bluray":"2",
    "vod":"8"
  }
  searchzone = switcher[preference['searchtype']]
  if searchzone is None:
      searchzone = "0"
else:
  searchzone = "0"

searchzone = "1"

if DEBUG:Log('Search Zone: %s %s' % (searchzone,str(preference['searchtype'])))

# URLS
ADE_BASEURL = 'https://www.dvderotik.com'
ADE_SEARCH_MOVIES = ADE_BASEURL + '/catalog/search.php/language/en?keywords=%s&zone=' + searchzone
ADE_MOVIE_INFO = ADE_BASEURL + '/catalog/product_info.php/products_id/%s/language/en'

scoreprefs = int(preference['goodscore'].strip())
if scoreprefs > 1:
    GOOD_SCORE = scoreprefs
else:
    GOOD_SCORE = 98
if DEBUG:Log('Result Score: %i' % GOOD_SCORE)

INITIAL_SCORE = 100

titleFormats = r'\(DVD\)|\(Blu-Ray\)|\(BR\)|\(VOD\)'

def Start():
  HTTP.CacheTime = CACHE_1MINUTE
  HTTP.SetHeader('User-agent', 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.2; Trident/4.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0)')

def ValidatePrefs():
  pass

class DEAgent(Agent.Movies):
  name = 'DVDErotik'
  languages = [Locale.Language.English]
  primary_provider = True
  accepts_from = ['com.plexapp.agents.adultdvdempire']

  def search(self, results, media, lang):
    title = media.name
    if media.year:
        yearsearch = "&rdate=" + str(media.year)
    else:
        yearsearch = ""

    if media.primary_metadata is not None:
      title = media.primary_metadata.title
      lang = media.primary_metadata.lang
      if media.primary_metadata.year:
          if media.primary_metadata.year > 1950 and media.primary_metadata.year < 2050:
              yearsearch = "&rdate=" + str(media.primary_metadata.year)

    query = String.URLEncode(String.StripDiacritics(title.replace('-','')))

    # resultarray[] is used to filter out duplicate search results
    resultarray=[]
    if DEBUG: Log('Search Query: %s' % str(ADE_SEARCH_MOVIES % query))
    # Finds the entire media enclosure <DIV> elements then steps through them
    if DEBUG: Log('Looking for Movies...')
    ADE_SEARCH_STRING = (ADE_SEARCH_MOVIES % query)
    ADE_SEARCH_STRING += yearsearch
    for movie in HTML.ElementFromURL(ADE_SEARCH_STRING).xpath('//div[@class="list_products"]'):
        # curName = The text in the 'title' p
        moviehref = movie.xpath('.//h2/a[contains(@href,"/products_id/")]')[0]
        curName = moviehref.text_content().strip()
        if curName.count(', The'):
          curName = 'The ' + curName.replace(', The','',1)
        curName += " [DE]"

        # curID = the ID portion of the href in 'movie'
        curID = moviehref.get('href').split('/',4)[4]
        score = INITIAL_SCORE - Util.LevenshteinDistance(title.lower(), curName.lower())
        if DEBUG: Log('Movie Found: %s \t ID: %s\t Score: %s' % (str(curName), str(curID),str(score)))

        if curName.lower().count(title.lower()):
            results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))
        elif (score >= GOOD_SCORE):
            results.Append(MetadataSearchResult(id = curID, name = curName, score = score, lang = lang))

    results.Sort('score', descending=True)

  def update(self, metadata, media, lang):
    html = HTML.ElementFromURL(ADE_MOVIE_INFO % metadata.id)
    metadata.title = media.title
    metadata.title = re.sub(r'\ \[DE\]','',metadata.title).strip()
    #This strips the format type returned in the "curName += "  (VOD)" style lines above
    #You can uncomment them and this to make it work, I jsut thought it was too busy with
    #The dates listed as well, not to mention that formats are sorted by type with the score
    #DVD = 91-100, Blu-Ray = 71-80, VOD = 31-40
    #metadata.title = re.sub(titleFormats,'',metadata.title).strip()

    # Thumb and Poster
    imgpath = html.xpath('//a[@class="lightbox"]/@href')[0]
    thumbpath = html.xpath('//a[@class="lightbox"][1]/img[1]/@src')[0]
    imgpath = imgpath.strip().replace("/c/", "/u/", 1)
    Log('Image URL: %s' % imgpath)
    thumb = HTTP.Request(thumbpath)
    metadata.posters[imgpath] = Proxy.Preview(thumbpath)

    # Tagline
    try: metadata.tagline = html.xpath('//p[@class="Tagline"]')[0].strip()
    except: pass

    # Summary.
    try:
      for summary in html.xpath('//td[@class="main"]/p/text()'):
        metadata.summary = summary.strip()
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Studio.
    try:
      for studio in html.xpath('//b[contains(text(),"Studio:")]/following-sibling::a[1]/text()'):
        metadata.studio = studio.strip()
        if DEBUG: Log('Added Studio: %s' % studio.strip())
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Release Date.
    try:
      for releasedate in html.xpath('//b[contains(text(),"Date added:")]/following-sibling::text()[1]'):
        metadata.originally_available_at = Datetime.ParseDate(releasedate.strip()).date()
        metadata.year = metadata.originally_available_at.year
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))

    # Production Year
    # If the user preference is set, then we want to replace the 'Release Date' with a created date
    # based off of the Production Year that is returned.  Don't want to do it unless the difference
    # is greater than one year however, to allow for production at the end of the year with first of
    # year release
    try:
      for prodyear in html.xpath('//b[contains(text(),"Production Year:")]/following-sibling::text()[1]'):
        productionyear = int(prodyear.strip())
        if productionyear > 1900:
            if DEBUG: Log('Release Date Year for Title: %i' % metadata.year)
            if DEBUG: Log('Production Year for Title: %i' % productionyear)
            if (metadata.year > 1900) and ((metadata.year - productionyear) >1):
                metadata.year = productionyear
                metadata.originally_available_at = Datetime.ParseDate(str(productionyear) + "-01-01")
                if DEBUG: Log('Production Year earlier than release, setting date to: %s' % (str(productionyear) + "-01-01"))
    except Exception, e:
      Log('Got an exception while parsing summary %s' %str(e))


    # Cast - added updated by Briadin / 20190108
    try:
      metadata.roles.clear()
      for castmember in html.xpath('//b[contains(text(),"Cast:")]/following-sibling::a[contains(@href,"/pornostar/")]/text()'):
          role = metadata.roles.new()
          role.name = castmember.strip()
          if DEBUG: Log('Added Star: %s' % castmember.strip())
    except Exception, e:
      Log('Got an exception while parsing cast %s' %str(e))

    # Series.
    try:
      metadata.collections.clear()
      for series in html.xpath('//b[contains(text(),"Series:")]/following-sibling::a[1]/text()'):
        metadata.collections.add(series.strip())
        if DEBUG: Log('Added Collection: %s' % series.strip())
    except: pass

    # Genres.
    try:
      metadata.genres.clear()
      ignoregenres = [x.lower().strip() for x in preference['ignoregenres'].split('|')]
      for genre in html.xpath('//b[contains(text(),"Category:")]/following-sibling::a[contains(@href,"cPath")]/text()'):
          if len(genre) > 0:
              if not genre.lower().strip() in ignoregenres:
                metadata.genres.add(genre.strip())
                if DEBUG: Log('Added Genre: %s' % genre.strip())
    except: pass
