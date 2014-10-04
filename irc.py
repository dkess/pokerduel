#!/usr/bin/env python2
# IRC Poker Duel - irc.py
# Copyright (C) 2014  Daniel Kessler
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict
from random import shuffle
import socket

import poker

def stripirchost(user):
    return user.split("!",1)[0]

config = {'init':[]}
with open("config") as configfile:
    for l in configfile.readlines():
        split = l[:-1].split("=",1)
        if split[0] == 'init':
            config['init'].append(split[1])
        else:
            config[split[0]] = split[1]

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((config["server"],int(config["port"])))
except (socket.error, socket.herror, socket.gaierror):
    print("Socket error")
except KeyError:
    print("You must specify a server and port in the config file!")

def ircsend(msg):
    global sock
    sock.send(msg + "\r\n")
    print("<- "+msg)

def chanmsg(msg):
    ircsend("PRIVMSG {} :{}".format(config["channel"], msg))

def notice_user(nick, msg):
    ircsend("NOTICE {} :{}".format(nick, msg))

def chantopic(topic):
    ircsend("TOPIC {} :{}".format(config["channel"], topic))

ircsend("USER %s 0 * :%s\r\nNICK %s\r\n" %
        (config["nick"],config["user"],config["nick"]))

# players is a mapping between player id and nick
players = []

# case insensitive function for getting player id
def idForPlayer(s):
    global players
    for i,p in enumerate(players):
        if p.lower() == s.lower():
            return i
    raise ValueError()

# The PokerGame, if it is in progress
pokergame=None
current_stage = -1
last_all_show = False

default_topic = "Welcome! To challenge someone, type !challenge playernick"

# listing of open challenges. the key is challengers and the value is opponents
# everything in this dict should be lowercase
challenges = defaultdict(lambda: None)

def begin_duel(p1, p2):
    global pokergame
    global players
    pokergame = poker.TexasHoldemGame([35,35], 2)
    players = [p1, p2]

    pokergame.newHand()

    update_poker()

def update_poker():
    global current_stage
    global pokergame
    global players
    global last_all_show

    pnum, committed, currentbet, pstage, all_show = pokergame.getCurrentTurn()

    if current_stage != pstage:
        current_stage = pstage

        if current_stage == 0:
            # show the players their cards
            for i, p in enumerate(players):
                hand = pokergame.players[i].hand
                notice_user(p, "Your hand is {} {}.".format(hand[0], hand[1]))
        elif current_stage == 1:
            # show the flop
            chanmsg("Community cards: {}".format(
                    " ".join(pokergame.community[:3])))
        elif current_stage == 2:
            chanmsg("Community cards: {}".format(
                    " ".join(pokergame.community[:4])))
        elif current_stage == 3:
            chanmsg("Community cards: {}".format(
                    " ".join(pokergame.community)))
        elif current_stage == 4:
            # reveal cards
            chanmsg(", ".join(["{}'s hand: {}".format(
                    players[p], " ".join(pokergame.players[p].hand))
                for p in pokergame.players_to_reveal]))
            # reveal winnings
            chanmsg(", ".join(["{} wins {} chips".format(players[p], c)
                               for p, c in pokergame.winnings.iteritems()]))
            chanmsg("If your hand was not shown, you may !reveal your cards. "
                    "Otherwise, advance to the next hand with !advance.")

            last_all_show = False


    if all_show and current_stage != 4:
        if not last_all_show:
            chanmsg(", ".join(["{}'s hand: {}".format(
                    players[p], " ".join(pokergame.players[p].hand))
                for p in pokergame.playersInHand]))
            last_all_show = True
        chanmsg("Anyone in this hand may type !advance to continue")
    elif currentbet == 0:
        message = "You may !check, !bet ##, or !fold."
    elif currentbet == committed:
        message = ("You have already placed {} big blind chips. "
                   "You may !check or !raiseto ##.".format(committed))
    else:
        message = ("The bet is {} and you have committed {} chips. "
                   "You may !call, !raiseto ##, or !fold.".format(currentbet,committed))

    if not all_show and current_stage != 4:
        chanmsg("{}: It is your turn. {}".format(players[pnum], message))

    # channel topic (complete game status)
    player_chips = ", ".join(["{}{}{}{} ({})".format("*" if p == pnum else "",
                                                     "+" if p in pokergame.playersInHand else "",
                                                     "@" if p == pokergame.buttonLocation else "",
                                                     players[p],
                                                     pokergame.players[p].chips)
                              for p in pokergame.alivePlayers])

    if len(pokergame.alivePlayers) == 1:
        chanmsg(players[pokergame.alivePlayers[0]] + " wins!")
        chantopic(default_topic)
        pokergame = None
        challenges = {}
    else:
        potinfo = "Pot: {} chips".format(pokergame.get_current_pot_total())
        community = "Community cards: " + " ".join(filter(lambda x: x, pokergame.community))
        chantopic(" | ".join([player_chips,potinfo, community]))


