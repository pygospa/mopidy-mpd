from __future__ import annotations

from typing import TYPE_CHECKING, Never

from mopidy.core import PlaybackState
from mopidy.types import DurationMs, Percentage, TracklistId

from mopidy_mpd import exceptions, protocol

if TYPE_CHECKING:
    from mopidy_mpd.context import MpdContext


@protocol.commands.add("consume", state=protocol.BOOL)
def consume(context: MpdContext, state: bool) -> None:  # noqa: FBT001
    """
    *musicpd.org, playback section:*

        ``consume {STATE}``

        Sets consume state to ``STATE``, ``STATE`` should be 0 or
        1. When consume is activated, each song played is removed from
        playlist.
    """
    context.core.tracklist.set_consume(state)


@protocol.commands.add("crossfade", seconds=protocol.UINT)
def crossfade(context: MpdContext, seconds: int) -> Never:
    """
    *musicpd.org, playback section:*

        ``crossfade {SECONDS}``

        Sets crossfading between songs.
    """
    raise exceptions.MpdNotImplementedError  # TODO


@protocol.commands.add("mixrampdb")
def mixrampdb(context: MpdContext, decibels: str) -> Never:
    """
    *musicpd.org, playback section:*

        ``mixrampdb {deciBels}``

    Sets the threshold at which songs will be overlapped. Like crossfading but
    doesn't fade the track volume, just overlaps. The songs need to have
    MixRamp tags added by an external tool. 0dB is the normalized maximum
    volume so use negative values, I prefer -17dB. In the absence of mixramp
    tags crossfading will be used. See
    https://sourceforge.net/projects/mixramp/
    """
    raise exceptions.MpdNotImplementedError  # TODO


@protocol.commands.add("mixrampdelay", seconds=protocol.UINT)
def mixrampdelay(context: MpdContext, seconds: int) -> Never:
    """
    *musicpd.org, playback section:*

        ``mixrampdelay {SECONDS}``

        Additional time subtracted from the overlap calculated by mixrampdb. A
        value of "nan" disables MixRamp overlapping and falls back to
        crossfading.
    """
    raise exceptions.MpdNotImplementedError  # TODO


@protocol.commands.add("next")
def next_(context: MpdContext) -> None:
    """
    *musicpd.org, playback section:*

        ``next``

        Plays next song in the playlist.

    *MPD's behaviour when affected by repeat/random/single/consume:*

        Given a playlist of three tracks numbered 1, 2, 3, and a currently
        playing track ``c``. ``next_track`` is defined at the track that
        will be played upon calls to ``next``.

        Tests performed on MPD 0.15.4-1ubuntu3.

        ======  ======  ======  =======  =====  =====  =====  =====
                    Inputs                    next_track
        -------------------------------  -------------------  -----
        repeat  random  single  consume  c = 1  c = 2  c = 3  Notes
        ======  ======  ======  =======  =====  =====  =====  =====
        T       T       T       T        2      3      EOPL
        T       T       T       .        Rand   Rand   Rand   [1]
        T       T       .       T        Rand   Rand   Rand   [4]
        T       T       .       .        Rand   Rand   Rand   [4]
        T       .       T       T        2      3      EOPL
        T       .       T       .        2      3      1
        T       .       .       T        3      3      EOPL
        T       .       .       .        2      3      1
        .       T       T       T        Rand   Rand   Rand   [3]
        .       T       T       .        Rand   Rand   Rand   [3]
        .       T       .       T        Rand   Rand   Rand   [2]
        .       T       .       .        Rand   Rand   Rand   [2]
        .       .       T       T        2      3      EOPL
        .       .       T       .        2      3      EOPL
        .       .       .       T        2      3      EOPL
        .       .       .       .        2      3      EOPL
        ======  ======  ======  =======  =====  =====  =====  =====

        - When end of playlist (EOPL) is reached, the current track is
          unset.
        - [1] When *random* and *single* is combined, ``next`` selects
          a track randomly at each invocation, and not just the next track
          in an internal prerandomized playlist.
        - [2] When *random* is active, ``next`` will skip through
          all tracks in the playlist in random order, and finally EOPL is
          reached.
        - [3] *single* has no effect in combination with *random*
          alone, or *random* and *consume*.
        - [4] When *random* and *repeat* is active, EOPL is never
          reached, but the playlist is played again, in the same random
          order as the first time.

    """
    context.core.playback.next().get()


@protocol.commands.add("pause", state=protocol.BOOL)
def pause(context: MpdContext, state: bool | None = None) -> None:
    """
    *musicpd.org, playback section:*

        ``pause {PAUSE}``

        Toggles pause/resumes playing, ``PAUSE`` is 0 or 1.

    *MPDroid:*

    - Calls ``pause`` without any arguments to toogle pause.
    """
    match state:
        case None:
            # Deprecated: Calling `pause` without any arguments
            playback_state = context.core.playback.get_state().get()
            if playback_state == PlaybackState.PLAYING:
                context.core.playback.pause().get()
            elif playback_state == PlaybackState.PAUSED:
                context.core.playback.resume().get()
        case True:
            context.core.playback.pause().get()
        case False:
            context.core.playback.resume().get()


