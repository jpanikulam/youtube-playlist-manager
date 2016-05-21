'''This is a personal tool for managing youtube playlists

python youtube.py -h
'''
import sys
import requests
import json
from bs4 import BeautifulSoup
from os import path
import os
import argparse
here = path.realpath(path.join(__file__, '..'))


class PlaylistGetter(object):
    _root_url = 'http://youtube.com'
    _disallowed_titles = ['[Private Video]', '[Deleted Video]']

    def __init__(self, _id):
        # Get rid of a possible '/''
        self.playlist_id = path.split(_id)[-1]
        self.session = requests.Session()
        self.pages = []
        self.videos = []
        self.next_url = None
        self.videos = self.get_all_videos()

    def get_all_videos(self):
        self.get_playlist_main()
        for k in range(20):
            pg_soup = self.get_next()
            if pg_soup is None:
                break
            else:
                self.pages.append(pg_soup)

        videos = []
        for soup in self.pages:
            videos.extend(self.find_videos(soup))
        return videos

    def find_videos(self, page):
        potential_videos = page.find_all('tr')
        video_names = []
        for pot_vid in potential_videos:
            if 'pl-video' in pot_vid['class']:
                title = pot_vid['data-title'].encode('utf-8').strip()
                if title in self._disallowed_titles:
                    continue

                video_names.append(title)
        return video_names

    def get_playlist_main(self):
        url = path.join(self._root_url, self.playlist_id)
        playlist_html = self.session.get(url)
        self.session.headers.update({'referer': url})
        soup = BeautifulSoup(playlist_html.text, 'html.parser')
        self.pages.append(soup)
        self.next_url = self.get_next_url(soup)

    def get_next_url(self, soup):
        attrs = {'data-uix-load-more-target-id': 'pl-load-more-destination'}
        found = soup.find_all(attrs=attrs)
        if len(found) == 0:
            return None
        next_tag = found[0]
        next_url = next_tag['data-uix-load-more-href']
        return next_url

    def get_next(self):
        if self.next_url is None:
            return None

        response = self.session.get(self._root_url + self.next_url)
        data = json.loads(response.text)
        load_more = data['load_more_widget_html']
        content = data['content_html']
        soup = BeautifulSoup(content, 'html.parser')
        if len(load_more) == 0:
            self.next_url = None
        else:
            self.next_url = self.get_next_url(BeautifulSoup(load_more, 'html.parser'))
        return soup

    @property
    def cache_filename(self):
        return path.join(here, self.playlist_id + '.json')

    def cache(self):
        '''Saves to json'''
        with open(self.cache_filename, 'w') as outfile:
            json.dump(self.videos, outfile, indent=1)

    def check_cache(self):
        '''Compares to json'''

        # Cache if the playlist is not already cached
        if not path.isfile(self.cache_filename):
            self.cache()

        with open(self.cache_filename) as data_file:
            contents = json.load(data_file)

        utf8_contents = map(lambda o: o.encode('utf-8'), contents)
        result = {
            'removed': set(utf8_contents) - set(self.videos),
            'added': set(self.videos) - set(utf8_contents),
        }

        return result


if __name__ == '__main__':
    usage_msg = "Give a youtube playlist id or a list of playlist ids!"
    desc_msg = "A tool for checking if videos have been deletd from your playlist"

    parser = argparse.ArgumentParser(usage=usage_msg, description=desc_msg)

    _help = ("The playlist id you'd like to use, looks like /playlist?list=PLJdSOdTNxWp_VEyljsy4LMSNb9NT67euu" +
             " can be a space-separated list. Write 'all' if you just want to check all cached playlists against youtube")
    # You can do all of these at once, if you want
    parser.add_argument(dest="playlist_id", nargs="+",
                        help=_help)

    parser.add_argument('--diff', dest='diff', action='store_true',
                        help="Print the videos that have been added or removed")
    parser.add_argument('--update', dest='update', action='store_true',
                        help="Add newly added videos to the cache (without overwriting removed videos), use this.")
    parser.add_argument('--overwrite', dest='overwrite', action='store_true',
                        help="Overwrite the existing cache with what we find on youtube")

    args = parser.parse_args(sys.argv[1:])

    if args.playlist_id == 'all':
        files_here = os.listdir(here)
        playlists = [playlist for playlist, ext in map(path.splitext, files_here) if '.json' == ext]
    else:
        playlists = list(args.playlist_id)

    for playlist_id in playlists:
        print '---------------------------------------------'
        print 'Looking at {}'.format(playlist_id)
        pg = PlaylistGetter(playlist_id)
        if args.diff:
            print '---Diff---'
            diff = pg.check_cache()
            print 'Newly added:'
            print '\n\t' + '\n\t'.join(diff['added'])
            print 'Removed from youtube:'
            print '\n\t' + '\n\t'.join(diff['removed'])

        if args.overwrite:
            print '---Overriding current cache---'
            pg.cache()

        if args.update:
            print '---Updating Cache---'
            diff = pg.check_cache()
            pg_vids = set(pg.videos)
            removed = diff['removed']
            print "Adding to cache:"
            print '\n\t' + '\n\t'.join(diff['added'])
            all_vids = pg_vids.union(removed)
            pg.videos = list(all_vids)
            pg.cache()
