# -*- coding: utf-8 -*-
# Copyright 2017 Leo Moll
#

# -- Imports ------------------------------------------------
import os, stat, string, sqlite3, time
import xbmc

# -- Classes ------------------------------------------------
class StoreSQLite( object ):
	def __init__( self, id, logger, notifier, settings ):
		self.logger		= logger
		self.notifier	= notifier
		self.settings	= settings
		# internals
		self.conn		= None
		self.dbpath		= os.path.join( xbmc.translatePath( "special://masterprofile" ), 'addon_data', id )
		self.dbfile		= os.path.join( xbmc.translatePath( "special://masterprofile" ), 'addon_data', id, 'filmliste01.db' )
		# useful query fragments
		self.sql_query_films	= "SELECT title,show,channel,description,duration,size,datetime(aired, 'unixepoch', 'localtime'),url_video,url_video_sd,url_video_hd FROM film LEFT JOIN show ON show.id=film.showid LEFT JOIN channel ON channel.id=film.channelid"
		self.sql_cond_nofuture	= " AND ( ( aired IS NULL ) OR ( ( UNIX_TIMESTAMP() - aired ) > 0 ) )" if settings.nofuture else ""
		self.sql_cond_minlength	= " AND ( ( duration IS NULL ) OR ( duration >= %d ) )" % settings.minlength if settings.minlength > 0 else ""

	def Init( self, reset = False ):
		self.logger.info( 'Using SQLite version {}, python library sqlite3 version {}', sqlite3.sqlite_version, sqlite3.version )
		if not self._dir_exists( self.dbpath ):
			os.mkdir( self.dbpath )
		if reset == True or not self._file_exists( self.dbfile ):
			self.logger.info( '===== RESET: Database will be deleted and regenerated =====' )
			self._file_remove( self.dbfile )
			self.conn = sqlite3.connect( self.dbfile )
			self.Reset()
		else:
			self.conn = sqlite3.connect( self.dbfile )
		self.conn.create_function( 'UNIX_TIMESTAMP', 0, UNIX_TIMESTAMP )
		self.conn.create_aggregate( 'GROUP_CONCAT', 1, GROUP_CONCAT )

	def Exit( self ):
		if self.conn is not None:
			self.conn.close()
			self.conn	= None

	def Search( self, search, filmui ):
		self.SearchCondition( '( title LIKE "%%%s%%")' % search, filmui, True, True )

	def SearchFull( self, search, filmui ):
		self.SearchCondition( '( ( title LIKE "%%%s%%") OR ( description LIKE "%%%s%%") )' % ( search, search ), filmui, True, True )

	def GetRecents( self, filmui ):
		self.SearchCondition( '( ( UNIX_TIMESTAMP() - aired ) <= 86400 )', filmui, True, True )

	def GetLiveStreams( self, filmui ):
		self.SearchCondition( '( show.search="LIVESTREAM" )', filmui, False, False )

	def GetChannels( self, channelui ):
		if self.conn is None:
			return
		try:
			self.logger.info( 'SQLite Query: {}', "SELECT id,channel FROM channel" )
			cursor = self.conn.cursor()
			cursor.execute( 'SELECT id,channel FROM channel' )
			channelui.Begin()
			for ( channelui.id, channelui.channel ) in cursor:
				channelui.Add()
			channelui.End()
			cursor.close()
		except sqlite3.Error as err:
			self.logger.error( 'Database error: {}', err )
			self.notifier.ShowDatabaseError( err )

	def GetInitials( self, channelid, initialui ):
		if self.conn is None:
			return
		try:
			condition = 'WHERE ( channelid=' + str( channelid ) + ' ) ' if channelid != '0' else ''
			self.logger.info( 'SQlite Query: {}', 
				'SELECT SUBSTR(search,1,1),COUNT(*) FROM show ' +
				condition +
				'GROUP BY LEFT(search,1)'
			)
			cursor = self.conn.cursor()
			cursor.execute(
				'SELECT SUBSTR(search,1,1),COUNT(*) FROM show ' +
				condition +
				'GROUP BY SUBSTR(search,1,1)'
			)
			initialui.Begin( channelid )
			for ( initialui.initial, initialui.count ) in cursor:
				initialui.Add()
			initialui.End()
			cursor.close()
		except sqlite3.Error as err:
			self.logger.error( 'Database error: {}', err )
			self.notifier.ShowDatabaseError( err )

	def GetShows( self, channelid, initial, showui ):
		if self.conn is None:
			return
		try:
			if channelid == '0' and self.settings.groupshows:
				query = 'SELECT GROUP_CONCAT(show.id),GROUP_CONCAT(channelid),show,GROUP_CONCAT(channel) FROM show LEFT JOIN channel ON channel.id=show.channelid WHERE ( show LIKE "%s%%" ) GROUP BY show' % initial
			elif channelid == '0':
				query = 'SELECT show.id,show.channelid,show.show,channel.channel FROM show LEFT JOIN channel ON channel.id=show.channelid WHERE ( show LIKE "%s%%" )' % initial
			else:
				query = 'SELECT show.id,show.channelid,show.show,channel.channel FROM show LEFT JOIN channel ON channel.id=show.channelid WHERE ( channelid=%s ) AND ( show LIKE "%s%%" )' % ( channelid, initial )
			self.logger.info( 'SQLite Query: {}', query )
			cursor = self.conn.cursor()
			cursor.execute( query )
			showui.Begin( channelid )
			for ( showui.id, showui.channelid, showui.show, showui.channel ) in cursor:
				showui.Add()
			showui.End()
			cursor.close()
		except sqlite3.Error as err:
			self.logger.error( 'Database error: {}', err )
			self.notifier.ShowDatabaseError( err )

	def GetFilms( self, showid, filmui ):
		if self.conn is None:
			return
		if showid.find( ',' ) == -1:
			# only one channel id
			condition = '( showid=%s )' % showid
			showchannels = False
		else:
			# multiple channel ids
			condition = '( showid IN ( %s ) )' % showid
			showchannels = True
		self.SearchCondition( condition, filmui, False, showchannels )

	def SearchCondition( self, condition, filmui, showshows, showchannels ):
		if self.conn is None:
			return
		try:
			self.logger.info( 'SQLite Query: {}', 
				self.sql_query_films +
				' WHERE ' +
				condition +
				self.sql_cond_nofuture +
				self.sql_cond_minlength
			)
			cursor = self.conn.cursor()
			cursor.execute(
				self.sql_query_films +
				' WHERE ' +
				condition +
				self.sql_cond_nofuture +
				self.sql_cond_minlength
			)
			filmui.Begin( showshows, showchannels )
			for ( filmui.title, filmui.show, filmui.channel, filmui.description, filmui.seconds, filmui.size, filmui.aired, filmui.url_video, filmui.url_video_sd, filmui.url_video_hd ) in cursor:
				filmui.Add()
			filmui.End()
			cursor.close()
		except sqlite3.Error as err:
			self.logger.error( 'Database error: {}', err )
			self.notifier.ShowDatabaseError( err )

	def GetStatus( self ):
		status = {
			'modified': int( time.time() ),
			'status': '',
			'lastupdate': 0,
			'add_chn': 0,
			'add_shw': 0,
			'add_mov': 0,
			'del_chn': 0,
			'del_shw': 0,
			'del_mov': 0,
			'tot_chn': 0,
			'tot_shw': 0,
			'tot_mov': 0,
			'description': ''
		}
		if self.conn is None:
			status['status'] = "UNINIT"
			return status
		cursor = self.conn.cursor()
		cursor.execute( 'SELECT * FROM `status` LIMIT 1' )
		r = cursor.fetchall()
		cursor.close()
		if len( r ) == 0:
			status['status'] = "NONE"
			return status
		status['modified']		= r[0][0]
		status['status']		= r[0][1]
		status['lastupdate']	= r[0][2]
		status['add_chn']		= r[0][3]
		status['add_shw']		= r[0][4]
		status['add_mov']		= r[0][5]
		status['del_chn']		= r[0][6]
		status['del_shw']		= r[0][7]
		status['del_mov']		= r[0][8]
		status['tot_chn']		= r[0][9]
		status['tot_shw']		= r[0][10]
		status['tot_mov']		= r[0][11]
		status['description']	= r[0][12]
		return status

	def UpdateStatus( self, status = None, description = None, lastupdate = None, add_chn = None, add_shw = None, add_mov = None, del_chn = None, del_shw = None, del_mov = None, tot_chn = None, tot_shw = None, tot_mov = None ):
		if self.conn is None:
			return
		new = self.GetStatus()
		old = new['status']
		if status is not None:
			new['status'] = status
		if lastupdate is not None:
			new['lastupdate'] = lastupdate
		if add_chn is not None:
			new['add_chn'] = add_chn
		if add_shw is not None:
			new['add_shw'] = add_shw
		if add_mov is not None:
			new['add_mov'] = add_mov
		if del_chn is not None:
			new['del_chn'] = del_chn
		if del_shw is not None:
			new['del_shw'] = del_shw
		if del_mov is not None:
			new['del_mov'] = del_mov
		if tot_chn is not None:
			new['tot_chn'] = tot_chn
		if tot_shw is not None:
			new['tot_shw'] = tot_shw
		if tot_mov is not None:
			new['tot_mov'] = tot_mov
		if description is not None:
			new['description'] = description
		# TODO: we should only write, if we have changed something...
		new['modified'] = int( time.time() )
		cursor = self.conn.cursor()
		if old == "NONE":
			# insert status
			cursor.execute(
				"""
				INSERT INTO `status` (
					`modified`,
					`status`,
					`lastupdate`,
					`add_chn`,
					`add_shw`,
					`add_mov`,
					`del_chm`,
					`del_shw`,
					`del_mov`,
					`tot_chn`,
					`tot_shw`,
					`tot_mov`,
					`description`
				)
				VALUES (
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?
				)
				""", (
					new['modified'],
					new['status'],
					new['lastupdate'],
					new['add_chn'],
					new['add_shw'],
					new['add_mov'],
					new['del_chn'],
					new['del_shw'],
					new['del_mov'],
					new['tot_chn'],
					new['tot_shw'],
					new['tot_mov'],
					new['description']
				)
			)
		else:
			# update status
			cursor.execute(
				"""
				UPDATE `status`
				SET		`modified`		= ?,
						`status`		= ?,
						`lastupdate`	= ?,
						`add_chn`		= ?,
						`add_shw`		= ?,
						`add_mov`		= ?,
						`del_chm`		= ?,
						`del_shw`		= ?,
						`del_mov`		= ?,
						`tot_chn`		= ?,
						`tot_shw`		= ?,
						`tot_mov`		= ?,
						`description`	= ?
				""", (
					new['modified'],
					new['status'],
					new['lastupdate'],
					new['add_chn'],
					new['add_shw'],
					new['add_mov'],
					new['del_chn'],
					new['del_shw'],
					new['del_mov'],
					new['tot_chn'],
					new['tot_shw'],
					new['tot_mov'],
					new['description']
				)
			)
		cursor.close()
		self.conn.commit()

	def SupportsUpdate( self ):
		return True

	def ftInit( self ):
		self.ft_channel = None
		self.ft_channelid = None
		self.ft_show = None
		self.ft_showid = None

	def ftUpdateStart( self, full = True ):
		cursor = self.conn.cursor()
		if full:
			cursor.executescript( """
				UPDATE	`channel`
				SET		`touched` = 0;

				UPDATE	`show`
				SET		`touched` = 0;

				UPDATE	`film`
				SET		`touched` = 0;
			""" )
		cursor.execute( 'SELECT COUNT(*) FROM `channel`' )
		r1 = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `show`' )
		r2 = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `film`' )
		r3 = cursor.fetchone()
		cursor.close()
		self.conn.commit()
		return ( r1[0], r2[0], r3[0], )

	def ftUpdateEnd( self, aborted ):
		cursor = self.conn.cursor()
		cursor.execute( 'SELECT COUNT(*) FROM `channel` WHERE ( touched = 0 )' )
		( del_chn, ) = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `show` WHERE ( touched = 0 )' )
		( del_shw, ) = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `film` WHERE ( touched = 0 )' )
		( del_mov, ) = cursor.fetchone()
		if aborted:
			del_chn = 0
			del_shw = 0
			del_mov = 0
		else:
			cursor.execute( 'DELETE FROM `show` WHERE ( show.touched = 0 ) AND ( ( SELECT SUM( film.touched ) FROM `film` WHERE film.showid = show.id ) = 0 )' )
			cursor.execute( 'DELETE FROM `film` WHERE ( touched = 0 )' )
		cursor.execute( 'SELECT COUNT(*) FROM `channel`' )
		( cnt_chn, ) = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `show`' )
		( cnt_shw, ) = cursor.fetchone()
		cursor.execute( 'SELECT COUNT(*) FROM `film`' )
		( cnt_mov, ) = cursor.fetchone()
		cursor.close()
		self.conn.commit()
		return ( del_chn, del_shw, del_mov, cnt_chn, cnt_shw, cnt_mov, )

	def ftInsertFilm( self, film ):
		cursor = self.conn.cursor()
		newchn = False
		inschn = 0
		insshw = 0
		insmov = 0

		# handle channel
		if self.ft_channel != film['channel']:
			# process changed channel
			newchn = True
			cursor.execute( 'SELECT `id`,`touched` FROM `channel` WHERE channel.channel=?', ( film['channel'], ) )
			r = cursor.fetchall()
			if len( r ) > 0:
				# get the channel data
				self.ft_channel = film['channel']
				self.ft_channelid = r[0][0]
				if r[0][1] == 0:
					# updated touched
					cursor.execute( 'UPDATE `channel` SET `touched`=1 WHERE ( channel.id=? )', ( self.ft_channelid, ) )
					self.conn.commit()
			else:
				# insert the new channel
				inschn = 1
				cursor.execute( 'INSERT INTO `channel` ( `dtCreated`,`channel` ) VALUES ( ?,? )', ( int( time.time() ), film['channel'] ) )
				self.ft_channel = film['channel']
				self.ft_channelid = cursor.lastrowid
				self.conn.commit()

		# handle show
		if newchn or self.ft_show != film['show']:
			# process changed show
			cursor.execute( 'SELECT `id`,`touched` FROM `show` WHERE ( show.channelid=? ) AND ( show.show=? )', ( self.ft_channelid, film['show'] ) )
			r = cursor.fetchall()
			if len( r ) > 0:
				# get the show data
				self.ft_show = film['show']
				self.ft_showid = r[0][0]
				if r[0][1] == 0:
					# updated touched
					cursor.execute( 'UPDATE `show` SET `touched`=1 WHERE ( show.id=? )', ( self.ft_showid, ) )
					self.conn.commit()
			else:
				# insert the new show
				insshw = 1
				cursor.execute(
					"""
					INSERT INTO `show` (
						`dtCreated`,
						`channelid`,
						`show`,
						`search`
					)
					VALUES (
						?,
						?,
						?,
						?
					)
					""", (
						int( time.time() ),
						self.ft_channelid, film['show'],
						self._make_search( film['show'] )
					)
				)
				self.ft_show = film['show']
				self.ft_showid = cursor.lastrowid
				self.conn.commit()

		# check if the movie is there
		cursor.execute( """
			SELECT		`id`,
						`touched`
			FROM		`film`
			WHERE		( film.channelid = ? )
						AND
						( film.showid = ? )
						AND
						( film.url_video = ? )
		""", ( self.ft_channelid, self.ft_showid, film['url_video'] ) )
		r = cursor.fetchall()
		if len( r ) > 0:
			# film found
			filmid = r[0][0]
			if r[0][1] == 0:
				# update touched
				cursor.execute( 'UPDATE `film` SET `touched`=1 WHERE ( film.id=? )', ( filmid, ) )
				self.conn.commit()
		else:
			# insert the new film
			insmov = 1
			cursor.execute(
				"""
				INSERT INTO `film` (
					`dtCreated`,
					`channelid`,
					`showid`,
					`title`,
					`search`,
					`aired`,
					`duration`,
					`size`,
					`description`,
					`website`,
					`url_sub`,
					`url_video`,
					`url_video_sd`,
					`url_video_hd`
				)
				VALUES (
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?,
					?
				)
				""", (
					int( time.time() ),
					self.ft_channelid,
					self.ft_showid,
					film['title'],
					self._make_search( film['title'] ),
					film['airedepoch'],
					self._make_duration( film['duration'] ),
					film['size'],
					film['description'],
					film['website'],
					film['url_sub'],
					film['url_video'],
					film['url_video_sd'],
					film['url_video_hd']
				)
			)
			filmid = cursor.lastrowid
			self.conn.commit()
		cursor.close()
		return ( filmid, inschn, insshw, insmov )

	def Reset( self ):
		self.conn.executescript( """
PRAGMA foreign_keys = false;

-- ----------------------------
--  Table structure for channel
-- ----------------------------
DROP TABLE IF EXISTS "channel";
CREATE TABLE "channel" (
	 "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	 "dtCreated" integer(11,0) NOT NULL DEFAULT 0,
	 "touched" integer(1,0) NOT NULL DEFAULT 1,
	 "channel" TEXT(255,0) NOT NULL
);

-- ----------------------------
--  Table structure for film
-- ----------------------------
DROP TABLE IF EXISTS "film";
CREATE TABLE "film" (
	 "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	 "dtCreated" integer(11,0) NOT NULL DEFAULT 0,
	 "touched" integer(1,0) NOT NULL DEFAULT 1,
	 "channelid" INTEGER(11,0) NOT NULL,
	 "showid" INTEGER(11,0) NOT NULL,
	 "title" TEXT(255,0) NOT NULL,
	 "search" TEXT(255,0) NOT NULL,
	 "aired" integer(11,0),
	 "duration" integer(11,0),
	 "size" integer(11,0),
	 "description" TEXT(2048,0),
	 "website" TEXT(384,0),
	 "url_sub" TEXT(384,0),
	 "url_video" TEXT(384,0),
	 "url_video_sd" TEXT(384,0),
	 "url_video_hd" TEXT(384,0),
	CONSTRAINT "FK_FilmShow" FOREIGN KEY ("showid") REFERENCES "show" ("id") ON DELETE CASCADE,
	CONSTRAINT "FK_FilmChannel" FOREIGN KEY ("channelid") REFERENCES "channel" ("id") ON DELETE CASCADE
);

-- ----------------------------
--  Table structure for show
-- ----------------------------
DROP TABLE IF EXISTS "show";
CREATE TABLE "show" (
	 "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
	 "dtCreated" integer(11,0) NOT NULL DEFAULT 0,
	 "touched" integer(1,0) NOT NULL DEFAULT 1,
	 "channelid" INTEGER(11,0) NOT NULL DEFAULT 0,
	 "show" TEXT(255,0) NOT NULL,
	 "search" TEXT(255,0) NOT NULL,
	CONSTRAINT "FK_ShowChannel" FOREIGN KEY ("channelid") REFERENCES "channel" ("id") ON DELETE CASCADE
);

-- ----------------------------
--  Table structure for status
-- ----------------------------
DROP TABLE IF EXISTS "status";
CREATE TABLE "status" (
	 "modified" integer(11,0),
	 "status" TEXT(32,0),
	 "lastupdate" integer(11,0),
	 "add_chn" integer(11,0),
	 "add_shw" integer(11,0),
	 "add_mov" integer(11,0),
	 "del_chm" integer(11,0),
	 "del_shw" integer(11,0),
	 "del_mov" integer(11,0),
	 "tot_chn" integer(11,0),
	 "tot_shw" integer(11,0),
	 "tot_mov" integer(11,0),
	 "description" TEXT(512,0)
);

-- ----------------------------
--  Indexes structure for table film
-- ----------------------------
CREATE INDEX "dupecheck" ON film ("channelid", "showid", "url_video");
CREATE INDEX "index_1" ON film ("channelid", "title" COLLATE NOCASE);
CREATE INDEX "index_2" ON film ("showid", "title" COLLATE NOCASE);

-- ----------------------------
--  Indexes structure for table show
-- ----------------------------
CREATE INDEX "category" ON show ("category");
CREATE INDEX "search" ON show ("search");
CREATE INDEX "combined_1" ON show ("channelid", "search");
CREATE INDEX "combined_2" ON show ("channelid", "show");

PRAGMA foreign_keys = true;
		""" )
		self.UpdateStatus( 'IDLE', '' )

	def _make_search( self, val ):
		cset = string.letters + string.digits + ' _-#'
		search = ''.join( [ c for c in val if c in cset ] )
		return search.upper().strip()

	def _make_duration( self, val ):
		if val == "00:00:00":
			return None
		elif val is None:
			return None
		x = val.split( ':' )
		if len( x ) != 3:
			return None
		return int( x[0] ) * 3600 + int( x[1] ) * 60 + int( x[2] )

	def _dir_exists( self, name ):
		try:
			s = os.stat( name )
			return stat.S_ISDIR( s.st_mode )
		except OSError as err:
			return False

	def _file_exists( self, name ):
		try:
			s = os.stat( name )
			return stat.S_ISREG( s.st_mode )
		except OSError as err:
			return False

	def _file_remove( self, name ):
		if self._file_exists( name ):
			try:
				os.remove( name )
				return True
			except OSError as err:
				self.logger.error( 'Failed to remove {}: error {}', name, err )
		return False

def UNIX_TIMESTAMP():
	return int( time.time() )

class GROUP_CONCAT:
	def __init__( self ):
		self.value = ''

	def step( self, value ):
		if value is not None:
			if self.value == '':
				self.value = '{0}'.format( value )
			else:
				self.value = '{0},{1}'.format( self.value, value )

	def finalize(self):
		return self.value