@protocol.commands.add("play", songpos=protocol.INT)
def play(context: MpdContext, songpos: int | None = None) -> None:
    """
    *musicpd.org, playback section:*

        ``play [SONGPOS]``

        Begins playing the playlist at song number ``SONGPOS``.

    The original MPD server resumes from the paused state on ``play``
    without arguments.

    *Clarifications:*

    - ``play "-1"`` when playing is ignored.
    - ``play "-1"`` when paused resumes playback.
    - ``play "-1"`` when stopped with a current track starts playback at the
      current track.
    - ``play "-1"`` when stopped without a current track, e.g. after playlist
      replacement, starts playback at the first track.

    *BitMPC:*

    - issues ``play 6`` without quotes around the argument.
    """
    if songpos is None:
        context.core.playback.play().get()
        return

    if songpos == -1:
        _play_minus_one(context)
        return

    try:
        tl_track = context.core.tracklist.slice(songpos, songpos + 1).get()[0]
        context.core.playback.play(tlid=TracklistId(tl_track.tlid)).get()
    except IndexError as exc:
        raise exceptions.MpdArgError("Bad song index") from exc


def _play_minus_one(context: MpdContext) -> None:
    match context.core.playback.get_state().get():
        case PlaybackState.PLAYING:
            pass  # Nothing to do
        case PlaybackState.PAUSED:
            context.core.playback.resume().get()
        case PlaybackState.STOPPED:
            current_tlid = context.core.playback.get_current_tlid().get()
            if current_tlid is not None:
                context.core.playback.play(tlid=current_tlid).get()
                return

            tl_tracks = context.core.tracklist.slice(0, 1).get()
            if tl_tracks:
                context.core.playback.play(tlid=TracklistId(tl_tracks[0].tlid)).get()
                return

            # No current track, empty tracklist: nothing to do


@protocol.commands.add("playid", tlid=protocol.INT)
def playid(context: MpdContext, tlid: int) -> None:
    """
    *musicpd.org, playback section:*

        ``playid [SONGID]``

        Begins playing the playlist at song ``SONGID``.

    *Clarifications:*

    - ``playid "-1"`` when playing is ignored.
    - ``playid "-1"`` when paused resumes playback.
    - ``playid "-1"`` when stopped with a current track starts playback at the
      current track.
    - ``playid "-1"`` when stopped without a current track, e.g. after playlist
      replacement, starts playback at the first track.
    """
    if tlid == -1:
        _play_minus_one(context)
        return

    tl_tracks = context.core.tracklist.filter({"tlid": [tlid]}).get()
    if not tl_tracks:
        raise exceptions.MpdNoExistError("No such song")
    context.core.playback.play(tlid=TracklistId(tl_tracks[0].tlid)).get()


@protocol.commands.add("previous")
def previous(context: MpdContext) -> None:
    """
    *musicpd.org, playback section:*

        ``previous``

        Plays previous song in the playlist.

    *MPD's behaviour when affected by repeat/random/single/consume:*

        Given a playlist of three tracks numbered 1, 2, 3, and a currently
        playing track ``c``. ``previous_track`` is defined at the track
        that will be played upon ``previous`` calls.

        Tests performed on MPD 0.15.4-1ubuntu3.

        ======  ======  ======  =======  =====  =====  =====
                    Inputs                  previous_track
        -------------------------------  -------------------
        repeat  random  single  consume  c = 1  c = 2  c = 3
        ======  ======  ======  =======  =====  =====  =====
        T       T       T       T        Rand?  Rand?  Rand?
        T       T       T       .        3      1      2
        T       T       .       T        Rand?  Rand?  Rand?
        T       T       .       .        3      1      2
        T       .       T       T        3      1      2
        T       .       T       .        3      1      2
        T       .       .       T        3      1      2
        T       .       .       .        3      1      2
        .       T       T       T        c      c      c
        .       T       T       .        c      c      c
        .       T       .       T        c      c      c
        .       T       .       .        c      c      c
        .       .       T       T        1      1      2
        .       .       T       .        1      1      2
        .       .       .       T        1      1      2
        .       .       .       .        1      1      2
        ======  ======  ======  =======  =====  =====  =====

        - If :attr:`time_position` of the current track is 15s or more,
          ``previous`` should do a seek to time position 0.

    """
    context.core.playback.previous().get()


@protocol.commands.add("random", state=protocol.BOOL)
def random(context: MpdContext, state: bool) -> None:  # noqa: FBT001
    """
    *musicpd.org, playback section:*

        ``random {STATE}``

        Sets random state to ``STATE``, ``STATE`` should be 0 or 1.
    """
    context.core.tracklist.set_random(state)


@protocol.commands.add("repeat", state=protocol.BOOL)
def repeat(context: MpdContext, state: bool) -> None:  # noqa: FBT001
    """
    *musicpd.org, playback section:*

        ``repeat {STATE}``

        Sets repeat state to ``STATE``, ``STATE`` should be 0 or 1.
    """
    context.core.tracklist.set_repeat(state)


