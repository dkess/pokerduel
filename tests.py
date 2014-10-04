#!/usr/bin/env python2
# IRC Poker Duel - tests.py
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

import unittest

import poker

class TestHands(unittest.TestCase):
    #def setUp(self):
        #pass

    def test_headsUpAllIn(self):
        game = poker.TexasHoldemGame([6,34], 2, 5)

        # this hand will result in a tie; both players flop a pair of 9s.
        game.newHand(preset=([("9C","4H"),("9H","4S")],["9D","10S","2D","6S","AC"]))

        # make sure players put in blinds
        self.assertEqual(game.players[0].chips, 4)
        self.assertEqual(game.players[1].chips, 30)
        self.assertEqual(game.get_current_pot_total(), 6)

        # player 0 (short stack, small blind) calls
        game.poker_call()

        self.assertEqual(game.players[0].chips, 2)
        self.assertEqual(game.players[1].chips, 30)
        self.assertEqual(game.get_current_pot_total(), 8)

        # player 1 checks
        game.poker_check()

        self.assertEqual(game.players[0].chips, 2)
        self.assertEqual(game.players[1].chips, 30)
        self.assertEqual(game.get_current_pot_total(), 8)

        # we are now at the flop
        self.assertEqual(game.hand_stage, 1)

        # player 1 bets 4 chips, forcing player 0 all in
        game.poker_bet(4)

        self.assertEqual(game.players[0].chips, 2)
        self.assertEqual(game.players[1].chips, 26)
        self.assertEqual(game.get_current_pot_total(), 12)

        # player 0 calls all in
        game.poker_call()

        self.assertEqual(game.players[0].chips, 0)
        self.assertEqual(game.players[1].chips, 26)
        self.assertEqual(game.get_current_pot_total(), 14)

        self.assertTrue(game.all_show)

        # advance past the turn, then the river
        game.poker_advance()
        game.poker_advance()

        # game over-- since this was a tie, chips should start over
        self.assertEqual(game.players[0].chips, 6)
        self.assertEqual(game.players[1].chips, 34)
        self.assertEqual(game.get_current_pot_total(), 0)

        # advance to the next hand.  player 0 should win this time
        game.newHand(preset=([("8H","9D"),("AS","AH")],["JH","2D","7S","6C","10S"]))

        # make sure players put in blinds
        self.assertEqual(game.players[0].chips, 2)
        self.assertEqual(game.players[1].chips, 32)
        self.assertEqual(game.get_current_pot_total(), 6)

        # player 1 starts off raising immediately
        game.poker_raise_by(4)

        # player 0 calls
        game.poker_call()

        self.assertEqual(game.players[0].chips, 0)
        self.assertEqual(game.players[1].chips, 26)
        self.assertEqual(game.get_current_pot_total(), 14)

        self.assertTrue(game.all_show)

        # advance past the flop, turn, then river
        game.poker_advance()
        game.poker_advance()
        game.poker_advance()

        # game over, player 0 doubles up
        self.assertEqual(game.players[0].chips, 12)
        self.assertEqual(game.players[1].chips, 28)
        self.assertEqual(game.get_current_pot_total(), 0)

if __name__ == "__main__":
    unittest.main()
