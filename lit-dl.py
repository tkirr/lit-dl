import sys
import requests
import json
import json.decoder
import codecs
import pprint
import os

CACHE_DIR = "literotica_cache"

TEMPLATE = """
<html>
<head>
<style>
div.story {{
  width: 800px;
  margin: 50px;
  font-size: 16pt;
  text-align: justify;
}}
div.desc {{
  font-style: italic;
}}
</style>
</head>
<body>
<h1 class="title"><a href="https://www.literotica.com/s/{slug}">{title}</a></h1>
<h2 class="byline">By <a href="https://www.literotica.com/stories/memberpage.php?uid={author_id}&page=submissions">{author}</a></h2>
<div class="desc">{description}</div>
<hr/>
<div class="story">
{contents}
</div>
<hr/>
{nav}
</body>
</html>
"""

def decode(s):
    decoder = json.JSONDecoder()
    obj, idx = decoder.raw_decode(s, idx=0)
    return obj

class StoryPage:
    def __init__(self, contents, page):
        KEY = "state='"
        i = contents.find(KEY)
        if i >= 0:
            ext = codecs.decode(contents[i+len(KEY):], 'unicode-escape')
        else:
            ext = contents

        decoder = json.JSONDecoder()
        self._fields, _ = decoder.raw_decode(ext, idx=0)
        self._page = page

    def page(self):
        return self._page

    def page_count(self):
        return self._fields['story']['data']['meta']['pages_count']

    def text(self):
        return next(iter(self._fields['story']['objects'].values()))["pageText"]

    def formatted_text(self):
        t = self.text()
        paragraphs = t.split("\r\n\r\n")
        return "".join("<p>{}</p>\n".format(p) for p in paragraphs)

    def series_slugs(self):
        if 'items' not in self._fields['story']['data']['series']:
            return [self.slug()]

        return [
            story['url']
            for story in self._fields['story']['data']['series']['items']
        ]

    def author(self):
        return self._fields['story']['data']['authorname']

    def author_id(self):
        return self._fields['story']['data']['author']['userid']

    def title(self):
        return self._fields['story']['data']['title']

    def slug(self):
        return self._fields['story']['data']['url']

    def description(self):
        return self._fields['story']['data']['description']

    def tags(self):
        return [t['tag'] for t in self._fields['story']['data']['tags']]

class Literotica:
    def __init__(self):
        self._cache = {}

    def fetch(self, story_slug, page=1):
        cache_key = "{}_{}".format(story_slug, page)

        if cache_key in self._cache:
            return self._cache[cache_key]

        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)
        cache_file = os.path.join(CACHE_DIR, cache_key)
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                sp = StoryPage(f.read(), page)
                self._cache[cache_key] = sp
                return sp

        url = "https://www.literotica.com/s/{}?page={}".format(story_slug, page)
        headers = {
            # Literotica rejects requests whose useragent indicates the
            # python requests library. Nearly anything else is okay.
            'User-Agent': 'Firefox or whatever',
        }
        contents = requests.get(url, headers=headers).text
        with open(cache_file, "w") as f:
            f.write(contents)
        sp = StoryPage(contents, page)
        self._cache[(story_slug, page)] = sp
        return sp

    def all_pages(self, story_slug):
        page1 = self.fetch(story_slug)
        num_pages = page1.page_count()

        result = [page1]
        for pageno in range(2, num_pages + 1):
            result.append(self.fetch(story_slug, pageno))

        return result

    def save(self, story_slug, nav=""):
        pages = self.all_pages(story_slug)
        contents = "".join(page.formatted_text() for page in pages)
        with open("{}.html".format(story_slug), "w") as f:
            f.write(TEMPLATE.format(
                contents=contents,
                title=pages[0].title(),
                author=pages[0].author(),
                author_id=pages[0].author_id(),
                slug=pages[0].slug(),
                description=pages[0].description(),
                nav=nav,
            ))

    def save_series(self, story_slug):
        story = self.fetch(story_slug)
        slugs = story.series_slugs()
        for i, slug in enumerate(slugs):
            nav_items = []
            if i != 0:
                nav_items.append("""<a href="{}.html">Previous</a>""".format(
                    slugs[i-1]
                ))
            if i != len(slugs) - 1:
                nav_items.append("""<a href="{}.html">Next</a>""".format(
                    slugs[i+1]
                ))
            nav = " | ".join(nav_items)
            print("Saving {}".format(slug))
            self.save(slug, nav)


slug = sys.argv[1]

l = Literotica()
l.save_series(slug)
