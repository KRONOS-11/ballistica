"""Functionality related to scores and statistics."""

from __future__ import annotations

import random
import weakref
from typing import TYPE_CHECKING
from dataclasses import dataclass

import _ba

if TYPE_CHECKING:
    import ba
    from weakref import ReferenceType
    from typing import Any, Dict, Optional, Sequence, Union


@dataclass
class PlayerScoredMessage:
    # noinspection PyUnresolvedReferences
    """Informs something that a ba.Player scored.

    Category: Message Classes

    Attributes:

        score
            The score value.
    """
    score: int


class PlayerRecord:
    """Stats for an individual player in a ba.Stats object.

    Category: Gameplay Classes

    This does not necessarily correspond to a ba.Player that is
    still present (stats may be retained for players that leave
    mid-game)
    """
    character: str

    def __init__(self, name: str, name_full: str, player: ba.Player,
                 stats: ba.Stats):
        self.name = name
        self.name_full = name_full
        self.score = 0
        self.accumscore = 0
        self.kill_count = 0
        self.accum_kill_count = 0
        self.killed_count = 0
        self.accum_killed_count = 0
        self._multi_kill_timer: Optional[ba.Timer] = None
        self._multikillcount = 0
        self._stats = weakref.ref(stats)
        self._last_player: Optional[ba.Player] = None
        self._player: Optional[ba.Player] = None
        self.associate_with_player(player)
        self._spaz: Optional[ReferenceType[ba.Actor]] = None
        self._team: Optional[ReferenceType[ba.Team]] = None
        self.streak = 0

    @property
    def team(self) -> ba.Team:
        """The ba.Team the last associated player was last on.

        This can still return a valid result even if the player is gone.
        Raises a ba.TeamNotFoundError if the team no longer exists.
        """
        assert self._team is not None
        team = self._team()
        if team is None:
            from ba._error import TeamNotFoundError
            raise TeamNotFoundError()
        return team

    @property
    def player(self) -> ba.Player:
        """Return the instance's associated ba.Player.

        Raises a ba.PlayerNotFoundError if the player no longer exists."""
        if not self._player:
            from ba._error import PlayerNotFoundError
            raise PlayerNotFoundError()
        return self._player

    def get_name(self, full: bool = False) -> str:
        """Return the player entry's name."""
        return self.name_full if full else self.name

    def get_icon(self) -> Dict[str, Any]:
        """Get the icon for this instance's player."""
        player = self._last_player
        assert player is not None
        return player.get_icon()

    def get_spaz(self) -> Optional[ba.Actor]:
        """Return the player entry's spaz."""
        if self._spaz is None:
            return None
        return self._spaz()

    def set_spaz(self, spaz: Optional[ba.Actor]) -> None:
        """(internal)"""
        self._spaz = weakref.ref(spaz) if spaz is not None else None

    def cancel_multi_kill_timer(self) -> None:
        """Cancel any multi-kill timer for this player entry."""
        self._multi_kill_timer = None

    def getactivity(self) -> Optional[ba.Activity]:
        """Return the ba.Activity this instance is currently associated with.

        Returns None if the activity no longer exists."""
        stats = self._stats()
        if stats is not None:
            return stats.getactivity()
        return None

    def associate_with_player(self, player: ba.Player) -> None:
        """Associate this entry with a ba.Player."""
        self._team = weakref.ref(player.team)
        self.character = player.character
        self._last_player = player
        self._player = player
        self._spaz = None
        self.streak = 0

    def _end_multi_kill(self) -> None:
        self._multi_kill_timer = None
        self._multikillcount = 0

    def get_last_player(self) -> ba.Player:
        """Return the last ba.Player we were associated with."""
        assert self._last_player is not None
        return self._last_player

    def submit_kill(self, showpoints: bool = True) -> None:
        """Submit a kill for this player entry."""
        # FIXME Clean this up.
        # pylint: disable=too-many-statements
        from ba._lang import Lstr
        from ba._general import Call
        from ba._enums import TimeFormat
        self._multikillcount += 1
        stats = self._stats()
        assert stats
        if self._multikillcount == 1:
            score = 0
            name = None
            delay = 0
            color = (0.0, 0.0, 0.0, 1.0)
            scale = 1.0
            sound = None
        elif self._multikillcount == 2:
            score = 20
            name = Lstr(resource='twoKillText')
            color = (0.1, 1.0, 0.0, 1)
            scale = 1.0
            delay = 0
            sound = stats.orchestrahitsound1
        elif self._multikillcount == 3:
            score = 40
            name = Lstr(resource='threeKillText')
            color = (1.0, 0.7, 0.0, 1)
            scale = 1.1
            delay = 300
            sound = stats.orchestrahitsound2
        elif self._multikillcount == 4:
            score = 60
            name = Lstr(resource='fourKillText')
            color = (1.0, 1.0, 0.0, 1)
            scale = 1.2
            delay = 600
            sound = stats.orchestrahitsound3
        elif self._multikillcount == 5:
            score = 80
            name = Lstr(resource='fiveKillText')
            color = (1.0, 0.5, 0.0, 1)
            scale = 1.3
            delay = 900
            sound = stats.orchestrahitsound4
        else:
            score = 100
            name = Lstr(resource='multiKillText',
                        subs=[('${COUNT}', str(self._multikillcount))])
            color = (1.0, 0.5, 0.0, 1)
            scale = 1.3
            delay = 1000
            sound = stats.orchestrahitsound4

        def _apply(name2: str, score2: int, showpoints2: bool,
                   color2: Sequence[float], scale2: float,
                   sound2: ba.Sound) -> None:
            from bastd.actor.popuptext import PopupText

            # Only award this if they're still alive and we can get
            # their pos.
            try:
                actor = self.get_spaz()
                assert actor is not None
                assert actor.node
                our_pos = actor.node.position
            except Exception:
                return

            # Jitter position a bit since these often come in clusters.
            our_pos = (our_pos[0] + (random.random() - 0.5) * 2.0,
                       our_pos[1] + (random.random() - 0.5) * 2.0,
                       our_pos[2] + (random.random() - 0.5) * 2.0)
            activity = self.getactivity()
            if activity is not None:
                PopupText(Lstr(
                    value=(('+' + str(score2) + ' ') if showpoints2 else '') +
                    '${N}',
                    subs=[('${N}', name2)]),
                          color=color2,
                          scale=scale2,
                          position=our_pos).autoretain()
            _ba.playsound(sound2)

            self.score += score2
            self.accumscore += score2

            # Inform a running game of the score.
            if score2 != 0 and activity is not None:
                activity.handlemessage(PlayerScoredMessage(score=score2))

        if name is not None:
            _ba.timer(300 + delay,
                      Call(_apply, name, score, showpoints, color, scale,
                           sound),
                      timeformat=TimeFormat.MILLISECONDS)

        # Keep the tally rollin'...
        # set a timer for a bit in the future.
        self._multi_kill_timer = _ba.Timer(1.0, self._end_multi_kill)


