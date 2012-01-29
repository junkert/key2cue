import os
import re
import sys
import math
import shutil
from optparse import OptionParser
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

MAX_CD_LENGTH = 4800  #80 min * 60 sec

def build_list(from_path):
  listing = {}
  re_mp3 = re.compile(r'.mp3$')
  re_artist_bpm = re.compile(
    r'([0-9]+[A-Ba-b]|[0-9]+[A-Ba-b]\/[0-9]+[A-Ba-b])\s*\-\s*([0-9]+\.[0-9]+|[0-9]+)\s*-\s*')
  re_artist_no_bpm = re.compile(
    r'([0-9]+[A-Ba-b])+\s*-\s*')
  for (dirpath, dirnames, filenames) in os.walk(from_path):
    for filename in filenames:
      if not re_mp3.search(filename):
        continue
      track_path = os.path.join(dirpath, filename)
      # Some mp3s do not have ID3 tags. Skip them.
      try:
        track_id3  = EasyID3(track_path)
        track_mp3  = MP3(track_path)
        if not track_id3.has_key('artist') or\
           not track_id3.has_key('title') or\
           not track_id3.has_key('genre'):
          print "[ERROR]: %s is missing ID3 tags!" % tack_path
          continue
      except:
        continue
      try:
        id3_dict = {'artist':   track_id3['artist'][0],
                    'title':    track_id3['title'][0],
                    'genre':    track_id3['genre'][0],
                    'length':   int(math.ceil(track_mp3.info.length)),
                    'filename': filename,
                    'path':     track_path}
      except KeyError:
        id3_dict = {'artist':   track_id3['artist'][0],
                    'title':    track_id3['title'][0],
                    'genre':    'N/A',
                    'length':   int(math.ceil(track_mp3.info.length)),
                    'filename': filename,
                    'path':     track_path}
      keys = []
      if re_artist_bpm.match(id3_dict['artist']):
        s = re_artist_bpm.split(id3_dict['artist'])
        if len(s) < 3:
          print "ERROR: %s does not contain proper format!" % track_path
          continue
        s[1] = s[1].strip(' ').rstrip('-')
        s[2] = s[2].strip(' ').lstrip('-').rstrip('-')
        s[3] = s[3].lstrip(' ').rstrip(' ').lstrip('-').rstrip('-')
        id3_dict['key'] = s[1]
        id3_dict['bpm'] = s[2]
        id3_dict['artist'] = s[3]
        if re.search(r"\/", s[1]):
          keys = re.split(r"\/", s[1])
        else:
          keys.append(s[1].strip(' '))
      else:
        s = re_artist_no_bpm.split(id3_dict['artist'])
        if len(s) < 3:
          print "ERROR: %s does not contain proper format!" % track_path
          continue
        id3_dict['artist'] = s[2]
        if re.search(r"\/", s[1]):
          keys = re.split(r"\/", s[1])
        else:
          keys.append(s[1])
      for k in keys:
        if not listing.has_key(id3_dict['genre']):
          listing[id3_dict['genre']] = {}
        if not listing[id3_dict['genre']].has_key(k):
          listing[id3_dict['genre']][k] = []
        id3_dict['key'] = k
        listing[id3_dict['genre']][k].append(id3_dict)  
      
  return listing

def copy_data(listing, to_path):
  counters = {'cds':    1,
              'tracks': 0,
              'mins':   0}
  for genre in listing:
    cd_count = 1
    cd_min_total = 0
    genre_path = os.path.join(to_path, genre)
    for key in listing[genre]:
      cd_count = 1
      counters['cds'] += 1
      counters['mins'] += cd_min_total
      cd_min_total = 0
      key_path = os.path.join(genre_path, key)
      cd_track_list = []
      dst = ""
      for t in listing[genre][key]:
        counters['tracks'] += 1
        if (cd_min_total + t['length']) > MAX_CD_LENGTH:
          make_track_sheet(counters['cds'], cd_track_list, to_path)
          cd_count += 1
          counters['cds'] += 1
          cd_min_total = 0
        cd_min_total    += t['length']
        cd_path = os.path.join(key_path, "CD%d" % cd_count)
        try:
          os.listdir(cd_path)
        except OSError:
          print "[Creating] %s" % (cd_path)
          os.makedirs(cd_path)
        dst = os.path.join(cd_path, "%s - %s.mp3" % (t['artist'], t['title']))
        try:
          os.stat(dst)
          print "\n\n[WARNING] file already exists %s\n%s\n" %(dst, t)
        except OSError:
          try:
            print "\n\n[Copying] %s => %s\n%s\n\n" % (t['path'], dst, t)
            shutil.copyfile(t['path'], dst)
            cd_track_list.append(t)
            counters['tracks'] += 1
          except shutil.Error:
            print "[ERROR] Unable to copy to %s" % (dst)
          except IOError:
            print "[ERROR] Unable to copy to %s" % (dst)
          except UnicodeEncodeError:
            print "[ERROR] Unable to decode id3tag for %s" % (t['path'])
      if len(cd_track_list) > 0:
        make_track_sheet(counters['cds'], cd_track_list, to_path)
  return counters

def make_track_sheet(cd_count, list, out_path):
    tmp = list[0]
    fh = open(os.path.join(out_path, "%s_%s_track_list.txt" % (tmp['genre'], tmp['key'])), 'w')
    fh.write("CD:    %d\n" % cd_count)
    fh.write("GENRE: %s\n" % tmp['genre'])
    fh.write("KEY:   %s\n\n\n" % tmp['key'])
    counter = 1
    for track in list:
      tn = "%d. %s - %s" % (counter, track['artist'], track['title'])
      if track.has_key('bpm'):
        tn = "%s [%s bpm]" % (tn, track['bpm'])
      tn_l = len(tn)
      if tn_l > 40 and tn_l < 80:
        fh.write("%s\n   %s\n" % (tn[0:40], tn[41:]))
      elif tn_l > 80:
        fh.write("%s\n   %s\n   %s\n" % (tn[0:40], tn[41:77], tn[78:]))
      else:
        fh.write("%s\n" % (tn))
      counter += 1
    fh.close()

def parse_args():
  usage = '%prog --from-path=<path> --to-path=<path>'
  parser = OptionParser(usage=usage)
  parser.add_option('--from-path',
                    dest    ='from_path',
                    action  ='store',
                    help    ='Root folder to crawl for MP3s')
  parser.add_option('--to-path',
                    dest    = 'to_path',
                    action  = 'store',
                    help    = 'Root folder to store CDs to')
  opts, args = parser.parse_args()
  if not opts.from_path or \
     not opts.to_path:
    parser.error("Must provide a to and from path!")
  
  return opts, args


def main():
  opts,args  = parse_args()
  listing    = build_list(opts.from_path)
  counters   = copy_data(listing, opts.to_path)
  
  hours = int(counters['mins'] / 60)
  mins  = counters['mins'] - (hours * 60)

  print "Number of CDs: %d" % counters['cds']
  print "Total Time: %d:%d" % (hours, mins)
  print "Tracks: %d" % counters['tracks']


if __name__ == '__main__':
    main()
