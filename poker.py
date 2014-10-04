# IRC Poker Duel - poker.py
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
from itertools import chain, groupby
from random import choice, shuffle

from specialk.SevenEval import SevenEval

def shuffledDeck(randomgen=None):
    deck = [face+suit
            for face in (map(str,range(2,11)) + ["J","Q","K","A"])
            for suit in ["H","D","S","C"]]
    if randomgen == None:
        shuffle(deck)
    else:
        randomgen.shuffle(deck)
    return deck

def cardToInt(cardString):
    facestr = cardString[:-1]
    suitstr = cardString[-1]

    try:
        if 2 <= int(facestr) <= 10:
            face = 14 - int(facestr)
        else:
            return -1
    except ValueError:
        if facestr == "J":
            face = 3
        elif facestr == "Q":
            face = 2
        elif facestr == "K":
            face = 1
        elif facestr == "A":
            face = 0
        else:
            return -1

    if suitstr == "S":
        suit = 0
    elif suitstr == "H":
        suit = 1
    elif suitstr == "D":
        suit = 2
    elif suitstr == "C":
        suit = 3
    else:
        return -1

    return face * 4 + suit

def nextInList(l, current, amount=1):
    listLength = len(l)
    if amount < 0 or amount >= listLength:
        amount = amount % listLength

    i = iter(l)
    while amount > 0:
        try:
            candidate = i.next()
            if candidate > current:
                current = candidate
                amount -= 1
        except StopIteration:
            i = iter(l)
            current = i.next()
            amount -= 1

    return current

class PokerException(Exception):
    pass

