# -*- coding: utf-8 -*-
# Copyright 2017 Leo Moll and Dominik Schlösser
#

# -- Imports ------------------------------------------------
import os, sys, urllib
import xbmc, xbmcgui, xbmcaddon, xbmcplugin

from de.yeasoft.kodi.KodiLogger import KodiLogger

# -- Classes ------------------------------------------------
class KodiAddon( KodiLogger ):

	def __init__( self ):
		self.addon			= xbmcaddon.Addon()
		self.addon_id		= self.addon.getAddonInfo( 'id' )
		self.icon			= self.addon.getAddonInfo( 'icon' )
		self.fanart			= self.addon.getAddonInfo( 'fanart' )
		self.version		= self.addon.getAddonInfo( 'version' )
		self.path			= self.addon.getAddonInfo( 'path' )
		self.datapath		= os.path.join( xbmc.translatePath( "special://masterprofile" ), 'addon_data', self.addon_id )
		self.language		= self.addon.getLocalizedString
		KodiLogger.__init__( self, self.addon_id, self.version )

	def getSetting( self, id ):
		return self.addon.getSetting( id )

	def setSetting( self, id, value ):
		return self.addon.setSetting( id, value )

class KodiService( KodiAddon ):
	def __init__( self ):
		KodiAddon.__init__( self )

class KodiPlugin( KodiAddon ):
	def __init__( self ):
		KodiAddon.__init__( self )
		self.base_url		= sys.argv[0]
		self.addon_handle	= int( sys.argv[1] )

	def build_url( self, query ):
		return self.base_url + '?' + urllib.urlencode( query )

	def addFolderItem( self, name, params ):
		if type( name ) is int:
			name = self.language( name )
		li = xbmcgui.ListItem( name )
		xbmcplugin.addDirectoryItem(
			handle		= self.addon_handle,
			url			= self.build_url( params ),
			listitem	= li,
			isFolder	= True
		)
