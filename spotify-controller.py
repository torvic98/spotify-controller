#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
#import traceback
import signal

from gi.repository import GLib

import dbus
import dbus.mainloop.glib

from subprocess import Popen, PIPE

import mutagen
import urllib

current_trackid = ""
old_processes = None
old_metadata = None
last_playbackStatus = None
FNULL = open(os.devnull, 'w')

def quit():
  loop.quit();
  if old_processes is not None:
    (old_process_pacat,old_process_lame) = old_processes
    old_process_pacat.kill()
    old_process_lame.kill()
    os.remove(get_name(old_metadata))
  print "Quit."

def get_name(metadata):
  return u"{0:02d} - {1} - {2}.{3}".format(
            metadata['xesam:trackNumber'],
            metadata['xesam:title'],
            metadata['xesam:artist'][0],
            "mp3")

def get_length(length):
  return u"{0:02d}:{1:02d}".format(
            int(length)/60000000,
            int(length)/1000000%60)

def print_info (metadata):
  print (u"Track:  {0:02d}".format(metadata['xesam:trackNumber']))
  print (u"Title:  {0}".format(metadata['xesam:title']))
  print (u"Artist: {0}".format(metadata['xesam:artist'][0]))
  # print (metadata['mpris:length'])
  print (u"Length: {0}".format(get_length(metadata['mpris:length'])))
  print (u"Disc:   {0}".format(metadata['xesam:discNumber']))
  print (u"Album:  {0}".format(metadata['xesam:album']))
  print (u"A.A.:   {0}".format(metadata['xesam:albumArtist'][0]))
  print (u"Rating: {0}".format(metadata['xesam:autoRating']))
  print (u"Id:     {0}".format(metadata['mpris:trackid']))
  print (u"Art:    {0}".format(metadata['mpris:artUrl']))
  print (u"Url:    {0}".format(metadata['xesam:url']))
  print

def cover_get(id3, _):
  return [img.data for img in id3['APIC'].data]

def cover_set(id3, key, value):
  id3.delall("APIC")
  for v in value:
    id3.add(mutagen.id3.APIC(
        encoding = 3,
        mime     = 'image/jpeg',
        type     = 3,
        desc     = 'cover',
        data     = v))

def add_tags(metadata):

  try:
    audio = mutagen.File(get_name(metadata), easy=True)
    audio.add_tags();

    audio.tags.RegisterKey('cover',cover_get,cover_set)
    audio.delete()
    audio['tracknumber'] = unicode(metadata['xesam:trackNumber'])
    audio['title'] = unicode(metadata['xesam:title'])
    audio['artist'] = map(unicode,metadata['xesam:artist'])
    audio['length'] = unicode(get_length(metadata['mpris:length']))
    audio['discnumber'] = unicode(metadata['xesam:discNumber'])
    audio['album'] = unicode(metadata['xesam:album'])
    audio['albumartist'] = map(unicode,metadata['xesam:albumArtist'])
    audio['discnumber'] = unicode(metadata['xesam:discNumber'])
    audio['cover'] = urllib.urlopen(metadata['mpris:artUrl']).read()
    audio.save()

  except mutagen.MutagenError as e:
    print "Invalid file type"
    raise e

def check_status ():
  global last_playbackStatus
  try:
    properties = dbus.Interface(
              object, "org.freedesktop.DBus.Properties")
    playbackStatus = properties.Get(
              "org.mpris.MediaPlayer2.Player", "PlaybackStatus")
  except dbus.DBusException:
    print "Spotify has been closed"
    sys.exit(0)

  if (last_playbackStatus != playbackStatus):
    last_playbackStatus = playbackStatus
    print ("Spotify is {}".format(playbackStatus))

  GLib.timeout_add(500, check_status)


def handler (interface_name, changed_properties, invaidate_properties):
  global current_trackid
  global old_processes
  global old_metadata
  global FNULL

  try:
    spotify_properties = dbus.Interface(
              object, "org.freedesktop.DBus.Properties")
    metadata = spotify_properties.Get(
              "org.mpris.MediaPlayer2.Player", "Metadata")
  except DBusException:
    print "Spotify has been closed"
    sys.exit(0)

  if (metadata['mpris:trackid'] != current_trackid):
    current_trackid = metadata['mpris:trackid'];
    
    process_pacat = Popen(['pacat', '-r', '--rate=44100', '-d', 
              'alsa_output.pci-0000_00_05.0.analog-stereo.monitor'],
              stdout=PIPE,
              shell=False)

    process_lame = Popen(['lame', '-r', '-V', '0', '-s', '44.1', 
              '-b', '320', '-', get_name(metadata)],
              stdin=process_pacat.stdout,
              stdout=FNULL,
              stderr=FNULL,
              shell=False)

    if old_processes is not None:
      (old_process_pacat,old_process_lame) = old_processes
      old_process_pacat.kill()
      old_process_lame.wait()
      add_tags(old_metadata)

    old_metadata = metadata
    old_processes = (process_pacat,process_lame)

    print_info(metadata)

if __name__ == '__main__':
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    bus = dbus.SessionBus()
    try:
        object = bus.get_object("org.mpris.MediaPlayer2.spotify", "/org/mpris/MediaPlayer2")
        object.connect_to_signal("PropertiesChanged", handler , dbus_interface="org.freedesktop.DBus.Properties")
    
    except dbus.DBusException:
        #traceback.print_exc()
        print "Spotify is not running"
        sys.exit(1)

    GLib.timeout_add(500, check_status)

    signal.signal(signal.SIGTERM, quit)
    signal.signal(signal.SIGINT, quit)

    loop = GLib.MainLoop()
    try:
      loop.run()
    
    except (KeyboardInterrupt, SystemExit):
      quit()