@protocol.commands.add("replay_gain_mode")
def replay_gain_mode(context: MpdContext, mode: str) -> Never:
    """
    *musicpd.org, playback section:*

        ``replay_gain_mode {MODE}``

        Sets the replay gain mode. One of ``off``, ``track``, ``album``.

        Changing the mode during playback may take several seconds, because
        the new settings does not affect the buffered data.

        This command triggers the options idle event.
    """
    raise exceptions.MpdNotImplementedError  # TODO


@protocol.commands.add("replay_gain_status")
def replay_gain_status(context: MpdContext) -> protocol.Result:
    """
    *musicpd.org, playback section:*

        ``replay_gain_status``

        Prints replay gain options. Currently, only the variable
        ``replay_gain_mode`` is returned.
    """
    return ("replay_gain_mode", "off")  # TODO


@protocol.commands.add("seek", songpos=protocol.UINT, seconds=protocol.UFLOAT)
def seek(context: MpdContext, songpos: int, seconds: float) -> None:
    """
    *musicpd.org, playback section:*

        ``seek {SONGPOS} {TIME}``

        Seeks to the position ``TIME`` (in seconds) of entry ``SONGPOS`` in
        the playlist.

    *Droid MPD:*

    - issues ``seek 1 120`` without quotes around the arguments.
    """
    tl_track = context.core.playback.get_current_tl_track().get()
    if context.core.tracklist.index(tl_track).get() != songpos:
        play(context, songpos=songpos)
    context.core.playback.seek(DurationMs(int(seconds * 1000))).get()


@protocol.commands.add("seekid", tlid=protocol.UINT, seconds=protocol.UFLOAT)
def seekid(context: MpdContext, tlid: int, seconds: float) -> None:
    """
    *musicpd.org, playback section:*

        ``seekid {SONGID} {TIME}``

        Seeks to the position ``TIME`` (in seconds) of song ``SONGID``.
    """
    tl_track = context.core.playback.get_current_tl_track().get()
    if not tl_track or tl_track.tlid != tlid:
        playid(context, tlid=tlid)
    context.core.playback.seek(DurationMs(int(seconds * 1000))).get()


@protocol.commands.add("seekcur")
def seekcur(context: MpdContext, time: str) -> None:
    """
    *musicpd.org, playback section:*

        ``seekcur {TIME}``

        Seeks to the position ``TIME`` within the current song. If prefixed by
        '+' or '-', then the time is relative to the current playing position.
    """
    if time.startswith(("+", "-")):
        position = context.core.playback.get_time_position().get()
        position = DurationMs(position + int(protocol.FLOAT(time) * 1000))
        context.core.playback.seek(position).get()
    else:
        position = DurationMs(int(protocol.UFLOAT(time) * 1000))
        context.core.playback.seek(position).get()


@protocol.commands.add("setvol", volume=protocol.INT)
def setvol(context: MpdContext, volume: int) -> None:
    """
    *musicpd.org, playback section:*

        ``setvol {VOL}``

        Sets volume to ``VOL``, the range of volume is 0-100.

    *Droid MPD:*

    - issues ``setvol 50`` without quotes around the argument.
    """
    # NOTE: we use INT as clients can pass in +N etc.
    value = Percentage(min(max(0, volume), 100))
    success = context.core.mixer.set_volume(value).get()
    if not success:
        raise exceptions.MpdSystemError("problems setting volume")


@protocol.commands.add("single", state=protocol.BOOL)
def single(context: MpdContext, state: bool) -> None:  # noqa: FBT001
    """
    *musicpd.org, playback section:*

        ``single {STATE}``

        Sets single state to ``STATE``, ``STATE`` should be 0 or 1. When
        single is activated, playback is stopped after current song, or
        song is repeated if the ``repeat`` mode is enabled.
    """
    context.core.tracklist.set_single(state)


@protocol.commands.add("stop")
def stop(context: MpdContext) -> None:
    """
    *musicpd.org, playback section:*

        ``stop``

        Stops playing.
    """
    context.core.playback.stop()


@protocol.commands.add("volume", change=protocol.INT)
def volume(context: MpdContext, change: int) -> None:
    """
    *musicpd.org, playback section:*

        ``volume {CHANGE}``

        Changes volume by amount ``CHANGE``.

        Note: ``volume`` is deprecated, use ``setvol`` instead.
    """
    min_volume_change = -100
    max_volume_change = 100
    min_volume = 0
    max_volume = 100

    if change < min_volume_change or change > max_volume_change:
        raise exceptions.MpdArgError("Invalid volume value")

    old_volume = context.core.mixer.get_volume().get()
    if old_volume is None:
        raise exceptions.MpdSystemError("problems setting volume")

    new_volume = Percentage(min(max(min_volume, old_volume + change), max_volume))
    success = context.core.mixer.set_volume(new_volume).get()
    if not success:
        raise exceptions.MpdSystemError("problems setting volume")