while (1):
    for ircline in [l.rstrip("\r") for l in sock.recv(512).split("\n")][:-1]:
        print("-> "+ircline)
        if ircline.startswith("PING :"):
            ircsend("PONG :"+ircline[6:])
        sirc = ircline[1:].split(" ")
        if len(sirc) > 3:
            # welcome message
            if sirc[1] == "001":
                ircsend("JOIN "+config["channel"])
                chantopic(default_topic)
                for cmd in config["init"]:
                    ircsend(cmd)
            if pokergame == None:
                if sirc[1] == "PRIVMSG":
                    nick = stripirchost(sirc[0])
                    if sirc[2] == config["channel"] and len(sirc) >= 5:
                        # commands that must be entered in the public channel
                        if sirc[3] == ":!challenge":
                            if challenges[sirc[4].lower()] == nick.lower():
                                chanmsg("That player has already challenged you!"
                                            " Starting the duel now...")
                                begin_duel(sirc[4].lower(), nick.lower())
                            else:
                                challenges[nick.lower()] = sirc[4].lower()
                                chanmsg("Your oppoenent should type \"!accept {}"
                                            "\" to start the duel.".format(nick))
                        elif sirc[3] == ":!accept":
                            if challenges[sirc[4].lower()] == nick.lower():
                                chanmsg("Let the games begin! May the best win.")
                                begin_duel(sirc[4].lower(), nick.lower())
            else:
                if sirc[1] == "PRIVMSG":
                    nick = stripirchost(sirc[0])
                    turn_nick = players[pokergame.playerTurn]
                    if nick.lower() == turn_nick:
                        try:
                            action_taken = True
                            print pokergame.hand_stage
                            if sirc[3] == ":!check":
                                pokergame.poker_check()
                            elif sirc[3] == ":!fold":
                                pokergame.poker_fold()
                            elif sirc[3] == ":!bet" and len(sirc) >= 5:
                                pokergame.poker_bet(int(sirc[4]))
                            elif sirc[3] == ":!call":
                                pokergame.poker_call()
                            elif sirc[3] == ":!raiseby" and len(sirc) >= 5:
                                pokergame.poker_raise_by(int(sirc[4]))
                            elif sirc[3] == ":!raiseto" and len(sirc) >= 5:
                                pokergame.poker_raise_to(int(sirc[4]))
                            elif sirc[3] == ":!allin":
                                pokergame.poker_allin()
                            else:
                                action_taken = False

                            if action_taken:
                                update_poker()
                                print pokergame.hand_stage

                        except poker.PokerException as e:
                            chanmsg("{}: {}".format(nick, e.msg))
                    try:
                        if idForPlayer(nick) in pokergame.playersInHand:
                            if sirc[3] == ":!advance":
                                print pokergame.hand_stage
                                pokergame.poker_advance()
                                print pokergame.hand_stage
                                update_poker()
                        elif idForPlayer(nick) in pokergame.alivePlayers:
                            if sirc[3] == ":!hand":
                                hand = pokergame.players[idForPlayer(nick)].hand
                                notice_user(nick, "Your hand is {} {}.".format(hand[0], hand[1]))
                    except ValueError:
                        pass

            if sirc[1] == "NICK":
                if stripirchost(sirc[0]) == config["nick"]:
                    config["nick"] = sirc[2][1:]
                try:
                    players[idForPlayer] = sirc[2][1:]
                except ValueError:
                    pass