class MustRespondBet(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "You must call, raise, or fold."

class NoBet(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "There must be an active bet for you to do that."

class NotEnoughChips(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "You do not have enough chips to do that."

class InvalidAmount(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "That is an invalid amount of chips."

class BetTooSmall(PokerException):
    def __init__(self, player, minimum):
        self.player = player
        self.msg = "The minimum bet is {}.".format(minimum)

class RaiseTooSmall(PokerException):
    def __init__(self, player, minimum):
        self.player = player
        self.msg = ("You must raise by at least double "
                    "the last pot increse ({}), or go all-in.".format(minimum))

class NoActionAllowed(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "No action is allowed. You must advance the game."

class MustBetOrCheck(PokerException):
    def __init__(self, player):
        self.player = player
        self.msg = "You must bet or check."

class Player:
    def __init__(self, startingChips):
        self.chips = startingChips
        self.past_bets = 0
        self.current_bet = 0
        self.hand = None

    def next_stage(self):
        """Moves chips from current_bet to past_bets"""
        self.past_bets += self.current_bet
        self.current_bet = 0

class TexasHoldemGame:
    def __init__(self, chipdist, smallblind, randomgen=None):
        self.buttonLocation = -1
        self.totalPlayers = len(chipdist)
        self.playerTurn = -1
        self.smallblind = smallblind
        self.handsPlayed = 0
        self.winnings = {}
        self.randomgen = randomgen

        self.players = []
        for c in chipdist:
            self.players.append(Player(c))

        # 0 - pre-flop
        # 1 - flop
        # 2 - turn
        # 3 - river
        # 4 - end of hand
        self.hand_stage = -1

    def newHand(self, preset=None):
        """Start a new hand. preset is a tuple of (cards_dealt,community cards).
        Example: preset=([("JH","JC"), ("AS","AC")], ["10D","9C","7H","QD","8D"])
        The cards dealt are assigned to players starting with whoever is to the
        left of the button, moving counter clockwise.  In a heads up scenario,
        the first hand is dealt to the big bilnd, and the second is dealt to
        the small blind.

        If preset is not specified, a randomly shuffled deck is used."""

        # if everyone (or all but one) is all-in, everyone shows their cards,
        # and this variable is turned on
        self.all_show = False

        self.players_to_reveal = []

        # reset the list of alive players
        self.alivePlayers = filter(lambda x: self.players[x].chips != 0,
                                   range(self.totalPlayers))
        self.playersInHand = self.alivePlayers[:]

        # reset community cards
        self.community = [None] * 5

        # update the blinds
        self.handsPlayed += 1

        if preset == None:
            # shuffle the deck
            self.deck = shuffledDeck(randomgen=self.randomgen)
        else:
            self.deck = list(chain(chain.from_iterable(preset[0]), preset[1]))

        # move the button to the next alive player
        self.buttonLocation = nextInList(self.alivePlayers, self.buttonLocation)

        current_deal = self.buttonLocation
        while(1):
            current_deal = nextInList(self.alivePlayers, current_deal)
            self.players[current_deal].hand = (self.deck.pop(0), self.deck.pop(0))
            if current_deal == self.buttonLocation:
                break

        if len(self.alivePlayers) > 2:
            self.playerTurn = (
                    nextInList(self.alivePlayers, self.buttonLocation, 3))
            sb = 1
        else:
            # special heads up rules
            self.playerTurn = self.buttonLocation
            sb = 0

        self.transfer_to_pot(
                nextInList(self.alivePlayers, self.buttonLocation, sb),
                self.smallblind)

        self.transfer_to_pot(
                nextInList(self.alivePlayers, self.buttonLocation, sb+1),
                self.smallblind * 2)

        # last_raise_player is the player id of the last person to raise/bet
        # playerTurn rotates around alivePlayers until it gets to this
        # In the pre-flop stage, this is the player after the big blind (three
        # to the left of the button)
        self.last_raise_player = nextInList(
                self.alivePlayers, self.buttonLocation, 2+sb)

        # set the stage to 0 (pre-flop)
        self.hand_stage = 0
        self.current_bet = self.smallblind * 2

        self.minimum_raise = self.smallblind * 2

    def getCurrentTurn(self):
        """Return who's turn it is, how many chips they have committed in this
        round, what the bet currently is, the hand's stage, and all_show status.

        Returns a tuple (playernun, commited, currentbet, stage)"""
        return (self.playerTurn, self.players[self.playerTurn].current_bet,
               self.current_bet, self.hand_stage, self.all_show)

    def get_current_pot_total(self):
        return sum([self.players[p].current_bet + self.players[p].past_bets
                    for p in self.alivePlayers])

    def transfer_to_pot(self, playernum, amount):
        """Subtracts amount from a player's chip count, and places it into
        their current_bet. If the amount exceeds their chip total, only the
        amount that they can afford will be transferred."""
        amount = min(amount, self.players[playernum].chips)
        self.players[playernum].chips -= amount
        self.players[playernum].current_bet += amount

    def rotate_player(self):
        self.playerTurn = nextInList(self.playersInHand, self.playerTurn)
        no_contest = len(self.playersInHand) < 2
        if (self.playerTurn == self.last_raise_player or
            no_contest or self.all_show):
            # go to the next stage
            for p in self.players:
                p.next_stage()

            self.hand_stage += 1

            self.playerTurn = nextInList(
                    self.playersInHand, self.buttonLocation)

            self.current_bet = 0
            self.minimum_raise = self.smallblind * 2

            # if there is only one player left, skip to the end
            if no_contest:
                self.hand_stage = 4
            elif not self.all_show and self.hand_stage != 4:
                # if there are two or more players with chips, do not go into
                # all_show mode
                players_with_chips = 0
                for p in self.players:
                    if p.chips > 0:
                        players_with_chips += 1
                if players_with_chips < 2:
                    self.all_show = True
                else:
                    # last_raise_player should be the player to the left of the
                    # dealther, however if that player has no chips, we keep
                    # moving to the left until we find someone with chips.
                    # This process should only be done if we are not in all_show
                    # mode, otherwise it doesn't matter where last_raise_player
                    # is.
                    while True:
                        self.last_raise_player = nextInList(
                                self.playersInHand, self.buttonLocation)
                        if self.players[self.last_raise_player].chips > 0:
                            break

            if self.hand_stage == 1:
                # deal the flop
                for i in range(3):
                    self.community[i] = self.deck.pop(0)
            elif self.hand_stage == 2:
                # deal the turn
                self.community[3] = self.deck.pop(0)
            elif self.hand_stage == 3:
                # deal the river
                self.community[4] = self.deck.pop(0)
            elif self.hand_stage == 4:
                if not no_contest:
                    # determine the winner
                    handRanksDict = defaultdict(list)
                    sevenEval = SevenEval()
                    for p in self.playersInHand:
                        intHand = map(cardToInt,
                                    list(self.players[p].hand) + self.community)
                        handRank = sevenEval.getRankOfSeven(*intHand)
                        handRanksDict[handRank].append(p)
                    hand_ranks = sorted(handRanksDict.iteritems(),
                                        key=lambda x:x[0], reverse=True)
                else:
                    hand_ranks = [(1, self.playersInHand)]

                # rankings is a list of sets.  rankings[0] is the set of players
                # tied for first place, and so on.
                rankings = [set(a[1]) for a in hand_ranks]

                # resolve side pots
                # each entry of sidepots is a (a,b) tuple. a is the set of
                # players contesting this side pot.  b is the total amount of
                # chips in that side pot.
                sidepots = []
                last_sidepot = 0
                last_chipcount = 0

                player_bets = sorted([(p, self.players[p].past_bets)
                                      for p in self.alivePlayers],
                                     key=lambda x: x[1])
                # sorted_players is the same as self.alivePlayers, but sorted by
                # whoever placed more chips in the pot.
                sorted_players = map(lambda x: x[0], player_bets)
                players_left = len(self.alivePlayers)
                for p, c in player_bets:
                    if c > last_chipcount:
                        sidepots.append((set(sorted_players[-players_left:]),
                                         (c - last_chipcount) * players_left))
                        last_chipcount = c

                    players_left -= 1

                # winnings is a mapping between players and how much they won
                self.winnings = defaultdict(int)

                for contenders, prize in sidepots:
                    for wins in rankings:
                        pot_winners = contenders.intersection(wins)
                        if pot_winners:
                            split, rem = divmod(prize, len(pot_winners))
                            for p in pot_winners:
                                self.winnings[p] += split
                            if rem != 0:
                                # the odd chip is given to a random player
                                self.winnings[choice(tuple(pot_winners))] += 1
                            break
                # actually award the chips
                for p, c in self.winnings.iteritems():
                    self.players[p].chips += c

                for p in self.players:
                    p.past_bets = 0
                    p.current_bet = 0

                # To decide whose hand to reveal: travel clockwise around the
                # table, starting with last_raise_player.  Every player we pass
                # must reveal their cards; if this player is a winner then we
                # remove them from winning_players.  When winning_players is
                # empty, we stop rotating, and anyone who we didn't pass is not
                # compelled to show their cards.
                # If there is only one player left, that player does not have to
                # reveal their cards.
                if not no_contest or not self.all_show:
                    winning_players = self.winnings.keys()
                    current_player = self.last_raise_player
                    while winning_players:
                        self.players_to_reveal.append(current_player)
                        if current_player in winning_players:
                            winning_players.remove(current_player)
                        current_player = nextInList(self.playersInHand,
                                                    current_player)
                return

        # we skip a player if they are out of chips
        if self.players[self.playerTurn].chips == 0 and not self.all_show:
            self.rotate_player()

    def poker_check(self):
        if self.all_show:
            raise NoActionAllowed(self.playerTurn)
        if self.current_bet > self.players[self.playerTurn].current_bet:
            raise MustRespondBet(self.playerTurn)
        else:
            self.rotate_player()

    def poker_fold(self):
        if self.all_show:
            raise NoActionAllowed(self.playerTurn)
        self.playersInHand.remove(self.playerTurn)
        self.rotate_player()

    def poker_bet(self, amount):
        if self.all_show:
            raise NoActionAllowed(self.playerTurn)
        if self.current_bet != 0:
            raise MustRespondBet(self.playerTurn)
        elif amount > self.players[self.playerTurn].chips:
            raise NotEnoughChips(self.playerTurn)
        elif (amount < self.smallblind * 2 and
              amount != self.players[self.playerTurn].chips):
            raise BetTooSmall(self.playerTurn, self.smallblind * 2)
        else:
            self.minimum_raise = amount
            self.transfer_to_pot(self.playerTurn, amount)
            self.current_bet = amount
            self.last_raise_player = self.playerTurn
            self.rotate_player()

    def poker_call(self):
        if self.all_show:
            raise NoActionAllowed(self.playerTurn)
        player_bet = self.players[self.playerTurn].current_bet
        if self.current_bet == player_bet:
            raise NoBet(self.playerTurn)
        else:
            self.transfer_to_pot(self.playerTurn, self.current_bet - player_bet)
            self.rotate_player()

    def poker_raise_by(self, amount):
        """Adds an amount to the current bet."""
        if self.all_show:
            raise NoActionAllowed(self.playerTurn)
        player_chips = self.players[self.playerTurn].chips
        player_cbet = self.players[self.playerTurn].current_bet
        chip_outflux = self.current_bet + amount - player_cbet
        if chip_outflux > player_chips:
            raise NotEnoughChips(self.playerTurn)
        elif amount < self.minimum_raise and chip_outflux != player_chips:
            raise RaiseTooSmall(self.playerTurn, self.minimum_raise)
        elif amount <= 0:
            raise InvalidAmount(self.playerTurn)
        else:
            self.transfer_to_pot(self.playerTurn, chip_outflux)
            self.minimum_raise = amount
            self.current_bet += amount
            self.last_raise_player = self.playerTurn
            self.rotate_player()

    def poker_raise_to(self, amount):
        self.poker_raise_by(amount - self.current_bet)

    def poker_allin(self):
        if self.current_bet == 0:
            self.poker_bet(self.players[self.playerTurn].chips)
        else:
            self.poker_raise_to(self.players[self.playerTurn].chips +
                                    self.players[self.playerTurn].current_bet)

    def poker_advance(self):
        if self.hand_stage == 4:
            self.newHand()
        elif self.all_show:
            self.rotate_player()
        elif self.current_bet == 0:
            raise MustBetOrCheck(self.playerTurn)
        else:
            raise MustRespondBet(self.playerTurn)