class Stats:
    """Manages scores and statistics for a ba.Session.

    category: Gameplay Classes
    """

    def __init__(self) -> None:
        self._activity: Optional[ReferenceType[ba.Activity]] = None
        self._player_records: Dict[str, PlayerRecord] = {}
        self.orchestrahitsound1: Optional[ba.Sound] = None
        self.orchestrahitsound2: Optional[ba.Sound] = None
        self.orchestrahitsound3: Optional[ba.Sound] = None
        self.orchestrahitsound4: Optional[ba.Sound] = None

    def set_activity(self, activity: ba.Activity) -> None:
        """Set the current activity for this instance."""

        self._activity = None if activity is None else weakref.ref(activity)

        # Load our media into this activity's context.
        if activity is not None:
            if activity.is_expired():
                from ba import _error
                _error.print_error('unexpected finalized activity')
            else:
                with _ba.Context(activity):
                    self._load_activity_media()

    def getactivity(self) -> Optional[ba.Activity]:
        """Get the activity associated with this instance.

        May return None.
        """
        if self._activity is None:
            return None
        return self._activity()

    def _load_activity_media(self) -> None:
        self.orchestrahitsound1 = _ba.getsound('orchestraHit')
        self.orchestrahitsound2 = _ba.getsound('orchestraHit2')
        self.orchestrahitsound3 = _ba.getsound('orchestraHit3')
        self.orchestrahitsound4 = _ba.getsound('orchestraHit4')

    def reset(self) -> None:
        """Reset the stats instance completely."""
        # Just to be safe, lets make sure no multi-kill timers are gonna go off
        # for no-longer-on-the-list players.
        for p_entry in list(self._player_records.values()):
            p_entry.cancel_multi_kill_timer()
        self._player_records = {}

    def reset_accum(self) -> None:
        """Reset per-sound sub-scores."""
        for s_player in list(self._player_records.values()):
            s_player.cancel_multi_kill_timer()
            s_player.accumscore = 0
            s_player.accum_kill_count = 0
            s_player.accum_killed_count = 0
            s_player.streak = 0

    def register_player(self, player: ba.Player) -> None:
        """Register a player with this score-set."""
        name = player.get_name()
        name_full = player.get_name(full=True)
        try:
            # If the player already exists, update his character and such as
            # it may have changed.
            self._player_records[name].associate_with_player(player)
        except Exception:
            # FIXME: Shouldn't use top level Exception catch for logic.
            #  Should only have this as a fallback and always log it.
            self._player_records[name] = PlayerRecord(name, name_full, player,
                                                      self)

    def get_records(self) -> Dict[str, ba.PlayerRecord]:
        """Get PlayerRecord corresponding to still-existing players."""
        records = {}

        # Go through our player records and return ones whose player id still
        # corresponds to a player with that name.
        for record_id, record in self._player_records.items():
            lastplayer = record.get_last_player()
            if lastplayer and lastplayer.get_name() == record_id:
                records[record_id] = record
        return records

    def _get_spaz(self, player: ba.Player) -> Optional[ba.Actor]:
        return self._player_records[player.get_name()].get_spaz()

    def player_got_new_spaz(self, player: ba.Player, spaz: ba.Actor) -> None:
        """Call this when a player gets a new Spaz."""
        record = self._player_records[player.get_name()]
        if record.get_spaz() is not None:
            raise Exception("got 2 player_got_new_spaz() messages in a row"
                            " without a lost-spaz message")
        record.set_spaz(spaz)

    def player_got_hit(self, player: ba.Player) -> None:
        """Call this when a player got hit."""
        s_player = self._player_records[player.get_name()]
        s_player.streak = 0

    def player_scored(self,
                      player: ba.Player,
                      base_points: int = 1,
                      target: Sequence[float] = None,
                      kill: bool = False,
                      victim_player: ba.Player = None,
                      scale: float = 1.0,
                      color: Sequence[float] = None,
                      title: Union[str, ba.Lstr] = None,
                      screenmessage: bool = True,
                      display: bool = True,
                      importance: int = 1,
                      showpoints: bool = True,
                      big_message: bool = False) -> int:
        """Register a score for the player.

        Return value is actual score with multipliers and such factored in.
        """
        # FIXME: Tidy this up.
        # pylint: disable=cyclic-import
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-locals
        # pylint: disable=too-many-statements
        from bastd.actor.popuptext import PopupText
        from ba import _math
        from ba._gameactivity import GameActivity
        from ba._lang import Lstr
        del victim_player  # currently unused
        name = player.get_name()
        s_player = self._player_records[name]

        if kill:
            s_player.submit_kill(showpoints=showpoints)

        display_color: Sequence[float] = (1.0, 1.0, 1.0, 1.0)

        if color is not None:
            display_color = color
        elif importance != 1:
            display_color = (1.0, 1.0, 0.4, 1.0)
        points = base_points

        # If they want a big announcement, throw a zoom-text up there.
        if display and big_message:
            try:
                assert self._activity is not None
                activity = self._activity()
                if isinstance(activity, GameActivity):
                    name_full = player.get_name(full=True, icon=False)
                    activity.show_zoom_message(
                        Lstr(resource='nameScoresText',
                             subs=[('${NAME}', name_full)]),
                        color=_math.normalized_color(player.team.color))
            except Exception:
                from ba import _error
                _error.print_exception('error showing big_message')

        # If we currently have a spaz, pop up a score over it.
        if display and showpoints:
            our_pos: Optional[Sequence[float]]
            try:
                spaz = s_player.get_spaz()
                assert spaz is not None
                assert spaz.node
                our_pos = spaz.node.position
            except Exception:
                our_pos = None
            if our_pos is not None:
                if target is None:
                    target = our_pos

                # If display-pos is *way* lower than us, raise it up
                # (so we can still see scores from dudes that fell off cliffs).
                display_pos = (target[0], max(target[1], our_pos[1] - 2.0),
                               min(target[2], our_pos[2] + 2.0))
                activity = self.getactivity()
                if activity is not None:
                    if title is not None:
                        sval = Lstr(value='+${A} ${B}',
                                    subs=[('${A}', str(points)),
                                          ('${B}', title)])
                    else:
                        sval = Lstr(value='+${A}',
                                    subs=[('${A}', str(points))])
                    PopupText(sval,
                              color=display_color,
                              scale=1.2 * scale,
                              position=display_pos).autoretain()

        # Tally kills.
        if kill:
            s_player.accum_kill_count += 1
            s_player.kill_count += 1

        # Report non-kill scorings.
        try:
            if screenmessage and not kill:
                _ba.screenmessage(Lstr(resource='nameScoresText',
                                       subs=[('${NAME}', name)]),
                                  top=True,
                                  color=player.color,
                                  image=player.get_icon())
        except Exception:
            from ba import _error
            _error.print_exception('error announcing score')

        s_player.score += points
        s_player.accumscore += points

        # Inform a running game of the score.
        if points != 0:
            activity = self._activity() if self._activity is not None else None
            if activity is not None:
                activity.handlemessage(PlayerScoredMessage(score=points))

        return points

    def player_lost_spaz(self,
                         player: ba.Player,
                         killed: bool = False,
                         killer: ba.Player = None) -> None:
        """Should be called when a player loses a spaz."""
        from ba._lang import Lstr
        name = player.get_name()
        prec = self._player_records[name]
        prec.set_spaz(None)
        prec.streak = 0
        if killed:
            prec.accum_killed_count += 1
            prec.killed_count += 1
        try:
            if killed and _ba.getactivity().announce_player_deaths:
                if killer == player:
                    _ba.screenmessage(Lstr(resource='nameSuicideText',
                                           subs=[('${NAME}', name)]),
                                      top=True,
                                      color=player.color,
                                      image=player.get_icon())
                elif killer is not None:
                    if killer.team == player.team:
                        _ba.screenmessage(Lstr(resource='nameBetrayedText',
                                               subs=[('${NAME}',
                                                      killer.get_name()),
                                                     ('${VICTIM}', name)]),
                                          top=True,
                                          color=killer.color,
                                          image=killer.get_icon())
                    else:
                        _ba.screenmessage(Lstr(resource='nameKilledText',
                                               subs=[('${NAME}',
                                                      killer.get_name()),
                                                     ('${VICTIM}', name)]),
                                          top=True,
                                          color=killer.color,
                                          image=killer.get_icon())
                else:
                    _ba.screenmessage(Lstr(resource='nameDiedText',
                                           subs=[('${NAME}', name)]),
                                      top=True,
                                      color=player.color,
                                      image=player.get_icon())
        except Exception:
            from ba import _error
            _error.print_exception('error announcing kill')