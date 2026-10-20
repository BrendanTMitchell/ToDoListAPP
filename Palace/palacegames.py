"""Basic Palace card-game setup and turn rules."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import random
try:
	import tkinter as tk
	from tkinter import messagebox, simpledialog, ttk
except ImportError:  # the browser build (Pyodide) only needs the game engine
	tk = messagebox = simpledialog = ttk = None

SUITS = ("Clubs", "Diamonds", "Hearts", "Spades")
RANKS = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace")
VALUES = {rank: value for value, rank in enumerate(RANKS, 2)}
ADMIN_PASSWORD = "ZaydIsABum"
MULTI_USE_RULES = {
	"Top card discard": "On your turn, remove the top card from one chosen discard pile and move it to the destroyed pile. This rule can be used once per round.",
	"Stack destroy": "When you play a card with the same value as the top card you played on that pile, destroy the entire pile, including both cards. This rule can trigger multiple times in a round.",
	"I-T": "This player is immune to all effects from other players.",
	"Quick Grab": "When another player plays a specific card value, this player can add that card and add it to their own hand.",
	"Soul Swap": "Two players swap all their cards, including face-up and face-down cards.",
	"Card Swapping": "This player can swap a specific card for another as long as they can see the card.",
	"Reveal": "Every player this is applied to has to reveal one card of their choice that is hidden from other players. This lasts until the card is played.",
	"Rescue Draw": "Once every 2 rounds you can choose to draw 2 cards from the draw pile or if the draw pile is gone you can take 1 card of your choice from the destroyed pile.",
	"Full Hand": "This player picks up all of their face-up and face-down cards and adds them to their hand.",
}
DOMAIN_TAG = "(Domain)"
DEFAULT_DOMAIN_REFINEMENT = 5
SIMPLE_DOMAIN_REFINEMENT = 3
DEFAULT_DOMAIN_DURATION = 3  # rounds a domain stays open; a domain may set "duration" (None = no limit) and "refinement"
DOMAIN_CLASHING_RULE = (
	"Domain Clashing: Any ability with (Domain) in its name is a domain. If anyone opens a domain, anyone with a domain, "
	"even an upgraded one they haven't unlocked, can instantly open theirs to clash. Without the domain unlocked, you can "
	"decrease its refinement by 1, expend a Joker from your hand, or exchange one of your upgraded abilities.\n"
	"- Every round that passes while clashing, the refinement of all clashing domains decreases by 1; at 0 the domain breaks.\n"
	"- A player who has their turn canceled or picks up the piles has their domain shatter instantly.\n"
	"- A domain with greater refinement than an opponent's shatters that opponent's domain at the end of the round.\n"
	"- Each turn while clashing you may draw a card: royal (Jack, Queen, King) blocks the next refinement decrease, "
	"a Joker adds 1 refinement, and a 2-5 removes 1 refinement.\n"
	"- Domain effects are disabled while domains are clashing.\n"
	"- With 3 or more domains open, a player who isn't clashing can expend a Joker to decrease one domain's refinement by 1.\n"
	"- A domain stays open until it breaks, shatters, a player picks up the piles or has a turn canceled, or its time limit runs out (usually 3 rounds, set per domain).\n"
	"- An \"open\" domain can't break during a clash, but if an opponent's refinement is higher, their domain's effect still lands."
)
GOD_RULES = ("Top card discard", "Soul Swap", "Stack destroy", "I-T", "Quick Grab", "Card Swapping", "Reveal", "Rescue Draw", "Full Hand")
CHARACTERS = {
	"Sukuna": {
		"ability": "Cleave",
		"description": "This player can use top card discard once per round.",
		"rules": ("Top card discard",),
		"evolution": {
			"ability": "Spider Net Cleave",
			"description": "Your top card discard from Cleave gains 5 uses per round and now whenever it causes a pile to lose all of its card the other pile will be destroy for free and you can replace both piles for free forcing them to place 1 card from their hand in each pile.",
		},
	},
	"Gojo": {
		"ability": "Hollow Purple",
		"description": "This player gains the ability to stack destroy",
		"rules": ("Stack destroy",),
		"evolution": {
			"ability": "Max Purple",
			"description": "When this player plays 3 cards in a row it will activate stack destroy as if they stacked 2 cards in a row.",
		},
	},
}
CHARACTERS["Sukuna"]["additional_abilities"] = (
	{
		"ability": "World Cutting Slash",
		"description": "Whenever this player plays a King, they can choose a card to delete from the game, then choose another player and increase their Cut Meter by 1. At 9, that player is eliminated and gets last place.",
		"evolution": {
			"ability": "Waffle Cutting Slash",
			"description": "Whenever this player uses World Cutting Slash, it counts as using it 3 times. This player's Kings can be played on top of any card regardless of when in the turn it is.",
		},
	},
	{
		"ability": "Enchain",
		"description": "This player can once per game, click this ability to force themselves into soul swapping with another player of this players choice. Then, this player will be forced to play 2 cards in a row, while playing those 2 cards this player will be immune to all other players' effects.",
		"rules": ("Soul Swap",),
		"evolution": {
			"ability": "Rule Workaround",
			"description": "Allows the player to soul swap with other players with no restrictions besides those immune to soul swap. During your 2 cards played from soul swapping you can completely ignore card values.",
			"rules": ("Soul Swap",),
		},
	},
	{
		"ability": "Binding Vow",
		"description": "In exchange for passing up a turn, any of your cards can be played as a king.",
		"evolution": {
			"ability": "Binding Vow Merchant",
			"description": "Any of this player's cards can be stacked on top of a king.",
		},
	},
	{
		"ability": "God of Jujutsu",
		"description": "This player can once per round use 1 multi use rule of their choice. This player is also completley immune to having other players swap card with them or use soul swap on them.",
	},
)
CHARACTERS["Gojo"]["additional_abilities"] = (
	{
		"ability": "Limitless Barrier",
		"description": "Whenever this player plays an Ace, they will gain a passive for however many they stacked. For 1 Ace, the player will gain I-T for 2 rounds. For 2 Aces, they will gain all of the previously listed abilities along with being able to pick up one of their face-down cards. For 3 Aces, the player will be able to pick up all of their face-down cards, along with I-T being applied for 3 rounds. Should 4 Aces be played, this player will be able to replace their hand with cards from the deleted pile along with this ability instantly being upgraded.",
		"rules": ("I-T",),
		"evolution": {
			"ability": "Perfected Limitless",
			"description": "When this ability is evolved this player will gain I-T for the rest of the game along with gaining the Quick Grab ability for Aces.",
			"rules": ("I-T", "Quick Grab"),
		},
	},
	{
		"ability": "Lapse Blue",
		"description": "Card Swapping with 5's and apply reveal on every other player when swapping cards.",
		"rules": ("Card Swapping", "Reveal"),
		"evolution": {
			"ability": "Reversal Red",
			"description": "The user can use card swapping with the card values of 6 and 9 now along with gaining rescue draw.",
			"rules": ("Card Swapping", "Rescue Draw"),
		},
	},
	{
		"ability": "Six Eyes",
		"description": "Once per turn, this player can choose to either view one of their face-down cards or see someone else's hand.",
		"evolution": {
			"ability": "Mastered Six Eyes",
			"description": "This player gains full hand along with being able to check any other player's cards at the start of their turn. Before drawing they are allowed to view the top 3 cards in both draw piles and choose 1 of them to draw.",
			"rules": ("Full Hand",),
		},
	},
	{
		"ability": "Simple Domain",
		"description": "This player grants themselves a domain refinement of 3. This player can also 1 time per round discard a card in their hand to remove a negative effect from themselves.",
	},
)


def character_ability_tracks(character_name):
	character = CHARACTERS.get(character_name)
	if not character:
		return ()
	primary = {key: value for key, value in character.items() if key != "additional_abilities"}
	return (primary, *character.get("additional_abilities", ()))


@dataclass(frozen=True)
class Card:
	rank: str
	suit: str = ""
	deck_number: int = 0

	def __str__(self):
		return "Joker" if self.rank == "Joker" else f"{self.rank} of {self.suit}"


@dataclass
class Player:
	name: str
	face_down: list = field(default_factory=list)
	hand: list = field(default_factory=list)
	face_up: list = field(default_factory=list)
	is_bot: bool = False
	character: str = ""
	ability_used_round: int = 0
	ability_uses_count: int = 0
	ability_uses_round: int = 0
	base_ability_removed: bool = False
	evolved_ability_active: bool = False
	ability_states: dict = field(default_factory=dict)
	pending_world_slashes: int = 0
	cut_meter: int = 0
	is_eliminated: bool = False
	ace_streak: int = 0
	it_until_round: int = 0
	enchain_used: bool = False
	vow_card: object = None
	god_round: int = 0
	god_rule: str = ""
	god_grab_value: int = 0
	revealed_cards: list = field(default_factory=list)
	swap_round: int = 0
	rescue_round: int = -99
	known_cards: list = field(default_factory=list)
	six_eyes_turn: int = -1
	domain_shield: bool = False
	domain_draw_turn: int = -1
	simple_domain_used: bool = False
	simple_domain_active: bool = False
	cleanse_round: int = 0
	pending_limitless_effects: list = field(default_factory=list)


DEFAULT_PLAYER_COUNT = 6
MAX_PLAYERS = 12
RANDOM_CHARACTER = "Random"
DEFAULT_DECK_COUNT = 3
DEFAULT_JOKER_COUNT = 8
CARDS_PER_PLAYER = 9
MIN_DRAW_CARDS = 4


def create_deck(rng=None, deck_count=DEFAULT_DECK_COUNT, joker_count=DEFAULT_JOKER_COUNT):
	"""Create and shuffle standard 52-card decks plus the requested number of jokers."""
	rng = rng or random
	cards = [Card(rank, suit, number) for number in range(deck_count)
			 for suit in SUITS for rank in RANKS]
	cards.extend(Card("Joker", deck_number=3) for _ in range(joker_count))
	rng.shuffle(cards)
	return cards


def default_player_names(bot_flags):
	"""Name players; a lone human is "You" and humans otherwise are numbered."""
	humans = sum(1 for is_bot in bot_flags if not is_bot)
	names = []
	bot_number = 0
	for index, is_bot in enumerate(bot_flags, start=1):
		if is_bot:
			bot_number += 1
			names.append(f"Bot {bot_number}")
		else:
			names.append("You" if humans == 1 else f"Player {index}")
	return names


def validate_game_settings(player_count, deck_count, joker_count):
	if player_count < 1:
		raise ValueError("At least one player is required")
	if deck_count < 1:
		raise ValueError("At least one deck is required")
	if joker_count < 0:
		raise ValueError("Jokers cannot be negative")
	total = deck_count * len(SUITS) * len(RANKS) + joker_count
	needed = player_count * CARDS_PER_PLAYER + MIN_DRAW_CARDS
	if total < needed:
		raise ValueError(f"{player_count} players need at least {needed} cards, but only {total} are in the deck")


class PalaceGame:
	def __init__(
		self,
		player_names=None,
		seed=None,
		player_character="Sukuna",
		bot_flags=None,
		characters=None,
		deck_count=DEFAULT_DECK_COUNT,
		joker_count=DEFAULT_JOKER_COUNT,
		start_with_joker=False,
	):
		self.start_with_joker = bool(start_with_joker)
		if bot_flags is None:
			bot_flags = [index > 0 for index in range(len(player_names) if player_names else DEFAULT_PLAYER_COUNT)]
		bot_flags = list(bot_flags)
		if player_names is None:
			player_names = default_player_names(bot_flags)
		if not player_names:
			raise ValueError("At least one player is required")
		if len(bot_flags) != len(player_names):
			raise ValueError("Each player needs a human or bot setting")
		if characters is None:
			characters = [player_character] + [None] * (len(player_names) - 1)
		if len(characters) != len(player_names):
			raise ValueError("Each player needs a character setting")
		validate_game_settings(len(player_names), deck_count, joker_count)
		self.rng = random.Random(seed)
		self.action_log = []
		self.log_path = Path(__file__).with_name("palace_game.log")
		self._record("Game started.")
		deck = create_deck(self.rng, deck_count, joker_count)
		self.players = [
			Player(
				name,
				is_bot=bot_flags[index],
				character=characters[index] or self.rng.choice(tuple(CHARACTERS)),
			)
			for index, name in enumerate(player_names)
		]
		for player in self.players:
			player.ability_states = {
				track["ability"]: {"removed": False, "evolved": False, "uses_count": 0, "uses_round": 0}
				for track in character_ability_tracks(player.character)
			}
		for player in self.players:
			player.face_down = [deck.pop() for _ in range(3)]
			player.hand = [deck.pop() for _ in range(6)]
			if player.is_bot:
				self._record(f"{player.name} chose {player.character}.")
			self._record(f"{player.name} was dealt 3 hidden face-down cards and drew: {', '.join(map(str, player.hand))}.")

		self.draw_piles = [[], []]
		for index, card in enumerate(deck):
			self.draw_piles[index % 2].append(card)
		for pile in self.draw_piles:
			self.rng.shuffle(pile)
		self.discard_piles = [[], []]
		self.destroyed_pile = []
		for pile_index, draw_pile in enumerate(self.draw_piles):
			card = draw_pile.pop()
			while card.rank == "Joker" and any(other.rank != "Joker" for other in draw_pile):
				self._record(f"Setup drew {card} for discard pile {pile_index + 1}; reshuffled it into draw pile {pile_index + 1}.")
				draw_pile.append(card)
				self.rng.shuffle(draw_pile)
				card = draw_pile.pop()
			if card.rank == "10":
				self.destroyed_pile.append(card)
				self._record(f"Setup drew {card} from draw pile {pile_index + 1}; it destroyed discard pile {pile_index + 1}.")
				continue
			self.discard_piles[pile_index].append(card)
			self._record(f"Setup drew {card} from draw pile {pile_index + 1} to start discard pile {pile_index + 1}.")
		self.pile_values = [
			(14 if pile[-1].rank == "Joker" else VALUES[pile[-1].rank]) if pile else 14
			for pile in self.discard_piles
		]
		self.pile_last_player = [None, None]
		self.pile_owner_history = [[None] if pile else [] for pile in self.discard_piles]
		self.pile_value_history = [[value] if pile else [] for value, pile in zip(self.pile_values, self.discard_piles)]
		self.deleted_pile = []
		self.current_player = 0
		self.cards_played_this_turn = 0
		self.turn_pile_index = None
		self.turn_number = 1
		self.round_number = 1
		self.winner = None
		self.finish_order = []
		self.last_remaining_player = None
		self.last_drawn_cards = []
		self.pending_quick_grabs = []
		self.pending_reveals = []
		self.draw_choice_hook = None
		self.domains = []
		self.enchain_player = None
		self.enchain_remaining = 0
		self.enchain_return = None
		self._record(f"Draw piles ready with {len(self.draw_piles[0])} and {len(self.draw_piles[1])} cards.")

	def _record(self, action):
		entry = f"{datetime.now().astimezone().isoformat(timespec='seconds')} | {action}"
		self.action_log.append(entry)
		try:
			with self.log_path.open("a", encoding="utf-8") as log_file:
				log_file.write(entry + "\n")
		except OSError:
			pass

	def effective_ability(self, player_index, base_ability=None):
		player = self.players[player_index]
		tracks = character_ability_tracks(player.character)
		if base_ability is None and tracks:
			base_ability = tracks[0]["ability"]
		for track in tracks:
			if track["ability"] != base_ability and track.get("evolution", {}).get("ability") != base_ability:
				continue
			state = player.ability_states[track["ability"]]
			if state["evolved"]:
				return track["evolution"]["ability"]
			if state["removed"] or track["ability"] != base_ability:
				return None
			return track["ability"]
		return None

	def player_has_immunity(self, player_index):
		player = self.players[player_index]
		return (
			self.effective_ability(player_index, "Limitless Barrier") == "Perfected Limitless"
			or self.round_number <= player.it_until_round
			or self.god_rule(player_index) == "I-T"
			or self.enchain_player == player_index and self.enchain_remaining > 0
		)

	def has_god_of_jujutsu(self, player_index):
		return self.effective_ability(player_index, "God of Jujutsu") == "God of Jujutsu"

	def god_rule(self, player_index):
		"""The multi use rule God of Jujutsu granted for the current round, if any."""
		player = self.players[player_index]
		if player.god_round == self.round_number and player.god_rule and self.has_god_of_jujutsu(player_index):
			return player.god_rule
		return None

	def cleave_ability_name(self, player_index):
		name = self.effective_ability(player_index, "Cleave")
		if name in ("Cleave", "Spider Net Cleave"):
			return name
		return "Cleave" if self.god_rule(player_index) == "Top card discard" else None

	def soul_swap_targets(self, player_index):
		return [
			index for index, target in enumerate(self.players)
			if index != player_index
			and not target.is_eliminated
			and not self.player_has_finished(index)
			and not self.player_has_soul_swap_immunity(index)
			and not self.player_has_immunity(index)
		]

	def can_choose_god_rule(self, player_index):
		player = self.players[player_index]
		return not (
			self.winner is not None
			or player_index != self.current_player
			or not self.has_god_of_jujutsu(player_index)
			or player.god_round == self.round_number
			or self.player_has_finished(player_index)
			or self.enchain_remaining > 0
			or self.enchain_return is not None
			or self.pending_quick_grabs
			or any(p.pending_world_slashes or p.pending_limitless_effects for p in self.players)
		)

	def use_god_rule(self, player_index, rule, value=None, target_index=None):
		if not self.can_choose_god_rule(player_index):
			raise ValueError("God of Jujutsu cannot be used right now")
		if rule not in GOD_RULES:
			raise ValueError("Choose a multi use rule")
		player = self.players[player_index]
		if rule in ("Quick Grab", "Card Swapping") and (value is None or not 2 <= value <= 14):
			raise ValueError(f"Choose a card value from 2 through 14 for {rule}")
		if rule == "Rescue Draw" and not self._rescue_ready(player_index):
			raise ValueError("Rescue Draw was used last round or there is nothing to draw")
		if rule == "Full Hand" and not (player.face_up or player.face_down):
			raise ValueError("There are no face-up or face-down cards to pick up")
		if rule == "Soul Swap":
			if self.cards_played_this_turn != 0:
				raise ValueError("Soul Swap must be used before playing any cards")
			if target_index not in self.soul_swap_targets(player_index):
				raise ValueError("That player cannot be soul swapped with")
			target = self.players[target_index]
			for zone in ("hand", "face_up", "face_down"):
				mine, theirs = getattr(player, zone), getattr(target, zone)
				setattr(player, zone, theirs)
				setattr(target, zone, mine)
		player.god_round = self.round_number
		player.god_rule = rule
		player.god_grab_value = value if rule in ("Quick Grab", "Card Swapping") else 0
		detail = f" for card value {value}" if rule in ("Quick Grab", "Card Swapping") else f" with {self.players[target_index].name}" if rule == "Soul Swap" else ""
		self._record(f"{player.name} used God of Jujutsu to use {rule}{detail} this round.")
		if rule == "Reveal":
			return self.apply_reveal(player_index)
		if rule == "Rescue Draw":
			self._do_rescue_draw(player_index, value)
		if rule == "Full Hand":
			self._do_full_hand(player_index)
		return []

	def bot_god_choice(self, player_index, cards):
		"""Rule a bot should pick: Top card discard when it unblocks a play, otherwise I-T."""
		if not self.can_choose_god_rule(player_index):
			return None
		if self.cards_played_this_turn == 0 and not _bot_legal_options(self, cards):
			player = self.players[player_index]
			player.god_round, player.god_rule = self.round_number, "Top card discard"
			helps = self.bot_cleave_choice(player_index, cards) is not None
			player.god_round, player.god_rule = 0, ""
			if helps:
				return "Top card discard"
		return "I-T"

	def has_six_eyes(self, player_index):
		return self.effective_ability(player_index, "Six Eyes") in ("Six Eyes", "Mastered Six Eyes")

	def is_known(self, viewer_index, card):
		return any(card is known for known in self.players[viewer_index].known_cards)

	def _learn(self, viewer_index, cards):
		known = self.players[viewer_index].known_cards
		for card in cards:
			if not any(card is seen for seen in known):
				known.append(card)

	def known_cards_of(self, viewer_index, owner_index):
		"""Cards held by owner (hand, face-down) that the viewer has permanently seen."""
		owner = self.players[owner_index]
		return [card for zone in (owner.hand, owner.face_down) for card in zone if self.is_known(viewer_index, card)]

	def six_eyes_options(self, player_index):
		player = self.players[player_index]
		options = [("face_down", index) for index, card in enumerate(player.face_down) if not self.is_known(player_index, card)]
		options.extend(
			("hand", index)
			for index, other in enumerate(self.players)
			if index != player_index
			and other.hand
			and not other.is_eliminated
			and not self.player_has_finished(index)
			and not self.player_has_immunity(index)
		)
		return options

	def can_use_six_eyes(self, player_index):
		return (
			player_index == self.current_player
			and not self._is_busy()
			and self.has_six_eyes(player_index)
			and self.players[player_index].six_eyes_turn != self.turn_number
			and not self.player_has_finished(player_index)
			and bool(self.six_eyes_options(player_index))
		)

	def use_six_eyes(self, player_index, kind, index):
		"""View one own face-down card (index = card) or another player's hand (index = player)."""
		if not self.can_use_six_eyes(player_index):
			raise ValueError("Six Eyes cannot be used right now")
		if (kind, index) not in self.six_eyes_options(player_index):
			raise ValueError("Choose something Six Eyes can view")
		player = self.players[player_index]
		if kind == "face_down":
			cards = [player.face_down[index]]
			self._record(f"{player.name} used Six Eyes to view one of their face-down cards.")
		else:
			cards = list(self.players[index].hand)
			self._record(f"{player.name} used Six Eyes to see {self.players[index].name}'s hand.")
		self._learn(player_index, cards)
		player.six_eyes_turn = self.turn_number
		return cards

	def six_eyes_scan(self, player_index):
		"""Mastered Six Eyes: at the start of the turn, see every other player's hand and face-down cards."""
		if self.effective_ability(player_index, "Six Eyes") != "Mastered Six Eyes":
			return
		for index, other in enumerate(self.players):
			if index != player_index and not other.is_eliminated and not self.player_has_immunity(index):
				self._learn(player_index, other.hand + other.face_down)
		self._record(f"{self.players[player_index].name} checked every other player's cards with Mastered Six Eyes.")

	def can_use_full_hand(self, player_index):
		player = self.players[player_index]
		return (
			player_index == self.current_player
			and not self._is_busy()
			and self.effective_ability(player_index, "Six Eyes") == "Mastered Six Eyes"
			and bool(player.face_up or player.face_down)
			and not self.player_has_finished(player_index)
		)

	def use_full_hand(self, player_index):
		if not self.can_use_full_hand(player_index):
			raise ValueError("Full Hand cannot be used right now")
		self._do_full_hand(player_index)

	def _do_full_hand(self, player_index):
		player = self.players[player_index]
		player.hand.extend(player.face_up)
		player.hand.extend(player.face_down)
		player.face_up.clear()
		player.face_down.clear()
		self._record(f"{player.name} used Full Hand and picked up all of their face-up and face-down cards.")

	def _mastered_draw(self, player_index):
		"""Pick 1 of the top 3 cards of each draw pile for a Mastered Six Eyes player."""
		options = [
			(pile_index, depth)
			for pile_index, pile in enumerate(self.draw_piles)
			for depth in range(min(3, len(pile)))
		]

		def value(option):
			card = self.draw_piles[option[0]][-1 - option[1]]
			return 15 if card.rank == "Joker" else VALUES[card.rank]

		choice = None
		if not self.players[player_index].is_bot and self.draw_choice_hook:
			choice = self.draw_choice_hook(player_index, options)
		if choice not in options:
			choice = max(options, key=value)
		pile_index, depth = choice
		return pile_index, self.draw_piles[pile_index].pop(-1 - depth)

	def domain_tracks(self, player_index):
		"""Every domain this player's character has: (name, track, is_evolution, unlocked, refinement, is_open_type)."""
		player = self.players[player_index]
		found = []
		for track in character_ability_tracks(player.character):
			state = player.ability_states.get(track["ability"])
			if state is None:
				continue
			evolution = track.get("evolution", {})
			for config, is_evolution in ((track, False), (evolution, True)):
				name = config.get("ability", "")
				if DOMAIN_TAG not in name:
					continue
				unlocked = state["evolved"] if is_evolution else not state["removed"]
				found.append((name, track, is_evolution, unlocked, config.get("refinement", DEFAULT_DOMAIN_REFINEMENT), config.get("open", False), config.get("duration", DEFAULT_DOMAIN_DURATION)))
		return found

	def player_domain(self, player_index):
		return next((domain for domain in self.domains if domain["player"] == player_index), None)

	def is_clashing(self):
		return len(self.domains) >= 2

	def domain_options(self, player_index):
		"""Domains this player may open right now as (name, unlocked)."""
		player = self.players[player_index]
		if (
			self.winner is not None
			or player.is_eliminated
			or self.player_has_finished(player_index)
			or self.player_domain(player_index)
		):
			return []
		tracks = self.domain_tracks(player_index)
		if not self.domains:
			if player_index != self.current_player:
				return []
			return [(item[0], True) for item in tracks if item[3]]
		return [(item[0], item[3]) for item in tracks]

	def open_domain(self, player_index, name, payment=None, ability=None):
		"""Open (or clash with) a domain. payment is 'refinement', 'joker' or 'ability' for a locked domain."""
		options = dict(self.domain_options(player_index))
		if name not in options:
			raise ValueError("That domain cannot be opened right now")
		player = self.players[player_index]
		entry = next(item for item in self.domain_tracks(player_index) if item[0] == name)
		refinement = entry[4]
		if not options[name]:
			if payment == "refinement":
				if refinement - 1 < 1:
					raise ValueError("The domain's refinement is too low to lower further")
				refinement -= 1
			elif payment == "joker":
				joker = next((card for card in player.hand if card.rank == "Joker"), None)
				if joker is None:
					raise ValueError("You have no Joker in your hand to expend")
				player.hand.remove(joker)
				self.destroyed_pile.append(joker)
			elif payment == "ability":
				if ability is None or DOMAIN_TAG in ability or not self.remove_player_ability(player_index, ability):
					raise ValueError("Choose one of your upgraded abilities to exchange")
			else:
				raise ValueError("Choose how to pay for the locked domain")
		clash = bool(self.domains)
		self.domains.append({"player": player_index, "name": name, "refinement": refinement, "open": entry[5], "rounds_left": entry[6]})
		self._record(f"{player.name} {'clashed with' if clash else 'opened'} {name} (refinement {refinement}).")
		for index, other in enumerate(self.players):
			if other.is_bot and index != player_index:
				self.bot_domain_clash(index)
		return refinement

	def domain_shatter(self, player_index, reason):
		domain = self.player_domain(player_index)
		if domain is None:
			return False
		if self.is_clashing() and domain["open"]:
			return False
		self.domains.remove(domain)
		self._record(f"{self.players[player_index].name}'s {domain['name']} shattered ({reason}).")
		return True

	def cancel_turn(self, player_index):
		"""Call when a player's turn is canceled; their domain shatters instantly."""
		self.domain_shatter(player_index, "turn canceled")

	def _domain_decrease(self, domain, amount=1):
		player = self.players[domain["player"]]
		if player.domain_shield:
			player.domain_shield = False
			self._record(f"{player.name}'s royal card blocked a refinement decrease on {domain['name']}.")
			return
		domain["refinement"] -= amount
		if domain["refinement"] <= 0:
			if domain["open"] and self.is_clashing():
				domain["refinement"] = 1
			else:
				self.domains.remove(domain)
				self._record(f"{player.name}'s {domain['name']} broke at refinement 0.")

	def domain_round_end(self):
		"""Called once per round: clashing domains lose refinement and the weaker ones shatter; time limits tick down."""
		if self.is_clashing():
			for domain in list(self.domains):
				self._domain_decrease(domain)
			if self.is_clashing():
				best = max(domain["refinement"] for domain in self.domains)
				for domain in list(self.domains):
					if domain["refinement"] < best and not domain["open"]:
						self.domains.remove(domain)
						self._record(f"{self.players[domain['player']].name}'s {domain['name']} shattered against a higher refinement.")
		for domain in list(self.domains):
			if domain.get("rounds_left") is None:
				continue
			domain["rounds_left"] -= 1
			if domain["rounds_left"] <= 0:
				self.domains.remove(domain)
				self._record(f"{self.players[domain['player']].name}'s {domain['name']} ran out of time and closed.")

	def domain_effect_active(self, player_index):
		"""Whether this player's open domain currently applies its effect."""
		domain = self.player_domain(player_index)
		if domain is None:
			return False
		if not self.is_clashing():
			return True
		return any(
			other["open"] and other["player"] != player_index and domain["refinement"] > other["refinement"]
			for other in self.domains
		)

	def can_domain_draw(self, player_index):
		player = self.players[player_index]
		return (
			self.is_clashing()
			and self.player_domain(player_index) is not None
			and player_index == self.current_player
			and player.domain_draw_turn != self.turn_number
			and any(self.draw_piles)
			and self.winner is None
		)

	def domain_draw(self, player_index):
		if not self.can_domain_draw(player_index):
			raise ValueError("You cannot draw for your domain right now")
		player = self.players[player_index]
		domain = self.player_domain(player_index)
		pile = self.rng.choice([p for p in self.draw_piles if p])
		card = pile.pop()
		player.hand.append(card)
		player.domain_draw_turn = self.turn_number
		if card.rank == "Joker":
			domain["refinement"] += 1
			result = "a Joker: refinement +1"
		elif card.rank in ("Jack", "Queen", "King"):
			player.domain_shield = True
			result = "a royal card: the next refinement decrease is blocked"
		elif card.rank in ("2", "3", "4", "5"):
			result = "a 2-5: refinement -1"
			self._domain_decrease(domain)
		else:
			result = "no effect"
		self._record(f"{player.name} drew {card} for {domain['name']}: {result}.")
		return card, result

	def can_joker_domain(self, player_index):
		player = self.players[player_index]
		return (
			len(self.domains) >= 3
			and self.player_domain(player_index) is None
			and any(card.rank == "Joker" for card in player.hand)
			and not player.is_eliminated
			and not self.player_has_finished(player_index)
		)

	def joker_domain(self, player_index, target_index):
		if not self.can_joker_domain(player_index):
			raise ValueError("You cannot use a Joker against a domain right now")
		domain = self.player_domain(target_index)
		if domain is None:
			raise ValueError("That player has no open domain")
		player = self.players[player_index]
		joker = next(card for card in player.hand if card.rank == "Joker")
		player.hand.remove(joker)
		self.destroyed_pile.append(joker)
		self._record(f"{player.name} expended a Joker to weaken {domain['name']}.")
		self._domain_decrease(domain)

	def bot_domain_clash(self, player_index):
		"""A bot clashes when it can: unlocked domains first, then paying with a Joker or refinement."""
		if not self.domains or self.player_domain(player_index):
			return False
		options = self.domain_options(player_index)
		if not options:
			return False
		name, unlocked = options[0]
		player = self.players[player_index]
		payment = None
		if not unlocked:
			payment = "joker" if any(card.rank == "Joker" for card in player.hand) else "refinement"
		try:
			self.open_domain(player_index, name, payment)
		except ValueError:
			return False
		return True

	def bot_domain_actions(self, player_index):
		notes = []
		if not self.domains and self.domain_options(player_index):
			name = self.domain_options(player_index)[0][0]
			self.open_domain(player_index, name)
			notes.append(f"opened {name}")
		if self.can_domain_draw(player_index):
			self.domain_draw(player_index)
			notes.append("drew for their domain")
		if self.can_joker_domain(player_index) and self.domains:
			target = max(self.domains, key=lambda domain: domain["refinement"])["player"]
			self.joker_domain(player_index, target)
			notes.append("used a Joker against a domain")
		return notes

	def has_simple_domain(self, player_index):
		return self.effective_ability(player_index, "Simple Domain") == "Simple Domain"

	def simple_domain_refinement(self, player_index):
		return SIMPLE_DOMAIN_REFINEMENT if self.players[player_index].simple_domain_active else 0

	def can_use_simple_domain(self, player_index):
		player = self.players[player_index]
		return not (
			self.winner is not None
			or not self.has_simple_domain(player_index)
			or player.simple_domain_used
			or player.is_eliminated
			or self.player_has_finished(player_index)
		)

	def use_simple_domain(self, player_index):
		"""Once per game: protects only the user, has no guaranteed hit and never opens a clash."""
		if not self.can_use_simple_domain(player_index):
			raise ValueError("Simple Domain cannot be used right now")
		player = self.players[player_index]
		player.simple_domain_used = True
		player.simple_domain_active = True
		self._record(f"{player.name} activated Simple Domain (refinement {SIMPLE_DOMAIN_REFINEMENT}).")

	def domain_lands_on(self, attacker_index, target_index):
		"""An enemy domain's effect lands on a Simple Domain user only if its refinement is greater."""
		protection = self.simple_domain_refinement(target_index)
		if not protection:
			return True
		domain = self.player_domain(attacker_index)
		return domain is not None and domain["refinement"] > protection

	def negative_effects(self, player_index):
		player = self.players[player_index]
		effects = []
		if player.cut_meter > 0:
			effects.append("Cut Meter")
		if self.revealed_cards(player_index):
			effects.append("Reveal")
		return effects

	def can_simple_cleanse(self, player_index):
		player = self.players[player_index]
		return (
			player.simple_domain_active
			and self.has_simple_domain(player_index)
			and player.cleanse_round != self.round_number
			and bool(player.hand)
			and bool(self.negative_effects(player_index))
			and self.winner is None
		)

	def simple_cleanse(self, player_index, effect, hand_index):
		if not self.can_simple_cleanse(player_index):
			raise ValueError("Simple Domain cannot remove an effect right now")
		player = self.players[player_index]
		if effect not in self.negative_effects(player_index):
			raise ValueError("That effect is not on this player")
		if not 0 <= hand_index < len(player.hand):
			raise ValueError("Choose a card from your hand to discard")
		card = player.hand.pop(hand_index)
		self.destroyed_pile.append(card)
		if effect == "Cut Meter":
			player.cut_meter -= 1
		else:
			player.revealed_cards = []
		player.cleanse_round = self.round_number
		self._record(f"{player.name} discarded {card} with Simple Domain to remove {effect}.")

	def bot_simple_domain(self, player_index):
		notes = []
		player = self.players[player_index]
		if self.can_use_simple_domain(player_index) and (
			player.cut_meter >= 3 or any(domain["player"] != player_index for domain in self.domains)
		):
			self.use_simple_domain(player_index)
			notes.append("activated Simple Domain")
		if self.can_simple_cleanse(player_index) and len(player.hand) > 1:
			lowest = min(range(len(player.hand)), key=lambda i: 15 if player.hand[i].rank == "Joker" else VALUES[player.hand[i].rank])
			self.simple_cleanse(player_index, self.negative_effects(player_index)[0], lowest)
			notes.append("removed a negative effect with Simple Domain")
		return notes

	def revealed_cards(self, player_index):
		player = self.players[player_index]
		player.revealed_cards = [card for card in player.revealed_cards if any(card is held for held in player.hand)]
		return player.revealed_cards

	def swap_ranks(self, player_index):
		ability = self.effective_ability(player_index, "Lapse Blue")
		ranks = {"5", "6", "9"} if ability == "Reversal Red" else {"5"} if ability == "Lapse Blue" else set()
		if self.god_rule(player_index) == "Card Swapping":
			ranks.add(RANKS[self.players[player_index].god_grab_value - 2])
		return ranks

	def swap_target_cards(self, owner, zone):
		"""The list of cards a swap target refers to; owner -1 means the shared piles."""
		if owner >= 0:
			return getattr(self.players[owner], zone)
		return self.destroyed_pile if zone == "destroyed" else self.discard_piles[int(zone[-1])]

	def swap_target_card(self, target):
		return self.swap_target_cards(target[0], target[1])[target[2]]

	def _is_busy(self):
		return bool(
			self.winner is not None
			or self.enchain_remaining > 0
			or self.enchain_return is not None
			or self.pending_quick_grabs
			or any(p.pending_world_slashes or p.pending_limitless_effects for p in self.players)
		)

	def can_use_card_swapping(self, player_index):
		return (
			player_index == self.current_player
			and not self._is_busy()
			and bool(self.swap_ranks(player_index))
			and not self.player_has_finished(player_index)
			and bool(self.card_swap_options(player_index)[0])
			and bool(self.card_swap_options(player_index)[1])
		)

	def card_swap_options(self, player_index):
		"""Own swappable cards and the visible cards of other players they can be swapped for."""
		player = self.players[player_index]
		ranks = self.swap_ranks(player_index)
		own = [
			(zone, index)
			for zone in ("hand", "face_up", "face_down")
			for index, card in enumerate(getattr(player, zone))
			if card.rank in ranks and (zone != "face_down" or self.is_known(player_index, card))
		]
		theirs = []
		for target_index, target in enumerate(self.players):
			if (
				target_index == player_index
				or target.is_eliminated
				or self.player_has_finished(target_index)
				or self.player_has_immunity(target_index)
				or self.has_god_of_jujutsu(target_index)
			):
				continue
			theirs.extend((target_index, "face_up", index) for index in range(len(target.face_up)))
			revealed = self.revealed_cards(target_index)
			theirs.extend(
				(target_index, "hand", index)
				for index, card in enumerate(target.hand)
				if any(card is shown for shown in revealed) or self.is_known(player_index, card)
			)
			theirs.extend(
				(target_index, "face_down", index)
				for index, card in enumerate(target.face_down)
				if self.is_known(player_index, card)
			)
		for pile_index, pile in enumerate(self.discard_piles):
			theirs.extend((-1, f"discard{pile_index}", index) for index in range(len(pile)))
		theirs.extend((-1, "destroyed", index) for index in range(len(self.destroyed_pile)))
		return own, theirs

	def card_swap(self, player_index, own_zone, own_index, target_index, target_zone, target_card_index):
		if not self.can_use_card_swapping(player_index):
			raise ValueError("Card Swapping cannot be used right now")
		own, theirs = self.card_swap_options(player_index)
		if (own_zone, own_index) not in own:
			raise ValueError("Choose one of your own visible 5s, 6s or 9s that can be swapped")
		if (target_index, target_zone, target_card_index) not in theirs:
			raise ValueError("Choose a card you can see")
		player = self.players[player_index]
		mine = getattr(player, own_zone)
		theirs_cards = self.swap_target_cards(target_index, target_zone)
		mine[own_index], theirs_cards[target_card_index] = theirs_cards[target_card_index], mine[own_index]
		player.swap_round = self.round_number
		if target_index < 0:
			where = "the destroyed pile" if target_zone == "destroyed" else f"discard pile {int(target_zone[-1]) + 1}"
			pile_index = None if target_zone == "destroyed" else int(target_zone[-1])
			if pile_index is not None:
				new_card = mine[own_index]
				pile = self.discard_piles[pile_index]
				if new_card.rank != "Joker":
					self.pile_value_history[pile_index][target_card_index] = VALUES[new_card.rank]
				if target_card_index == len(pile) - 1:
					self.pile_values[pile_index] = self.pile_value_history[pile_index][-1]
		else:
			where = f"{self.players[target_index].name}'s {target_zone.replace('_', ' ')}"
		self._record(f"{player.name} used Card Swapping to swap {theirs_cards[target_card_index]} from their {own_zone.replace('_', ' ')} with {mine[own_index]} from {where}.")
		return self.apply_reveal(player_index)

	def apply_reveal(self, source_index):
		"""Make every other non-immune player reveal a hand card; returns humans who must still choose."""
		self.pending_reveals = []
		for index, other in enumerate(self.players):
			if (
				index == source_index
				or other.is_eliminated
				or self.player_has_finished(index)
				or self.player_has_immunity(index)
				or not other.hand
				or self.revealed_cards(index)
			):
				continue
			if other.is_bot:
				self.reveal_card(index, self.rng.randrange(len(other.hand)), queued=False)
			else:
				self.pending_reveals.append(index)
		return list(self.pending_reveals)

	def reveal_card(self, player_index, hand_index, queued=True):
		if queued and player_index not in self.pending_reveals:
			raise ValueError("This player does not need to reveal a card")
		player = self.players[player_index]
		if not 0 <= hand_index < len(player.hand):
			raise ValueError("Choose a card from your hand")
		card = player.hand[hand_index]
		player.revealed_cards.append(card)
		if player_index in self.pending_reveals:
			self.pending_reveals.remove(player_index)
		self._record(f"{player.name} revealed {card} until it is played.")

	def _rescue_ready(self, player_index):
		return (
			self.round_number - self.players[player_index].rescue_round >= 2
			and (any(self.draw_piles) or bool(self.destroyed_pile))
		)

	def can_use_rescue_draw(self, player_index):
		return (
			player_index == self.current_player
			and not self._is_busy()
			and self.effective_ability(player_index, "Lapse Blue") == "Reversal Red"
			and not self.player_has_finished(player_index)
			and self._rescue_ready(player_index)
		)

	def use_rescue_draw(self, player_index, destroyed_index=None):
		if not self.can_use_rescue_draw(player_index):
			raise ValueError("Rescue Draw cannot be used right now")
		self._do_rescue_draw(player_index, destroyed_index)

	def _do_rescue_draw(self, player_index, destroyed_index=None):
		player = self.players[player_index]
		if any(self.draw_piles):
			for _ in range(2):
				available = [i for i, pile in enumerate(self.draw_piles) if pile]
				if not available:
					break
				player.hand.append(self.draw_piles[self.rng.choice(available)].pop())
			self._record(f"{player.name} used Rescue Draw and drew from the draw piles.")
		else:
			if destroyed_index is None or not 0 <= destroyed_index < len(self.destroyed_pile):
				raise ValueError("Choose a card from the destroyed pile")
			card = self.destroyed_pile.pop(destroyed_index)
			player.hand.append(card)
			self._record(f"{player.name} used Rescue Draw and took {card} from the destroyed pile.")
		player.rescue_round = self.round_number

	def bot_lapse_actions(self, player_index):
		"""Bots use Rescue Draw whenever available and swap a low rank for the best visible card."""
		notes = []
		notes.extend(self.bot_simple_domain(player_index))
		notes.extend(self.bot_domain_actions(player_index))
		if self.can_use_six_eyes(player_index):
			targets = [option for option in self.six_eyes_options(player_index) if option[0] == "hand"]
			if targets:
				self.use_six_eyes(player_index, *max(targets, key=lambda option: len(self.players[option[1]].hand)))
				notes.append("used Six Eyes")
		if self.can_use_rescue_draw(player_index):
			index = None
			if not any(self.draw_piles):
				index = max(range(len(self.destroyed_pile)), key=lambda i: 15 if self.destroyed_pile[i].rank == "Joker" else VALUES[self.destroyed_pile[i].rank])
			self.use_rescue_draw(player_index, index)
			notes.append("used Rescue Draw")
		if self.can_use_card_swapping(player_index):
			own, theirs = self.card_swap_options(player_index)

			def value(card):
				return 15 if card.rank == "Joker" else VALUES[card.rank]

			player = self.players[player_index]
			own_pick = min(own, key=lambda item: value(getattr(player, item[0])[item[1]]))
			their_pick = max(theirs, key=lambda item: value(self.swap_target_card(item)))
			if value(self.swap_target_card(their_pick)) > value(getattr(player, own_pick[0])[own_pick[1]]):
				self.card_swap(player_index, *own_pick, *their_pick)
				notes.append("used Card Swapping and made everyone reveal a card")
		return notes

	def quick_grab_values(self, player_index):
		values = set()
		if self.effective_ability(player_index, "Limitless Barrier") == "Perfected Limitless":
			values.add(VALUES["Ace"])
		if self.god_rule(player_index) == "Quick Grab":
			values.add(self.players[player_index].god_grab_value)
		return values

	def player_has_soul_swap_immunity(self, player_index):
		"""Specific Soul Swap immunity; general-immunity bypasses never override it."""
		return self.has_god_of_jujutsu(player_index)

	def enchain_targets(self, player_index):
		ability = self.effective_ability(player_index, "Enchain")
		return [
			index for index, target in enumerate(self.players)
			if index != player_index
			and not target.is_eliminated
			and not self.player_has_finished(index)
			and not self.player_has_soul_swap_immunity(index)
			and (ability == "Rule Workaround" or not self.player_has_immunity(index))
		]

	def can_use_enchain(self, player_index):
		if (
			self.winner is not None
			or self.enchain_remaining > 0
			or self.pending_quick_grabs
			or any(p.pending_world_slashes or p.pending_limitless_effects for p in self.players)
			or self.effective_ability(player_index, "Enchain") not in ("Enchain", "Rule Workaround")
			or self.players[player_index].enchain_used
			or self.player_has_finished(player_index)
			or not self.enchain_targets(player_index)
		):
			return False
		return player_index != self.current_player or self.cards_played_this_turn == 0

	def use_enchain(self, player_index, target_index):
		if not self.can_use_enchain(player_index):
			raise ValueError("Enchain cannot be used right now")
		if target_index not in self.enchain_targets(player_index):
			raise ValueError("That player cannot be soul swapped with")
		player = self.players[player_index]
		target = self.players[target_index]
		if player_index != self.current_player:
			self.enchain_return = {
				"current_player": self.current_player,
				"cards_played": self.cards_played_this_turn,
				"turn_pile_index": self.turn_pile_index,
			}
			self.current_player = player_index
			self.cards_played_this_turn = 0
			self.turn_pile_index = None
		for zone in ("hand", "face_up", "face_down"):
			mine, theirs = getattr(player, zone), getattr(target, zone)
			setattr(player, zone, theirs)
			setattr(target, zone, mine)
		player.enchain_used = True
		self.enchain_player = player_index
		self.enchain_remaining = 2
		self._record(f"{player.name} used {self.effective_ability(player_index, 'Enchain')} and soul swapped all cards with {target.name}; {player.name} must play 2 cards and is immune to other players' effects meanwhile.")

	def is_vow_card(self, player_index, card):
		return (
			card is not None
			and self.players[player_index].vow_card is card
			and self.effective_ability(player_index, "Binding Vow") in ("Binding Vow", "Binding Vow Merchant")
		)

	def binding_vow_cards(self, player_index):
		player = self.players[player_index]
		if player.hand:
			return player.hand
		return [] if any(self.draw_piles) else player.face_up

	def can_use_binding_vow(self, player_index):
		player = self.players[player_index]
		return not (
			self.winner is not None
			or player_index != self.current_player
			or self.cards_played_this_turn != 0
			or self.enchain_remaining > 0
			or self.enchain_return is not None
			or self.pending_quick_grabs
			or any(p.pending_world_slashes or p.pending_limitless_effects for p in self.players)
			or self.effective_ability(player_index, "Binding Vow") not in ("Binding Vow", "Binding Vow Merchant")
			or player.vow_card is not None
			or self.player_has_finished(player_index)
			or not self.binding_vow_cards(player_index)
		)

	def use_binding_vow(self, player_index, card_index):
		if not self.can_use_binding_vow(player_index):
			raise ValueError("Binding Vow cannot be used right now")
		cards = self.binding_vow_cards(player_index)
		if not 0 <= card_index < len(cards):
			raise ValueError("Choose a card from your hand")
		player = self.players[player_index]
		player.vow_card = cards[card_index]
		self._record(f"{player.name} used Binding Vow, passing their turn; {player.vow_card} will be played as a King.")
		self.end_turn()

	def bot_binding_vow_choice(self, player_index):
		"""Index of the lowest card a bot should bind, or None when it cannot use the vow."""
		if not self.can_use_binding_vow(player_index):
			return None
		cards = self.binding_vow_cards(player_index)
		return min(range(len(cards)), key=lambda i: 14 if cards[i].rank == "Joker" else VALUES[cards[i].rank])

	def bot_cleave_choice(self, player_index, cards):
		"""Pick a pile where Cleave would let a bot who has no legal play make one."""
		if (
			self.cleave_ability_name(player_index) is None
			or self.ability_uses_remaining(player_index, "Cleave") == 0
		):
			return None
		player = self.players[player_index]
		available = len(player.hand) + len(player.face_up) + len(player.face_down)
		for pile_index, pile in enumerate(self.discard_piles):
			if not pile or (self.cards_played_this_turn and self.turn_pile_index is not None and pile_index != self.turn_pile_index):
				continue
			if len(pile) == 1 and self.effective_ability(player_index, "Cleave") == "Spider Net Cleave" and available >= 2:
				continue
			saved = (
				list(pile),
				list(self.pile_owner_history[pile_index]),
				list(self.pile_value_history[pile_index]),
				self.pile_values[pile_index],
				self.pile_last_player[pile_index],
			)
			pile.pop()
			self.pile_owner_history[pile_index].pop()
			self.pile_value_history[pile_index].pop()
			self.pile_last_player[pile_index] = self.pile_owner_history[pile_index][-1] if pile else None
			self.pile_values[pile_index] = self.pile_value_history[pile_index][-1] if pile else 14
			try:
				playable = any(
					self.can_play(card, pile_index, joker_value=14 if card.rank == "Joker" else None)
					for card in cards
				)
			finally:
				pile[:] = saved[0]
				self.pile_owner_history[pile_index][:] = saved[1]
				self.pile_value_history[pile_index][:] = saved[2]
				self.pile_values[pile_index] = saved[3]
				self.pile_last_player[pile_index] = saved[4]
			if playable:
				return pile_index
		return None

	def enchain_must_keep_playing(self, player_index):
		if self.enchain_player != player_index or self.enchain_remaining <= 0:
			return False
		player = self.players[player_index]
		if player.hand:
			cards = player.hand
		elif any(self.draw_piles):
			return False
		elif player.face_up:
			cards = player.face_up
		else:
			return bool(player.face_down)
		return any(
			self.can_play(card, pile_index, joker_value=14 if card.rank == "Joker" else None)
			for card in cards
			for pile_index in (0, 1)
		)

	def _quick_grab_targets(self, player_index, card_value, source, count_as_play):
		if not count_as_play or source.startswith("Spider Net Cleave") or self.player_has_immunity(player_index):
			return []
		return [
			target_index for target_index, target in enumerate(self.players)
			if target_index != player_index
			and not target.is_eliminated
			and not self.player_has_finished(target_index)
			and card_value in self.quick_grab_values(target_index)
		]

	def _record_limitless_ace(self, player_index, card, stack_destroy):
		player = self.players[player_index]
		ability = self.effective_ability(player_index, "Limitless Barrier")
		if ability not in ("Limitless Barrier", "Perfected Limitless"):
			player.ace_streak = 0
			return
		# Called for any card played as an Ace, including Jokers.
		player.ace_streak += 1
		if player.ace_streak <= 2:
			player.it_until_round = max(player.it_until_round, self.round_number + 1)
		elif player.ace_streak == 3:
			player.it_until_round = max(player.it_until_round, self.round_number + 2)
		if player.ace_streak == 2:
			player.pending_limitless_effects.append("pick_one_face_down")
		elif player.ace_streak == 3:
			player.pending_limitless_effects.append("pick_all_face_down")
		elif player.ace_streak == 4:
			state = player.ability_states["Limitless Barrier"]
			if not state["evolved"]:
				state["evolved"] = True
				player.pending_limitless_effects.append("replace_hand_from_deleted")
				self._record(f"{player.name} evolved Limitless Barrier into Perfected Limitless after four consecutive Aces.")

	def resolve_limitless_effect(self, player_index, face_down_index=None, deleted_indices=None):
		if player_index != self.current_player:
			raise ValueError("Limitless effects resolve on their owner's turn")
		player = self.players[player_index]
		if not player.pending_limitless_effects:
			raise ValueError("There are no pending Limitless effects")
		effect = player.pending_limitless_effects[0]
		if effect == "pick_one_face_down":
			if not player.face_down:
				player.pending_limitless_effects.pop(0)
				self._record(f"{player.name} had no face-down cards to pick up for Limitless Barrier.")
				return []
			if face_down_index is None or not 0 <= face_down_index < len(player.face_down):
				raise ValueError("Choose one of your face-down cards")
			cards = [player.face_down.pop(face_down_index)]
		elif effect == "pick_all_face_down":
			cards = list(player.face_down)
			player.face_down.clear()
		else:
			old_hand_size = len(player.hand)
			count = min(old_hand_size, len(self.deleted_pile))
			if count == 0:
				player.pending_limitless_effects.pop(0)
				self._record(f"{player.name} had no deleted cards available to replace their hand.")
				return []
			if deleted_indices is None:
				raise ValueError("Choose deleted cards to replace your hand")
			if len(deleted_indices) != count or len(set(deleted_indices)) != count:
				raise ValueError(f"Choose {count} different deleted cards")
			if any(index < 0 or index >= len(self.deleted_pile) for index in deleted_indices):
				raise ValueError("Deleted card index out of range")
			cards = [self.deleted_pile[index] for index in deleted_indices]
			self.destroyed_pile.extend(player.hand)
			player.hand.clear()
			for index in sorted(deleted_indices, reverse=True):
				self.deleted_pile.pop(index)
			player.hand.extend(cards)
			player.pending_limitless_effects.pop(0)
			self._record(f"{player.name} replaced their hand with {len(cards)} cards from Deleted using Limitless Barrier.")
			return cards
		player.hand.extend(cards)
		player.pending_limitless_effects.pop(0)
		self._record(f"{player.name} picked up {len(cards)} face-down card(s) with Limitless Barrier.")
		return cards

	def resolve_bot_limitless_effects(self, player_index):
		player = self.players[player_index]
		while player.pending_limitless_effects and self.winner is None:
			effect = player.pending_limitless_effects[0]
			if effect == "pick_one_face_down":
				index = self.rng.randrange(len(player.face_down)) if player.face_down else None
				self.resolve_limitless_effect(player_index, face_down_index=index)
			elif effect == "pick_all_face_down":
				self.resolve_limitless_effect(player_index)
			else:
				count = min(len(player.hand), len(self.deleted_pile))
				indices = self.rng.sample(range(len(self.deleted_pile)), count) if count else ()
				self.resolve_limitless_effect(player_index, deleted_indices=indices)

	def resolve_quick_grab(self, grabber_index, accept):
		if not self.pending_quick_grabs:
			raise ValueError("There is no card waiting for Quick Grab")
		event = self.pending_quick_grabs[0]
		if grabber_index not in event["targets"] or self.player_has_immunity(event["played_by"]):
			raise ValueError("This player does not have Quick Grab for this card")
		if accept:
			pile = self.destroyed_pile if event["zone"] == "destroyed_pile" else self.discard_piles[event["pile_index"]]
			try:
				card_index = next(index for index, card in enumerate(pile) if card is event["card"])
			except StopIteration as error:
				raise ValueError("That card is no longer on its pile") from error
			card = pile.pop(card_index)
			if event["zone"] == "discard_pile":
				self.pile_owner_history[event["pile_index"]].pop(card_index)
				self.pile_value_history[event["pile_index"]].pop(card_index)
				self.pile_last_player[event["pile_index"]] = self.pile_owner_history[event["pile_index"]][-1] if pile else None
				self.pile_values[event["pile_index"]] = self.pile_value_history[event["pile_index"]][-1] if pile else 14
			self.players[grabber_index].hand.append(card)
			if event["played_by"] == self.current_player and self.cards_played_this_turn > 0 and self.enchain_remaining == 0:
				# A grabbed card no longer counts as played, so the player can keep playing normally.
				self.cards_played_this_turn -= 1
				if self.cards_played_this_turn == 0:
					self.turn_pile_index = None
			self._record(f"{self.players[grabber_index].name} used Quick Grab to take {card} played by {self.players[event['played_by']].name}.")
		else:
			event["targets"].remove(grabber_index)
			self._record(f"{self.players[grabber_index].name} declined Quick Grab.")
		if accept or not event["targets"]:
			self.pending_quick_grabs.pop(0)
		self._check_winner()
		return accept

	def resolve_bot_quick_grabs(self):
		while self.pending_quick_grabs and self.winner is None:
			event = self.pending_quick_grabs[0]
			if any(not self.players[index].is_bot for index in event["targets"]):
				return
			targets = [
				index for index in event["targets"]
				if not self.player_has_immunity(event["played_by"])
				and not self.players[index].is_eliminated
			]
			if not targets:
				self.pending_quick_grabs.pop(0)
				continue
			bot_targets = [index for index in targets if self.players[index].is_bot]
			if not bot_targets:
				return
			grabber = self.rng.choice(bot_targets)
			self.resolve_quick_grab(grabber, True)

	def remove_player_ability(self, player_index, ability_name):
		player = self.players[player_index]
		for track in character_ability_tracks(player.character):
			state = player.ability_states[track["ability"]]
			if ability_name == track.get("evolution", {}).get("ability"):
				if not state["evolved"]:
					return False
				state["evolved"] = False
				state["removed"] = False
				state["uses_count"] = 0
				state["uses_round"] = 0
				self._record(f"{player.name} lost {ability_name}; {track['ability']} is retained.")
				return True
			if ability_name == track["ability"]:
				state["removed"] = True
				self._record(f"{player.name}'s base ability {ability_name} was removed.")
				return True
		return False

	def evolve_ability(self, player_index, joker_index, ability_name=None):
		if player_index != self.current_player:
			raise ValueError("Abilities can only be evolved on your own turn")
		if self.cards_played_this_turn != 0:
			raise ValueError("Abilities can only be evolved before playing any cards")
		player = self.players[player_index]
		tracks = [
			track for track in character_ability_tracks(player.character)
			if "evolution" in track
			and not player.ability_states[track["ability"]]["removed"]
			and not player.ability_states[track["ability"]]["evolved"]
		]
		if ability_name is None:
			if len(tracks) != 1:
				raise ValueError("Choose which ability to evolve")
			track = tracks[0]
		else:
			track = next((item for item in tracks if item["ability"] == ability_name), None)
			if track is None:
				raise ValueError("This ability cannot be evolved")
		if not 0 <= joker_index < len(player.hand) or player.hand[joker_index].rank != "Joker":
			raise ValueError("A Joker in your hand is required to evolve")
		joker = player.hand.pop(joker_index)
		self.deleted_pile.append(joker)
		player.ability_states[track["ability"]]["evolved"] = True
		player.ability_states[track["ability"]]["uses_count"] = 0
		player.ability_states[track["ability"]]["uses_round"] = 0
		self._record(f"{player.name} evolved {track['ability']} into {track['evolution']['ability']} and deleted a Joker.")
		self._draw_to_three(player)
		self._check_winner()
		if self.winner is None:
			self.end_turn()
		return joker

	def choose_face_up(self, player_index, hand_indices):
		"""Set aside exactly three of a player's six visible cards."""
		player = self.players[player_index]
		if player.face_up or len(hand_indices) != 3 or len(set(hand_indices)) != 3:
			raise ValueError("Choose three different cards once")
		if any(index < 0 or index >= len(player.hand) for index in hand_indices):
			raise ValueError("Hand card index out of range")
		selected = set(hand_indices)
		player.face_up = [card for i, card in enumerate(player.hand) if i in selected]
		player.hand = [card for i, card in enumerate(player.hand) if i not in selected]
		self._record(f"{player.name} set aside face-up cards: {', '.join(map(str, player.face_up))}.")
		if self.start_with_joker:
			player.hand.append(Card("Joker", deck_number=3))
			self._record(f"{player.name} started the game with a bonus Joker.")

	def can_play(self, card, pile_index, joker_value=None):
		if pile_index not in (0, 1):
			return False
		if self.cards_played_this_turn and self.turn_pile_index is not None and pile_index != self.turn_pile_index:
			return False
		if self.is_vow_card(self.current_player, card):
			card = Card("King", card.suit, card.deck_number)
			joker_value = None
		if (
			self.enchain_remaining > 0
			and self.enchain_player == self.current_player
			and self.effective_ability(self.current_player, "Enchain") == "Rule Workaround"
		):
			return True
		plays_as_king = card.rank == "King" or card.rank == "Joker" and joker_value == VALUES["King"]
		if plays_as_king and self.effective_ability(self.current_player, "World Cutting Slash") == "Waffle Cutting Slash":
			return True
		pile = self.discard_piles[pile_index]
		first = self.cards_played_this_turn == 0
		if not pile:
			return True
		if (
			self.effective_ability(self.current_player, "Binding Vow") == "Binding Vow Merchant"
			and self.pile_last_player[pile_index] == self.current_player
			and self.pile_values[pile_index] == VALUES["King"]
		):
			return True
		plays_as_two = card.rank == "2" or card.rank == "Joker" and joker_value == 2
		if plays_as_two:
			top_is_ace_or_two = self.pile_values[pile_index] in (2, 14)
			return first or top_is_ace_or_two
		if (card.rank == "10" or card.rank == "Joker" and joker_value == 10) and first:
			return True
		if self.cards_played_this_turn and self.pile_last_player[pile_index] == self.current_player:
			card_value = joker_value if card.rank == "Joker" else VALUES[card.rank]
			if card.rank == "Joker" and joker_value is None:
				return True
			return self.pile_values[pile_index] <= card_value <= self.pile_values[pile_index] + 1
		if card.rank == "Joker":
			return True
		return VALUES[card.rank] >= self.pile_values[pile_index]

	def ability_uses_remaining(self, player_index, base_ability="Cleave"):
		player = self.players[player_index]
		ability = self.effective_ability(player_index, base_ability)
		limit = 5 if ability == "Spider Net Cleave" else 1 if ability == "Cleave" else 0
		if self.god_rule(player_index) == "Top card discard" and base_ability == "Cleave":
			limit += 1
		state = player.ability_states.get(base_ability, {})
		used = state.get("uses_count", 0) if state.get("uses_round") == self.round_number else 0
		return max(0, limit - used)

	def use_cleave(
		self,
		player_index,
		pile_index,
		replacement_indices=None,
		replacement_joker_values=None,
		replacement_sources=None,
	):
		if player_index != self.current_player:
			raise ValueError("Abilities can only be used on your own turn")
		cleave_ability = self.cleave_ability_name(player_index)
		if cleave_ability is None:
			raise ValueError("This player does not have Cleave")
		if self.ability_uses_remaining(player_index, "Cleave") == 0:
			raise ValueError("Cleave has no uses remaining this round")
		if pile_index not in (0, 1):
			raise ValueError("Invalid discard pile")
		pile = self.discard_piles[pile_index]
		if not pile:
			raise ValueError("Cannot use Cleave on an empty discard pile")
		player = self.players[player_index]
		available_replacements = sum(len(getattr(player, source)) for source in ("hand", "face_up", "face_down"))
		spider_net_chain = (
			cleave_ability == "Spider Net Cleave"
			and len(pile) == 1
			and available_replacements >= 2
		)
		if spider_net_chain:
			replacement_sources = replacement_sources or ("hand", "hand")
			if replacement_indices is None or len(replacement_indices) != 2 or len(replacement_sources) != 2:
				raise ValueError("Choose two different cards to replace the piles")
			if any(source not in ("hand", "face_up", "face_down") for source in replacement_sources):
				raise ValueError("Invalid replacement card source")
			if len(set(zip(replacement_sources, replacement_indices))) != 2:
				raise ValueError("Choose two different cards to replace the piles")
			for source, index in zip(replacement_sources, replacement_indices):
				if not 0 <= index < len(getattr(player, source)):
					raise ValueError(f"Replacement {source} card index out of range")
			replacement_joker_values = replacement_joker_values or (None, None)
			if len(replacement_joker_values) != 2:
				raise ValueError("Choose a value for each Joker replacement")
			for source, index, joker_value in zip(replacement_sources, replacement_indices, replacement_joker_values):
				card = getattr(player, source)[index]
				if card.rank == "Joker" and (joker_value is None or not 2 <= joker_value <= 14):
					raise ValueError("Choose a value from 2 through 14 for each Joker replacement")
		else:
			replacement_joker_values = (None, None)
		card = pile.pop()
		self.pile_owner_history[pile_index].pop()
		self.pile_value_history[pile_index].pop()
		self.destroyed_pile.append(card)
		self.pile_last_player[pile_index] = self.pile_owner_history[pile_index][-1] if pile else None
		self.pile_values[pile_index] = self.pile_value_history[pile_index][-1] if pile else 14
		if spider_net_chain:
			other_index = 1 - pile_index
			self.destroyed_pile.extend(self.discard_piles[other_index])
			self.discard_piles[other_index].clear()
			self.pile_owner_history[other_index].clear()
			self.pile_value_history[other_index].clear()
			self.pile_values[other_index] = 14
			self.pile_last_player[other_index] = None
			replacements = [
				(source, index, getattr(player, source)[index], joker_value)
				for source, index, joker_value in zip(replacement_sources, replacement_indices, replacement_joker_values)
			]
			for source in ("hand", "face_up", "face_down"):
				for index in sorted(
					(index for selected_source, index in zip(replacement_sources, replacement_indices) if selected_source == source),
					reverse=True,
				):
					getattr(player, source).pop(index)
			for target_index, (source, _, replacement, joker_value) in enumerate(replacements):
				self._place_card(
					replacement,
					target_index,
					player_index,
					joker_value,
					source=f"Spider Net Cleave ({source})",
					count_as_play=False,
					check_winner=False,
				)
		state = player.ability_states["Cleave"]
		uses_this_round = state["uses_count"] if state["uses_round"] == self.round_number else 0
		state["uses_count"] = uses_this_round + 1
		state["uses_round"] = self.round_number
		self._record(f"{self.players[player_index].name} used Cleave on discard pile {pile_index + 1}; {card} moved to the destroyed pile.")
		if spider_net_chain:
			self._record(f"Spider Net Cleave destroyed both piles and replaced them with cards from {player.name}'s available zones.")
		self._check_winner()
		return card

	def _place_card(
		self,
		card,
		pile_index,
		player_index,
		joker_value=None,
		source="hand",
		count_as_play=True,
		check_winner=True,
	):
		pile = self.discard_piles[pile_index]
		vow = count_as_play and self.is_vow_card(player_index, card)
		card_value = VALUES["King"] if vow else joker_value if card.rank == "Joker" else VALUES[card.rank]
		is_ten = not vow and (card.rank == "10" or card.rank == "Joker" and joker_value == 10)
		player = self.players[player_index]
		if vow:
			player.vow_card = None
		base_hollow_purple = (
			self.effective_ability(player_index, "Hollow Purple") in ("Hollow Purple", "Max Purple")
			or self.god_rule(player_index) == "Stack destroy"
		)
		hollow_purple = (
			self.effective_ability(player_index, "Hollow Purple") == "Max Purple"
			and count_as_play
			and self.cards_played_this_turn % 3 == 2
		)
		stack_destroy = bool(hollow_purple or (
			base_hollow_purple
			and pile
			and self.pile_last_player[pile_index] == player_index
			and self.pile_values[pile_index] == card_value
		))
		if is_ten or stack_destroy:
			burned_count = len(pile) + 1
			self.destroyed_pile.extend(pile)
			self.destroyed_pile.append(card)
			pile.clear()
			self.pile_owner_history[pile_index].clear()
			self.pile_value_history[pile_index].clear()
			self.pile_values[pile_index] = 14
			self.pile_last_player[pile_index] = None
			if is_ten:
				played_as = "a 10" if card.rank == "10" else "a Joker as 10"
				self._record(f"{self.players[player_index].name} played {played_as} from {source} on discard pile {pile_index + 1}; {burned_count} cards moved to the destroyed pile.")
			else:
				self._record(f"{self.players[player_index].name} triggered Hollow Purple on discard pile {pile_index + 1}; {burned_count} cards moved to the destroyed pile.")
		else:
			pile.append(card)
			self.pile_values[pile_index] = card_value
			self.pile_last_player[pile_index] = player_index
			self.pile_owner_history[pile_index].append(player_index)
			self.pile_value_history[pile_index].append(card_value)
			played_as = f"{card} as a King (Binding Vow)" if vow else _played_card_label(card, joker_value)
			self._record(f"{self.players[player_index].name} played {played_as} from {source} on discard pile {pile_index + 1}.")
		if count_as_play:
			# A destroyed pile frees the player to continue on either pile.
			self.turn_pile_index = None if is_ten or stack_destroy else pile_index
			self.cards_played_this_turn += 1
			if self.enchain_remaining > 0 and self.enchain_player == player_index:
				self.enchain_remaining -= 1
			if card_value == VALUES["Ace"]:
				self._record_limitless_ace(player_index, card, stack_destroy)
			elif not stack_destroy:
				player.ace_streak = 0
			quick_grab_targets = self._quick_grab_targets(player_index, card_value, source, count_as_play)
			if quick_grab_targets:
				self.pending_quick_grabs.append({
					"card": card,
					"pile_index": pile_index,
					"played_by": player_index,
					"zone": "destroyed_pile" if is_ten or stack_destroy else "discard_pile",
					"targets": quick_grab_targets,
					"value": card_value,
				})
		world_ability = self.effective_ability(player_index, "World Cutting Slash")
		if card_value == VALUES["King"] and world_ability in ("World Cutting Slash", "Waffle Cutting Slash"):
			uses = 3 if world_ability == "Waffle Cutting Slash" else 1
			player.pending_world_slashes += uses
			self._record(f"{player.name} played a King; {world_ability} queued {uses} use(s).")
		if check_winner:
			self._check_winner()

	def resolve_world_cutting_slash(
		self,
		player_index,
		zone,
		target_player_index,
		card_owner_index=None,
		card_index=None,
		pile_index=None,
	):
		if player_index != self.current_player:
			raise ValueError("World Cutting Slash can only be resolved on its owner's turn")
		if self.effective_ability(player_index, "World Cutting Slash") not in ("World Cutting Slash", "Waffle Cutting Slash"):
			raise ValueError("World Cutting Slash is not active")
		if self.players[player_index].pending_world_slashes <= 0:
			raise ValueError("No World Cutting Slash uses are pending")
		active_targets = [
			index for index, player in enumerate(self.players)
			if index != player_index and not player.is_eliminated and not self.player_has_finished(index) and not self.player_has_immunity(index)
		]
		if target_player_index is None:
			if active_targets:
				raise ValueError("Choose another player for the Cut Meter")
			target = None
		else:
			if target_player_index not in active_targets:
				if 0 <= target_player_index < len(self.players) and self.player_has_immunity(target_player_index):
					raise ValueError("I-T blocks World Cutting Slash against that player")
				raise ValueError("Choose an active, non-immune opponent for the Cut Meter")
			target = self.players[target_player_index]
		if zone in ("hand", "face_up", "face_down"):
			if card_owner_index is None or not 0 <= card_owner_index < len(self.players):
				raise ValueError("Choose a player who owns the card")
			owner = self.players[card_owner_index]
			if card_owner_index != player_index and self.player_has_immunity(card_owner_index):
				raise ValueError("I-T blocks deletion of that player's cards")
			cards = getattr(owner, zone)
			if not cards:
				raise ValueError("That card zone is empty")
			selected_index = self.rng.randrange(len(cards)) if zone == "face_down" else card_index
			if selected_index is None or not 0 <= selected_index < len(cards):
				raise ValueError("Choose a valid card")
			card = cards.pop(selected_index)
			description = f"{owner.name}'s {zone.replace('_', ' ')}"
			hidden = zone == "face_down"
		elif zone in ("discard_pile", "destroyed_pile"):
			if pile_index not in (0, 1):
				if zone != "destroyed_pile":
					raise ValueError("Choose a discard pile")
			cards = self.destroyed_pile if zone == "destroyed_pile" else self.discard_piles[pile_index]
			if not cards:
				raise ValueError("That card pile is empty")
			if card_index is None or not 0 <= card_index < len(cards):
				raise ValueError("Choose a valid card from the selected pile")
			card = cards.pop(card_index)
			if zone == "discard_pile":
				self.pile_owner_history[pile_index].pop(card_index)
				self.pile_value_history[pile_index].pop(card_index)
				self.pile_last_player[pile_index] = self.pile_owner_history[pile_index][-1] if cards else None
				self.pile_values[pile_index] = self.pile_value_history[pile_index][-1] if cards else 14
				description = f"discard pile {pile_index + 1}"
			else:
				description = "destroyed pile"
			hidden = False
		elif zone == "draw_pile":
			if pile_index not in (0, 1) or not self.draw_piles[pile_index]:
				raise ValueError("That draw pile is empty")
			cards = self.draw_piles[pile_index]
			card = cards.pop(self.rng.randrange(len(cards)))
			description = f"draw pile {pile_index + 1}"
			hidden = True
		else:
			raise ValueError("Invalid World Cutting Slash card zone")
		self.deleted_pile.append(card)
		self.players[player_index].pending_world_slashes -= 1
		self._record(f"{self.players[player_index].name} deleted a card from {description} with World Cutting Slash.")
		if target is not None:
			if self.player_has_finished(target_player_index):
				self._record(f"{target.name} already finished, so the Cut Meter cannot affect them.")
				target.cut_meter = min(target.cut_meter, 8)
				self._check_winner()
				return card, hidden, target.cut_meter
			target.cut_meter += 1
			self._record(f"{target.name}'s Cut Meter increased to {target.cut_meter}.")
			if target.cut_meter >= 9:
				target.is_eliminated = True
				self.deleted_pile.extend(target.hand)
				self.deleted_pile.extend(target.face_up)
				self.deleted_pile.extend(target.face_down)
				target.hand.clear()
				target.face_up.clear()
				target.face_down.clear()
				self._record(f"{target.name} was eliminated by Cut Meter and will tie for last place.")
		self._check_winner()
		return card, hidden, target.cut_meter if target is not None else None

	def resolve_bot_world_slashes(self, player_index):
		player = self.players[player_index]
		while player.pending_world_slashes and self.winner is None and self.current_player == player_index:
			choices = []
			for owner_index, owner in enumerate(self.players):
				if owner.is_eliminated or owner_index != player_index and self.player_has_immunity(owner_index):
					continue
				for zone in ("hand", "face_up", "face_down"):
					if getattr(owner, zone):
						choices.append((zone, owner_index, None, None))
			for pile_index, pile in enumerate(self.discard_piles):
				if pile:
					choices.append(("discard_pile", None, None, pile_index))
			for pile_index, pile in enumerate(self.draw_piles):
				if pile:
					choices.append(("draw_pile", None, None, pile_index))
			if not choices:
				player.pending_world_slashes = 0
				return
			zone, owner_index, card_index, pile_index = self.rng.choice(choices)
			if zone in ("hand", "face_up"):
				card_index = self.rng.randrange(len(getattr(self.players[owner_index], zone)))
			elif zone == "discard_pile":
				card_index = self.rng.randrange(len(self.discard_piles[pile_index]))
			active_targets = [
				index for index in range(len(self.players))
				if index != player_index and not self.players[index].is_eliminated and not self.player_has_finished(index) and not self.player_has_immunity(index)
			]
			target_index = self.rng.choice(active_targets) if active_targets else None
			self.resolve_world_cutting_slash(
				player_index,
				zone,
				target_index,
				card_owner_index=owner_index,
				card_index=card_index,
				pile_index=pile_index,
			)

	def _draw_to_three(self, player):
		drawn_cards = []
		while len(player.hand) < 3:
			available = [i for i, pile in enumerate(self.draw_piles) if pile]
			if not available:
				break
			player_index = next(i for i, p in enumerate(self.players) if p is player)
			if self.effective_ability(player_index, "Six Eyes") == "Mastered Six Eyes":
				index, card = self._mastered_draw(player_index)
			else:
				index = self.rng.choice(available)
				card = self.draw_piles[index].pop()
			player.hand.append(card)
			drawn_cards.append(card)
			self._record(f"{player.name} drew {card} from draw pile {index + 1}; hand now has {len(player.hand)} cards.")
		return drawn_cards

	def refill_player_hand(self, player_index):
		if player_index != self.current_player:
			raise ValueError("Only the current player can refill their hand")
		if self.player_has_finished(player_index):
			return []
		return self._draw_to_three(self.players[player_index])

	def _check_winner(self):
		if any(player.pending_world_slashes or player.pending_limitless_effects for player in self.players) or self.pending_quick_grabs:
			return
		if any(self.draw_piles):
			return
		finished_players = {result["player_index"] for result in self.finish_order}
		for index, player in enumerate(self.players):
			if index not in finished_players and not player.is_eliminated and not player.hand and not player.face_up and not player.face_down:
				rank = len(self.finish_order) + 1
				self.finish_order.append({
					"player_index": index,
					"rank": rank,
					"round": self.round_number,
					"turn": self.turn_number,
					"status": "finished",
				})
				self._record(f"{player.name} finished in rank {rank} at round {self.round_number}, turn {self.turn_number}.")
		finished_players = {result["player_index"] for result in self.finish_order}
		remaining = [
			index for index, player in enumerate(self.players)
			if index not in finished_players and not player.is_eliminated
		]
		eliminated = [index for index, player in enumerate(self.players) if player.is_eliminated and index not in finished_players]
		if len(remaining) <= 1:
			last_rank = len(self.finish_order) + 1
			if remaining:
				index = remaining[0]
				self.last_remaining_player = index
				self.finish_order.append({
					"player_index": index,
					"rank": last_rank,
					"round": self.round_number,
					"turn": self.turn_number,
					"status": "last remaining",
				})
				self._record(f"{self.players[index].name} was last remaining in rank {last_rank} at round {self.round_number}, turn {self.turn_number}.")
			for index in eliminated:
				self.finish_order.append({
					"player_index": index,
					"rank": last_rank,
					"round": self.round_number,
					"turn": self.turn_number,
					"status": "last place (Cut Meter)",
				})
				self._record(f"{self.players[index].name} tied for last place at rank {last_rank} after Cut Meter elimination.")
			self.winner = self.finish_order[0]["player_index"] if self.finish_order else (remaining[0] if remaining else None)
			self._record("Game finished; final standings recorded.")

	def player_has_finished(self, player_index):
		player = self.players[player_index]
		if player.is_eliminated or any(result["player_index"] == player_index for result in self.finish_order):
			return True
		return not any(self.draw_piles) and not player.hand and not player.face_up and not player.face_down

	def play(self, player_index, source, card_index, pile_index, joker_value=None):
		"""Play from hand, or from face-up cards after hand and draws run out."""
		self.last_drawn_cards = []
		if player_index != self.current_player:
			raise ValueError("It is not this player's turn")
		if source not in ("hand", "face_up") or pile_index not in (0, 1):
			raise ValueError("Invalid source or discard pile")
		player = self.players[player_index]
		if source == "hand":
			self.last_drawn_cards.extend(self.refill_player_hand(player_index))
		if source == "face_up" and (player.hand or any(self.draw_piles)):
			raise ValueError("Face-up cards cannot yet be played")
		cards = player.hand if source == "hand" else player.face_up
		if not 0 <= card_index < len(cards):
			raise ValueError("Card index out of range")
		card = cards[card_index]
		first_move = self.cards_played_this_turn == 0
		if card.rank == "Joker" and (joker_value is None or not 2 <= joker_value <= 14):
			raise ValueError("Choose a joker value from 2 through 14")
		if not self.can_play(card, pile_index, joker_value):
			top = self.discard_piles[pile_index][-1] if self.discard_piles[pile_index] else None
			penalty = "both piles picked up" if first_move else "piles retained"
			self._record(f"{player.name} attempted illegal {card} on discard pile {pile_index + 1} (top: {top if top else 'empty'}); turn forfeited, {penalty}.")
			if first_move:
				self.take_discard_piles(player_index)
			return None
		cards.pop(card_index)
		self._place_card(card, pile_index, player_index, joker_value, source)
		if source == "hand":
			self.last_drawn_cards.extend(self._draw_to_three(player))
		return card

	def take_discard_pile(self, player_index, pile_index):
		if player_index != self.current_player:
			raise ValueError("It is not this player's turn")
		if pile_index not in (0, 1):
			raise ValueError("Invalid discard pile")
		self.take_discard_piles(player_index)

	def take_discard_piles(self, player_index):
		if player_index != self.current_player:
			raise ValueError("It is not this player's turn")
		player = self.players[player_index]
		picked_up = sum(len(pile) for pile in self.discard_piles)
		for pile_index, pile in enumerate(self.discard_piles):
			player.hand.extend(pile)
			pile.clear()
			self.pile_values[pile_index] = 14
			self.pile_last_player[pile_index] = None
			self.pile_owner_history[pile_index].clear()
			self.pile_value_history[pile_index].clear()
		self._record(f"{player.name} picked up both discard piles ({picked_up} cards).")
		self.domain_shatter(player_index, "picked up the piles")

	def play_face_down(self, player_index, card_index, pile_index, joker_value=None):
		if player_index != self.current_player:
			raise ValueError("It is not this player's turn")
		if pile_index not in (0, 1):
			raise ValueError("Invalid discard pile")
		player = self.players[player_index]
		if player.hand or player.face_up or any(self.draw_piles):
			raise ValueError("Face-down cards cannot yet be played")
		if not 0 <= card_index < len(player.face_down):
			raise ValueError("Face-down card index out of range")
		card = player.face_down.pop(card_index)
		if card.rank == "Joker" and (joker_value is None or not 2 <= joker_value <= 14):
			player.face_down.append(card)
			raise ValueError("Choose a joker value from 2 through 14")
		if not self.can_play(card, pile_index, joker_value):
			player.hand.append(card)
			self._record(f"{player.name} revealed illegal {card} on discard pile {pile_index + 1}; turn forfeited, both piles picked up.")
			self.take_discard_piles(player_index)
			return card, False
		self._place_card(card, pile_index, player_index, joker_value, "face-down")
		return card, True

	def end_turn(self):
		"""Advance the turn; hand refills happen immediately after plays."""
		if self.pending_quick_grabs:
			raise ValueError("Resolve Quick Grab before ending the turn")
		ending_player = self.players[self.current_player]
		self._record(f"{ending_player.name} ended their turn.")
		if self.enchain_return is not None:
			saved = self.enchain_return
			self.enchain_return = None
			self.enchain_player = None
			self.enchain_remaining = 0
			self.current_player = saved["current_player"]
			self.cards_played_this_turn = saved["cards_played"]
			self.turn_pile_index = saved["turn_pile_index"]
			self._record(f"Enchain finished; it is {self.players[self.current_player].name}'s turn again.")
			return
		self.cards_played_this_turn = 0
		self.turn_pile_index = None
		self.enchain_player = None
		self.enchain_remaining = 0
		for _ in self.players:
			self.current_player = (self.current_player + 1) % len(self.players)
			self.turn_number += 1
			if self.current_player == 0:
				self.round_number += 1
				self.domain_round_end()
			if not self.player_has_finished(self.current_player):
				break
			self._record(f"{self.players[self.current_player].name} is finished and skips their turn.")
		self._record(f"It is now {self.players[self.current_player].name}'s turn.")
		self.six_eyes_scan(self.current_player)


def _ask_index(prompt, choices):
	while True:
		try:
			choice = int(input(prompt)) - 1
		except ValueError:
			print("Enter one of the listed numbers.")
			continue
		if choice in choices:
			return choice
		print("That choice is not available.")


def _ask_joker_value():
	while True:
		try:
			value = int(input("Choose the Joker's value (2-14): "))
		except ValueError:
			print("Enter a number from 2 through 14.")
			continue
		if 2 <= value <= 14:
			return value
		print("Enter a number from 2 through 14.")


def _choose_face_up_cards(game, player_index):
	player = game.players[player_index]
	if player.is_bot:
		best_cards = sorted(
			range(len(player.hand)),
			key=lambda index: 15 if player.hand[index].rank == "Joker" else VALUES[player.hand[index].rank],
			reverse=True,
		)[:3]
		game.choose_face_up(player_index, best_cards)
		print(f"{player.name} is ready.")
		return

	print("Choose 3 cards to keep face up for later.")
	for index, card in enumerate(player.hand, start=1):
		print(f"  {index}. {card}")
	while True:
		try:
			indices = [int(value) - 1 for value in input("Card numbers (example: 1 3 6): ").replace(",", " ").split()]
			game.choose_face_up(player_index, indices)
			return
		except ValueError as error:
			print(error or "Enter three different card numbers.")


def _display_table(game):
	player = game.players[game.current_player]
	print(f"\nRound {game.round_number} | Turn {game.turn_number} | {player.name}")
	print("Draw piles: " + " / ".join(str(len(pile)) for pile in game.draw_piles))
	for index, pile in enumerate(game.discard_piles, start=1):
		top = _played_card_label(pile[-1], game.pile_values[index - 1]) if pile else "empty"
		print(f"Discard {index}: {top} ({len(pile)} cards)")
	if not player.is_bot:
		print("Your hand: " + (", ".join(str(card) for card in player.hand) or "empty"))
		print("Your face-up cards: " + (", ".join(str(card) for card in player.face_up) or "empty"))


def _played_card_label(card, joker_value=None):
	if card.rank == "Joker" and joker_value is not None:
		return f"Joker as {RANKS[joker_value - 2]}"
	return str(card)


def _current_source(game, player):
	if player.hand:
		return "hand", player.hand
	if any(game.draw_piles):
		return None, []
	if player.face_up:
		return "face_up", player.face_up
	if player.face_down:
		return "face_down", player.face_down
	return None, []


def _legal_options(game, cards):
	return [
		(card_index, pile_index)
		for card_index, card in enumerate(cards)
		for pile_index in range(2)
		if game.can_play(card, pile_index)
	]


def _resolve_console_world_slashes(game, player_index):
	while game.players[player_index].pending_world_slashes and game.winner is None:
		choices = []
		for owner_index, owner in enumerate(game.players):
			if owner.is_eliminated or owner_index != player_index and game.player_has_immunity(owner_index):
				continue
			for zone, label in (("hand", "hand"), ("face_up", "face-up"), ("face_down", "face-down, random card")):
				count = len(getattr(owner, zone))
				if count:
					choices.append((f"{owner.name}'s {label} ({count})", zone, owner_index, None))
		for pile_index, pile in enumerate(game.discard_piles):
			if pile:
				choices.append((f"Discard pile {pile_index + 1} ({len(pile)})", "discard_pile", None, pile_index))
		if game.destroyed_pile:
			choices.append((f"Destroyed pile ({len(game.destroyed_pile)})", "destroyed_pile", None, None))
		for pile_index, pile in enumerate(game.draw_piles):
			if pile:
				choices.append((f"Draw pile {pile_index + 1}, random card ({len(pile)})", "draw_pile", None, pile_index))
		if not choices:
			game.players[player_index].pending_world_slashes = 0
			return
		print("Choose a card or pile to delete:")
		for index, (label, _, _, _) in enumerate(choices, start=1):
			print(f"  {index}. {label}")
		choice_index = _ask_index("Choice: ", range(len(choices)))
		_, zone, owner_index, pile_index = choices[choice_index]
		card_index = None
		if zone in ("hand", "face_up", "discard_pile", "destroyed_pile"):
			if zone == "discard_pile":
				cards = game.discard_piles[pile_index]
			elif zone == "destroyed_pile":
				cards = game.destroyed_pile
			else:
				cards = getattr(game.players[owner_index], zone)
			for index, card in enumerate(cards, start=1):
				print(f"  {index}. {card}")
			card_index = _ask_index("Card to delete: ", range(len(cards)))
		targets = [
			index for index in range(len(game.players))
			if index != player_index and not game.players[index].is_eliminated and not game.player_has_finished(index) and not game.player_has_immunity(index)
		]
		target_index = None
		if targets:
			for index, target in enumerate(targets, start=1):
				print(f"  {index}. {game.players[target].name} (Cut Meter {game.players[target].cut_meter}/9)")
			target_index = targets[_ask_index("Player to increase Cut Meter: ", range(len(targets)))]
		card, hidden, meter = game.resolve_world_cutting_slash(
			player_index,
			zone,
			target_index,
			card_owner_index=owner_index,
			card_index=card_index,
			pile_index=pile_index,
		)
		print(f"World Cutting Slash deleted {'a hidden card' if hidden else card}.")
		if target_index is not None:
			print(f"{game.players[target_index].name}'s Cut Meter is {meter}/9.")


def _bot_legal_options(game, cards):
	return [
		(card_index, pile_index)
		for card_index, card in enumerate(cards)
		for pile_index in range(2)
		if game.can_play(card, pile_index, joker_value=14 if card.rank == "Joker" else None)
	]


def _bot_choose_play(game, cards, options):
	if game.cards_played_this_turn == 0:
		lowest_pile = min(
			range(2),
			key=lambda index: (game.pile_values[index] if game.discard_piles[index] else 0, len(game.discard_piles[index])),
		)
		options_on_lowest_pile = [option for option in options if option[1] == lowest_pile]
		if options_on_lowest_pile:
			options = options_on_lowest_pile

	def priority(card):
		if card.rank == "2":
			return 1, 0
		if card.rank == "10":
			return 1, 1
		return 0, 14 if card.rank == "Joker" else VALUES[card.rank]

	return min(
		options,
		key=lambda option: (
			*priority(cards[option[0]]),
			game.pile_values[option[1]] if game.discard_piles[option[1]] else 0,
			len(game.discard_piles[option[1]]),
		),
	)


def _finish_turn(game):
	if game.winner is None:
		game.end_turn()


def _human_turn(game):
	player_index = game.current_player
	player = game.players[player_index]
	while game.winner is None:
		game.refill_player_hand(player_index)
		source, cards = _current_source(game, player)
		if source is None:
			_finish_turn(game)
			return

		if source == "face_down":
			print("You must reveal a face-down card.")
			card_index = _ask_index("Choose a hidden card (1-3): ", range(len(cards)))
			pile_index = _ask_index("Choose discard pile (1 or 2): ", range(2))
			card, played = game.play_face_down(player_index, card_index, pile_index, joker_value=14)
			if player.pending_world_slashes and game.winner is None:
				_resolve_console_world_slashes(game, player_index)
			if player.pending_limitless_effects and game.winner is None:
				game.resolve_bot_limitless_effects(player_index)
			if game.pending_quick_grabs:
				game.resolve_bot_quick_grabs()
			if played:
				print(f"You revealed and played {_played_card_label(card, 14)}.")
			else:
				print(f"You revealed {card} and picked up both discard piles.")
			_finish_turn(game)
			return

		options = _legal_options(game, cards)
		if not options:
			if game.cards_played_this_turn == 0:
				print("You have no legal play and must pick up both discard piles.")
				game.take_discard_piles(player_index)
			else:
				print("You have no legal follow-up play; your turn ends with the piles unchanged.")
			_finish_turn(game)
			return

		print(f"Choose a {source.replace('_', '-')} card:")
		for index, card in enumerate(cards, start=1):
			print(f"  {index}. {card}")
		card_index = _ask_index("Card number: ", range(len(cards)))
		legal_piles = [pile for card, pile in options if card == card_index]
		for index, pile_index in enumerate(range(2)):
			top = str(game.discard_piles[pile_index][-1]) if game.discard_piles[pile_index] else "empty"
			status = "legal" if pile_index in legal_piles else "illegal; picks up both piles" if game.cards_played_this_turn == 0 else "illegal; ends turn"
			print(f"  {index + 1}. Discard pile {pile_index + 1} (top: {top}; {status})")
		pile_index = _ask_index("Pile choice: ", range(2))
		card = cards[card_index]
		joker_value = _ask_joker_value() if card.rank == "Joker" and game.can_play(card, pile_index) else None
		played = game.play(player_index, source, card_index, pile_index, joker_value)
		if played is None:
			penalty = "you picked up both discard piles" if game.cards_played_this_turn == 0 else "the piles were left unchanged"
			print(f"That play is illegal; {penalty}, and your turn ended.")
			_finish_turn(game)
			return
		print(f"You played {_played_card_label(card, joker_value)} on discard pile {pile_index + 1}.")
		if player.pending_world_slashes and game.winner is None:
			_resolve_console_world_slashes(game, player_index)
		if player.pending_limitless_effects and game.winner is None:
			game.resolve_bot_limitless_effects(player_index)
		if game.pending_quick_grabs:
			game.resolve_bot_quick_grabs()
		if game.winner is not None:
			return
		if game.last_drawn_cards:
			print("You drew: " + ", ".join(str(card) for card in game.last_drawn_cards))
		elif source == "hand" and len(player.hand) < 3:
			print("No cards drawn; the draw piles are empty.")
		if input("Play another card this turn? [y/N]: ").strip().lower() != "y":
			_finish_turn(game)
			return


def _bot_turn(game):
	player_index = game.current_player
	player = game.players[player_index]
	while game.winner is None and game.current_player == player_index:
		game.refill_player_hand(player_index)
		source, cards = _current_source(game, player)
		if source is None:
			_finish_turn(game)
			return

		if source == "face_down":
			card_index = game.rng.randrange(len(cards))
			card = cards[card_index]
			joker_value = 14 if card.rank == "Joker" else None
			legal_piles = [
				index for index in range(2)
				if game.can_play(card, index, joker_value=joker_value)
			]
			if legal_piles:
				pile_index = min(
					legal_piles,
					key=lambda index: (game.pile_values[index] if game.discard_piles[index] else 0, len(game.discard_piles[index])),
				)
				card, played = game.play_face_down(player_index, card_index, pile_index, joker_value=14)
				if played:
					print(f"{player.name} reveals and plays {_played_card_label(card, 14)}.")
				else:
					print(f"{player.name} reveals {card} and picks up both discard piles.")
			else:
				pile_index = min(range(2), key=lambda index: len(game.discard_piles[index]))
				card, _ = game.play_face_down(player_index, card_index, pile_index, joker_value=14)
				print(f"{player.name} reveals {card} and picks up both discard piles.")
			if player.pending_world_slashes and game.winner is None:
				game.resolve_bot_world_slashes(player_index)
			if player.pending_limitless_effects and game.winner is None:
				game.resolve_bot_limitless_effects(player_index)
			if game.pending_quick_grabs:
				game.resolve_bot_quick_grabs()
			_finish_turn(game)
			return

		options = _bot_legal_options(game, cards)
		if not options:
			if game.cards_played_this_turn == 0:
				game.take_discard_piles(player_index)
				print(f"{player.name} has no legal play and picks up both discard piles.")
			else:
				print(f"{player.name} has no legal follow-up play.")
			_finish_turn(game)
			return

		card_index, pile_index = _bot_choose_play(game, cards, options)
		joker_value = 14 if cards[card_index].rank == "Joker" else None
		card = game.play(player_index, source, card_index, pile_index, joker_value=joker_value)
		if card is None:
			_finish_turn(game)
			return
		print(f"{player.name} plays {_played_card_label(card, joker_value)} on discard pile {pile_index + 1}.")
		if player.pending_world_slashes and game.winner is None:
			game.resolve_bot_world_slashes(player_index)
		if player.pending_limitless_effects and game.winner is None:
			game.resolve_bot_limitless_effects(player_index)
		if game.pending_quick_grabs:
			game.resolve_bot_quick_grabs()


class PalaceApp:
	def __init__(self, root):
		self.root = root
		self.root.title("Palace")
		self.root.geometry("1040x720")
		self.root.minsize(780, 580)
		self.root.configure(bg="#173b32")
		self.style = ttk.Style(root)
		self.style.configure("App.TFrame", background="#173b32")
		self.style.configure("Title.TLabel", background="#173b32", foreground="#f4eddc", font=("Georgia", 24, "bold"))
		self.style.configure("Info.TLabel", background="#173b32", foreground="#d8e2d6", font=("Segoe UI", 11))
		self.style.configure("Section.TLabel", background="#173b32", foreground="#f4eddc", font=("Segoe UI", 13, "bold"))
		self.style.configure("Action.TButton", font=("Segoe UI", 11, "bold"), padding=(16, 10))
		self.selected_cards = set()
		self.selected_card = None
		self.selected_pile = None
		self.human_has_played = False
		self.setup_complete = False
		self.fast_forward = False
		self.game_started = False
		self.selected_character = None
		self.game = None
		self.admin_unlocked = False
		self.setup_player = None
		self.setup_queue = []
		self.last_human = 0
		self.device_holder = None
		self.player_type_vars = []
		self.player_character_vars = []
		self.player_count_var = tk.IntVar(value=DEFAULT_PLAYER_COUNT)
		self.deck_count_var = tk.IntVar(value=DEFAULT_DECK_COUNT)
		self.joker_count_var = tk.IntVar(value=DEFAULT_JOKER_COUNT)
		container = self._make_scrollable_container(root)
		header = ttk.Frame(container, style="App.TFrame")
		header.pack(fill="x", pady=(0, 18))
		ttk.Label(header, text="PALACE", style="Title.TLabel").pack(side="left")
		self.characters_button = ttk.Button(header, text="Characters", command=self._show_character_reference)
		self.characters_button.pack(side="right", padx=4)
		self.settings_button = ttk.Button(header, text="Settings", command=self._show_settings)
		self.settings_button.pack(side="right", padx=4)
		self.action_log_button = ttk.Button(header, text="Action log", command=self._show_action_log, state="disabled")
		self.action_log_button.pack(side="right", padx=4)
		self.new_game_button = ttk.Button(header, text="New game", command=self._reset_game, state="disabled")
		self.new_game_button.pack(side="right", padx=4)

		self.selection_frame = ttk.Frame(container, style="App.TFrame")
		self.selection_frame.pack(fill="both", expand=True)
		self.start_tabs = ttk.Notebook(self.selection_frame)
		self.start_tabs.pack(fill="both", expand=True)
		characters_tab = ttk.Frame(self.start_tabs, style="App.TFrame", padding=16)
		rules_tab = ttk.Frame(self.start_tabs, style="App.TFrame", padding=16)
		self.start_tabs.add(characters_tab, text="Characters")
		setup_tab = ttk.Frame(self.start_tabs, style="App.TFrame", padding=16)
		self.start_tabs.add(setup_tab, text="Game setup")
		self.start_tabs.add(rules_tab, text="Multi-use rules")
		self._build_setup_tab(setup_tab)
		ttk.Label(characters_tab, text="Choose your character", style="Section.TLabel").pack(anchor="w", pady=(0, 14))
		selection_body = ttk.Frame(characters_tab, style="App.TFrame")
		selection_body.pack(fill="both", expand=True)
		self.character_list = tk.Listbox(
			selection_body,
			width=24,
			height=8,
			font=("Georgia", 14, "bold"),
			bg="#f4eddc",
			fg="#19362f",
			selectbackground="#d7b66d",
			selectforeground="#19362f",
			relief="flat",
			exportselection=False,
		)
		self.character_list.pack(side="left", fill="y", padx=(0, 20))
		for character_name in CHARACTERS:
			self.character_list.insert("end", character_name)
		self.character_list.bind("<<ListboxSelect>>", self._preview_character)
		details_frame = ttk.Frame(selection_body, style="App.TFrame")
		details_frame.pack(side="left", fill="both", expand=True)
		details_scroll = ttk.Scrollbar(details_frame, orient="vertical")
		details_scroll.pack(side="right", fill="y")
		self.character_details = tk.Text(
			details_frame,
			wrap="word",
			height=18,
			font=("Segoe UI", 11),
			bg=ttk.Style().lookup("App.TFrame", "background") or "#f4eddc",
			relief="flat",
			borderwidth=0,
			highlightthickness=0,
			cursor="arrow",
			yscrollcommand=details_scroll.set,
		)
		details_scroll.config(command=self.character_details.yview)
		self.character_details.pack(side="left", fill="both", expand=True)
		self.character_details.tag_configure("rule", underline=True, foreground="#1a5fb4")
		self.character_details.tag_configure("heading", font=("Segoe UI", 12, "bold"))
		self.character_details.tag_bind("rule", "<Enter>", lambda _e: self.character_details.config(cursor="hand2"))
		self.character_details.tag_bind("rule", "<Leave>", lambda _e: self.character_details.config(cursor="arrow"))
		self.character_details.config(state="disabled")
		self.start_game_button = ttk.Button(
			characters_tab,
			text="Select character and start",
			style="Action.TButton",
			command=self._start_selected_character,
		)
		self.start_game_button.pack(anchor="w", pady=(18, 0))
		for rule_name, description in MULTI_USE_RULES.items():
			ttk.Label(rules_tab, text=rule_name, style="Section.TLabel").pack(anchor="w", pady=(0, 4))
			ttk.Label(rules_tab, text=description, style="Info.TLabel", wraplength=880, justify="left").pack(anchor="w", pady=(0, 18))
		self.character_list.selection_set(0)
		self._preview_character()

		self.game_frame = ttk.Frame(container, style="App.TFrame")
		self.status_label = ttk.Label(self.game_frame, style="Info.TLabel", wraplength=920)
		self.status_label.pack(anchor="w", pady=(0, 16))
		self.players_title = ttk.Label(self.game_frame, text="Players", style="Section.TLabel")
		self.players_title.pack(anchor="w", pady=(0, 6))
		self.players_frame = ttk.Frame(self.game_frame, style="App.TFrame")
		self.players_frame.pack(fill="x", pady=(0, 12))
		self.piles_frame = ttk.Frame(self.game_frame, style="App.TFrame")
		self.piles_frame.pack(fill="x", pady=(0, 18))
		self.cards_title = ttk.Label(self.game_frame, style="Section.TLabel")
		self.cards_title.pack(anchor="w", pady=(0, 8))
		self.cards_frame = ttk.Frame(self.game_frame, style="App.TFrame")
		self.cards_frame.pack(fill="both", expand=True, anchor="n")
		self.controls = ttk.Frame(self.game_frame, style="App.TFrame")
		self.controls.pack(fill="x", pady=(16, 0))
		self.play_button = ttk.Button(self.controls, text="Play selected card", style="Action.TButton", command=self._play_selected)
		self.play_button.pack(side="left")
		self.end_button = ttk.Button(self.controls, text="End turn", command=self._end_human_turn)
		self.end_button.pack(side="left", padx=10)
		self.ability_button = ttk.Button(self.controls, text="Use ability", command=self._use_character_ability)
		self.world_ability_label = ttk.Label(self.controls, style="Info.TLabel")
		self.hollow_ability_label = ttk.Label(self.controls, style="Info.TLabel")
		self.world_slash_button = ttk.Button(self.controls, text="Resolve World Cutting Slash", command=self._resolve_pending_world_slashes)
		self.limitless_button = ttk.Button(self.controls, text="Resolve Limitless effect", command=self._resolve_pending_limitless_effects)
		self.quick_grab_button = ttk.Button(self.controls, text="Quick Grab", command=self._quick_grab_pending_ace)
		self.decline_quick_grab_button = ttk.Button(self.controls, text="Decline", command=self._decline_quick_grab)
		self.evolve_button = ttk.Button(self.controls, text="Evolve ability", style="Action.TButton", command=self._evolve_selected_ability)
		self.enchain_button = ttk.Button(self.controls, text="Enchain", command=self._use_enchain)
		self.vow_button = ttk.Button(self.controls, text="Binding Vow", command=self._use_binding_vow)
		self.vow_label = ttk.Label(self.controls, style="Info.TLabel")
		self.god_button = ttk.Button(self.controls, text="God of Jujutsu", command=self._use_god_of_jujutsu)
		self.god_label = ttk.Label(self.controls, style="Info.TLabel")
		self.swap_button = ttk.Button(self.controls, text="Card Swapping", command=self._use_card_swapping)
		self.rescue_button = ttk.Button(self.controls, text="Rescue Draw", command=self._use_rescue_draw)
		self.six_eyes_button = ttk.Button(self.controls, text="Six Eyes", command=self._use_six_eyes)
		self.full_hand_button = ttk.Button(self.controls, text="Full Hand", command=self._use_full_hand)
		self.domain_button = ttk.Button(self.controls, text="Domain", command=self._use_domain)
		self.simple_button = ttk.Button(self.controls, text="Simple Domain", command=self._use_simple_domain)
		self.skip_button = ttk.Button(self.controls, text="Skip to results", command=self._skip_to_results)

	def _preview_character(self, _event=None):
		selection = self.character_list.curselection()
		if not selection:
			return
		character_name = self.character_list.get(selection[0])
		box = self.character_details
		box.config(state="normal")
		box.delete("1.0", "end")
		box.insert("end", f"{character_name}\n\n", "heading")

		def add_block(title, description, rules):
			box.insert("end", f"{title}\n", "heading")
			start = box.index("end-1c")
			box.insert("end", description)
			lowered = description.lower()
			for rule_name in rules:
				needle = rule_name.lower()
				position = lowered.find(needle)
				while position != -1:
					end = position + len(needle)
					tag = f"rule_{rule_name}_{position}"
					box.tag_add("rule", f"{start}+{position}c", f"{start}+{end}c")
					box.tag_add(tag, f"{start}+{position}c", f"{start}+{end}c")
					box.tag_bind(tag, "<Button-1>", lambda _e, name=rule_name: self._show_rule(name))
					position = lowered.find(needle, end)
			box.insert("end", "\n\n")

		tracks = character_ability_tracks(character_name)
		for index, track in enumerate(tracks):
			if index:
				box.insert("end", "--------------------\n\n")
			add_block(track["ability"], track["description"], track.get("rules", ()))
			if "evolution" in track:
				evolution = track["evolution"]
				add_block(f"Evolution: {evolution['ability']}", evolution["description"], evolution.get("rules", ()))
		box.insert("end", "Each evolution requires a Joker in hand before you play any cards and ends your turn.\nUnderlined rule names can be clicked to read what they do.")
		box.config(state="disabled")

	def _show_rule(self, rule_name):
		messagebox.showinfo(rule_name, MULTI_USE_RULES[rule_name])

	def _make_scrollable_container(self, root):
		outer = ttk.Frame(root)
		outer.pack(fill="both", expand=True)
		background = ttk.Style().lookup("App.TFrame", "background") or root.cget("bg")
		canvas = tk.Canvas(outer, highlightthickness=0, bg=background)
		scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
		canvas.configure(yscrollcommand=scrollbar.set)
		scrollbar.pack(side="right", fill="y")
		canvas.pack(side="left", fill="both", expand=True)
		container = ttk.Frame(canvas, style="App.TFrame", padding=24)
		window = canvas.create_window((0, 0), window=container, anchor="nw")

		def resize(_event=None):
			height = max(canvas.winfo_height(), container.winfo_reqheight())
			canvas.itemconfigure(window, width=canvas.winfo_width(), height=height)
			canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), height))

		canvas.bind("<Configure>", resize)
		container.bind("<Configure>", resize)

		def on_wheel(event):
			widget = event.widget
			if not isinstance(widget, tk.Misc) or widget.winfo_toplevel() is not root:
				return
			if isinstance(widget, (tk.Text, tk.Listbox)):
				return
			if container.winfo_reqheight() > canvas.winfo_height():
				canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

		root.bind_all("<MouseWheel>", on_wheel)
		return container

	def _build_setup_tab(self, tab):
		ttk.Label(tab, text="Game setup", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
		options = ttk.Frame(tab, style="App.TFrame")
		options.pack(anchor="w", pady=(0, 10))
		for column, (label, variable, low, high) in enumerate((
			("Players", self.player_count_var, 2, MAX_PLAYERS),
			("Decks (52 cards each)", self.deck_count_var, 1, 10),
			("Jokers (total)", self.joker_count_var, 0, 40),
		)):
			ttk.Label(options, text=label, style="Info.TLabel").grid(row=0, column=column, sticky="w", padx=(0, 18))
			ttk.Spinbox(options, from_=low, to=high, textvariable=variable, width=8).grid(row=1, column=column, sticky="w", padx=(0, 18))
		self.player_count_var.trace_add("write", lambda *_: self._rebuild_player_rows())
		self.player_rows_frame = ttk.Frame(tab, style="App.TFrame")
		self.player_rows_frame.pack(anchor="w", fill="x", pady=(0, 10))
		buttons = ttk.Frame(tab, style="App.TFrame")
		buttons.pack(anchor="w")
		ttk.Button(buttons, text="Restore defaults", command=self._restore_setup_defaults).pack(side="left", padx=(0, 10))
		ttk.Button(buttons, text="Start game", style="Action.TButton", command=self._start_selected_character).pack(side="left")
		self._rebuild_player_rows()

	def _restore_setup_defaults(self):
		self.deck_count_var.set(DEFAULT_DECK_COUNT)
		self.joker_count_var.set(DEFAULT_JOKER_COUNT)
		self.player_type_vars = []
		self.player_character_vars = []
		self.player_count_var.set(DEFAULT_PLAYER_COUNT)
		self._rebuild_player_rows()

	def _rebuild_player_rows(self):
		try:
			count = max(1, min(MAX_PLAYERS, self.player_count_var.get()))
		except tk.TclError:
			return
		for widget in self.player_rows_frame.winfo_children():
			widget.destroy()
		del self.player_type_vars[count:]
		del self.player_character_vars[count:]
		while len(self.player_type_vars) < count:
			index = len(self.player_type_vars)
			self.player_type_vars.append(tk.StringVar(value="Human" if index == 0 else "Bot"))
			self.player_character_vars.append(tk.StringVar(value=RANDOM_CHARACTER))
		for index in range(count):
			row = ttk.Frame(self.player_rows_frame, style="App.TFrame")
			row.grid(row=index % 6, column=index // 6, sticky="w", padx=(0, 24), pady=2)
			ttk.Label(row, text=f"Player {index + 1}", style="Info.TLabel", width=9).pack(side="left")
			ttk.Combobox(row, textvariable=self.player_type_vars[index], values=("Human", "Bot"), state="readonly", width=7).pack(side="left", padx=(0, 6))
			if index == 0:
				ttk.Label(row, text="Character: Characters tab", style="Info.TLabel").pack(side="left")
			else:
				ttk.Combobox(
					row,
					textvariable=self.player_character_vars[index],
					values=(RANDOM_CHARACTER, *CHARACTERS),
					state="readonly",
					width=12,
				).pack(side="left")

	def _read_game_settings(self):
		try:
			player_count = self.player_count_var.get()
			deck_count = self.deck_count_var.get()
			joker_count = self.joker_count_var.get()
		except tk.TclError:
			raise ValueError("Players, decks and jokers must be whole numbers")
		if not 2 <= player_count <= MAX_PLAYERS:
			raise ValueError(f"Players must be between 2 and {MAX_PLAYERS}")
		validate_game_settings(player_count, deck_count, joker_count)
		bot_flags = [variable.get() == "Bot" for variable in self.player_type_vars[:player_count]]
		if all(bot_flags):
			raise ValueError("At least one player must be a human")
		characters = [self.selected_character] + [
			None if variable.get() == RANDOM_CHARACTER else variable.get()
			for variable in self.player_character_vars[1:player_count]
		]
		return {"bot_flags": bot_flags, "characters": characters, "deck_count": deck_count, "joker_count": joker_count}

	def _start_selected_character(self):
		selection = self.character_list.curselection()
		if not selection:
			return
		self.selected_character = self.character_list.get(selection[0])
		try:
			settings = self._read_game_settings()
			self._new_game(settings)
		except ValueError as error:
			messagebox.showerror("Game setup", str(error), parent=self.root)
			return
		self.selection_frame.pack_forget()
		self.game_frame.pack(fill="both", expand=True)
		self.action_log_button.config(state="normal")
		self.new_game_button.config(state="normal")
		self._render()

	def _new_game(self, settings):
		self.game = PalaceGame(**settings)
		self.game.draw_choice_hook = self._choose_draw_card
		humans = []
		for player_index, player in enumerate(self.game.players):
			if not player.is_bot:
				humans.append(player_index)
				continue
			best_cards = sorted(
				range(len(player.hand)),
				key=lambda index: 15 if player.hand[index].rank == "Joker" else VALUES[player.hand[index].rank],
				reverse=True,
			)[:3]
			self.game.choose_face_up(player_index, best_cards)
		self.setup_queue = humans
		self.setup_player = humans[0]
		self.device_holder = humans[0] if len(humans) == 1 else None
		self.last_human = humans[0]
		self.selected_cards = set()
		self.selected_card = None
		self.selected_pile = None
		self.human_has_played = False
		self.setup_complete = False
		self.fast_forward = False
		self.game_started = True
		self.notice = "Choose three cards to keep face-up for later."

	def _human_indices(self):
		return [index for index, player in enumerate(self.game.players) if not player.is_bot]

	def _is_hot_seat(self):
		return len(self._human_indices()) > 1

	def _needs_handoff(self, player_index):
		return self._is_hot_seat() and player_index != self.device_holder

	def _you(self, player_index):
		return self.game.players[player_index].name if self._is_hot_seat() else "You"

	def _human_quick_grab_target(self):
		if not self.game.pending_quick_grabs:
			return None
		return next(
			(index for index in self.game.pending_quick_grabs[0]["targets"] if not self.game.players[index].is_bot),
			None,
		)

	def _viewer(self):
		"""The human whose controls the screen currently shows."""
		grabber = self._human_quick_grab_target()
		if grabber is not None:
			return grabber
		if not self.setup_complete:
			return self.setup_player
		if not self.game.players[self.game.current_player].is_bot:
			self.last_human = self.game.current_player
		return self.last_human

	def _confirm_handoff(self):
		if not self.setup_complete:
			self.device_holder = self.setup_player
			self._render()
		else:
			self.device_holder = self.game.current_player
			self._run_bot_turns()

	def _reset_game(self):
		if not self.game_started:
			return
		self.game = None
		self.game_started = False
		self.game_frame.pack_forget()
		self.selection_frame.pack(fill="both", expand=True)
		self.action_log_button.config(state="disabled")
		self.new_game_button.config(state="disabled")
		if self.selected_character in CHARACTERS:
			character_index = tuple(CHARACTERS).index(self.selected_character)
			self.character_list.selection_clear(0, "end")
			self.character_list.selection_set(character_index)
			self._preview_character()

	def _card_button(self, parent, text, command, selected=False, hidden=False):
		background = "#d7b66d" if selected else "#304e43" if hidden else "#f4eddc"
		foreground = "#19362f" if not hidden else "#f4eddc"
		return tk.Button(
			parent,
			text=text,
			command=command,
			width=15,
			height=3,
			wraplength=120,
			font=("Georgia", 10, "bold"),
			bg=background,
			fg=foreground,
			activebackground="#d7b66d",
			activeforeground="#19362f",
			relief="flat",
			bd=0,
			cursor="hand2",
		)

	def _render(self):
		self.enchain_button.pack_forget()
		self.vow_button.pack_forget()
		self.vow_label.pack_forget()
		self.god_button.pack_forget()
		self.god_label.pack_forget()
		self.swap_button.pack_forget()
		self.rescue_button.pack_forget()
		self.six_eyes_button.pack_forget()
		self.full_hand_button.pack_forget()
		self.domain_button.pack_forget()
		self.simple_button.pack_forget()
		for widget in self.piles_frame.winfo_children():
			widget.destroy()
		for widget in self.cards_frame.winfo_children():
			widget.destroy()

		game = self.game
		if self.setup_complete and game.winner is None and not game.player_has_finished(game.current_player):
			game.refill_player_hand(game.current_player)
		for widget in self.players_frame.winfo_children():
			widget.destroy()
		for index, player in enumerate(game.players):
			face_up = ", ".join(map(str, player.face_up)) or "none"
			turn_marker = " (current turn)" if index == game.current_player and game.winner is None else ""
			character = f" ({player.character})" if player.character else ""
			cut_meter = f" | Cut Meter: {player.cut_meter}" if player.character == "Sukuna" else ""
			limitless = " | I-T: Permanent" if self.game.effective_ability(index, "Limitless Barrier") == "Perfected Limitless" else " | I-T: Active" if self.game.player_has_immunity(index) else ""
			eliminated = " | ELIMINATED" if player.is_eliminated else ""
			domain = game.player_domain(index)
			if player.simple_domain_active:
				eliminated += f" | Simple Domain: refinement {SIMPLE_DOMAIN_REFINEMENT}"
			if domain:
				eliminated += f" | {domain['name']}: refinement {domain['refinement']}{' (clashing)' if game.is_clashing() else ''}{'' if domain.get('rounds_left') is None else f', {domain['rounds_left']} round(s) left'}"
			revealed = ", ".join(map(str, game.revealed_cards(index)))
			revealed_text = f"\nRevealed: {revealed}" if revealed else ""
			seen = game.known_cards_of(self._viewer(), index) if index != self._viewer() else []
			if seen:
				revealed_text += "\nSeen (Six Eyes): " + ", ".join(map(str, seen))
			label = f"{player.name}{character}{turn_marker}{eliminated} | Hand: {len(player.hand)} | Face-down: {len(player.face_down)}{cut_meter}{limitless}\nFace-up: {face_up}{revealed_text}"
			ttk.Label(
				self.players_frame,
				text=label,
				style="Info.TLabel",
				wraplength=290,
				justify="left",
			).grid(row=index // 3, column=index % 3, sticky="nw", padx=(0, 14), pady=3)
		for column in range(3):
			self.players_frame.columnconfigure(column, weight=1)
		if game.winner is not None:
			winner = game.players[game.winner]
			self.status_label.config(text=f"{winner.name} finished first. Start a new game whenever you're ready.")
			self.cards_title.config(text="Final standings")
			for result in game.finish_order:
				player = game.players[result["player_index"]]
				status = {
					"last remaining": "last player standing",
					"last place (Cut Meter)": "tied last place (Cut Meter)",
				}.get(result["status"], "finished")
				label = f"{result['rank']}. {player.name} - {status} - Round {result['round']}, Turn {result['turn']}"
				ttk.Label(self.cards_frame, text=label, style="Info.TLabel").pack(anchor="w", pady=4)
			self.play_button.pack_forget()
			self.end_button.pack_forget()
			self.ability_button.pack_forget()
			self.world_ability_label.pack_forget()
			self.hollow_ability_label.pack_forget()
			self.world_slash_button.pack_forget()
			self.limitless_button.pack_forget()
			self.quick_grab_button.pack_forget()
			self.decline_quick_grab_button.pack_forget()
			self.evolve_button.pack_forget()
			self.skip_button.pack_forget()
			return

		self.play_button.pack(side="left")
		self.end_button.pack(side="left", padx=10)
		self.ability_button.pack_forget()
		self.world_ability_label.pack_forget()
		self.hollow_ability_label.pack_forget()
		self.world_slash_button.pack_forget()
		self.limitless_button.pack_forget()
		self.quick_grab_button.pack_forget()
		self.decline_quick_grab_button.pack_forget()
		self.evolve_button.pack_forget()
		self.skip_button.pack_forget()
		viewer = self._viewer()
		if all(game.player_has_finished(index) for index in self._human_indices()):
			self.skip_button.pack(side="left", padx=10)
		elif self.setup_complete:
			player_character = game.players[viewer].character
			cleave_ability = game.cleave_ability_name(viewer)
			if cleave_ability is not None:
				remaining = game.ability_uses_remaining(viewer, "Cleave")
				pile_selected = self.selected_pile in (0, 1) and bool(game.discard_piles[self.selected_pile])
				self.ability_button.config(
					text=f"Use {cleave_ability} ({remaining} uses left)",
					state="normal" if game.current_player == viewer and remaining > 0 and pile_selected else "disabled",
				)
				self.ability_button.pack(side="left", padx=10)
			world_ability = game.effective_ability(viewer, "World Cutting Slash")
			if world_ability in ("World Cutting Slash", "Waffle Cutting Slash"):
				self.world_ability_label.config(text=f"{world_ability} active")
				self.world_ability_label.pack(side="left", padx=10)
			hollow_ability = game.effective_ability(viewer, "Hollow Purple")
			if hollow_ability in ("Hollow Purple", "Max Purple"):
				self.hollow_ability_label.config(text=f"{hollow_ability} active")
				self.hollow_ability_label.pack(side="left", padx=10)
			enchain_users = [index for index in self._human_indices() if game.can_use_enchain(index)]
			if enchain_users:
				self.enchain_button.config(text="Use Enchain / Rule Workaround (once per game)")
				self.enchain_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_use_card_swapping(viewer):
				self.swap_button.config(text=f"Card Swapping ({'/'.join(sorted(game.swap_ranks(viewer)))}s)")
				self.swap_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_use_rescue_draw(viewer):
				self.rescue_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_use_six_eyes(viewer):
				self.six_eyes_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_use_full_hand(viewer):
				self.full_hand_button.pack(side="left", padx=10)
			if game.domains and (game.domain_options(viewer) or game.can_domain_draw(viewer) or game.can_joker_domain(viewer)) or (
				game.current_player == viewer and game.domain_options(viewer)
			):
				self.domain_button.config(text="Domain (clash)" if game.domains else "Domain")
				self.domain_button.pack(side="left", padx=10)
			if game.can_use_simple_domain(viewer):
				self.simple_button.config(text="Simple Domain (once per game)")
				self.simple_button.pack(side="left", padx=10)
			elif game.can_simple_cleanse(viewer):
				self.simple_button.config(text="Simple Domain: discard a card to remove an effect")
				self.simple_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_choose_god_rule(viewer):
				self.god_button.config(text="God of Jujutsu (choose a multi use rule for this round)")
				self.god_button.pack(side="left", padx=10)
			if game.god_rule(viewer):
				rule = game.god_rule(viewer)
				extra = f" ({RANKS[game.players[viewer].god_grab_value - 2]})" if rule in ("Quick Grab", "Card Swapping") else ""
				self.god_label.config(text=f"God of Jujutsu: {rule}{extra} this round")
				self.god_label.pack(side="left", padx=10)
			if game.current_player == viewer and game.can_use_binding_vow(viewer):
				self.vow_button.config(text="Binding Vow (pass turn, play a card as a King)")
				self.vow_button.pack(side="left", padx=10)
			if game.is_vow_card(viewer, game.players[viewer].vow_card):
				self.vow_label.config(text=f"Binding Vow: {game.players[viewer].vow_card} plays as a King")
				self.vow_label.pack(side="left", padx=10)
			if game.current_player == viewer and game.players[viewer].pending_world_slashes:
				self.world_slash_button.config(text=f"Resolve World Cutting Slash ({game.players[viewer].pending_world_slashes})")
				self.world_slash_button.pack(side="left", padx=10)
			if game.current_player == viewer and game.players[viewer].pending_limitless_effects:
				self.limitless_button.config(text=f"Resolve Limitless effect ({len(game.players[viewer].pending_limitless_effects)})")
				self.limitless_button.pack(side="left", padx=10)
			if game.pending_quick_grabs and viewer in game.pending_quick_grabs[0]["targets"]:
				self.quick_grab_button.pack(side="left", padx=10)
				self.decline_quick_grab_button.pack(side="left", padx=4)
			eligible_evolutions = [
				track for track in character_ability_tracks(player_character)
				if "evolution" in track
				and not game.players[viewer].ability_states[track["ability"]]["removed"]
				and not game.players[viewer].ability_states[track["ability"]]["evolved"]
			]
			if (
				game.current_player == viewer
				and game.cards_played_this_turn == 0
				and eligible_evolutions
				and any(card.rank == "Joker" for card in game.players[viewer].hand)
			):
				evolutions = ", ".join(track["evolution"]["ability"] for track in eligible_evolutions)
				self.evolve_button.config(text=f"Evolve ability (end turn): {evolutions}")
				self.evolve_button.pack(side="left", padx=10)
		phase = "Setup" if not self.setup_complete else f"Round {game.round_number}  |  Turn {game.turn_number}  |  {game.players[game.current_player].name}"
		self.status_label.config(text=f"{phase}\n{self.notice}")
		for pile_index, pile in enumerate(game.draw_piles):
			draw_panel = tk.Label(
				self.piles_frame,
				text=f"DRAW PILE {pile_index + 1}\nCards hidden\n{len(pile)} cards",
				font=("Georgia", 10, "bold"),
				bg="#304e43",
				fg="#f4eddc",
				width=20,
				height=4,
			)
			draw_panel.grid(row=0, column=pile_index, padx=5, pady=(0, 8), sticky="ew")
		for column, (title, pile) in enumerate((
			("Destroyed pile", game.destroyed_pile),
			("Deleted pile", game.deleted_pile),
		)):
			pile_button = ttk.Button(
				self.piles_frame,
				text=f"{title}\n{len(pile)} cards",
				command=lambda name=title: self._show_special_pile(name),
			)
			pile_button.grid(row=0, column=column + 2, padx=5, pady=(0, 8), sticky="ew")
		for pile_index, pile in enumerate(game.discard_piles):
			top = _played_card_label(pile[-1], game.pile_values[pile_index]) if pile else "Empty"
			selected = pile_index == self.selected_pile
			discard_panel = ttk.Frame(self.piles_frame, style="App.TFrame")
			discard_panel.grid(row=1, column=pile_index * 2, columnspan=2, padx=5, sticky="ew")
			button = tk.Button(
				discard_panel,
				text=f"DISCARD {pile_index + 1}\n{top}\n{len(pile)} cards",
				command=lambda index=pile_index: self._select_pile(index),
				font=("Georgia", 11, "bold"),
				bg="#d7b66d" if selected else "#f4eddc",
				fg="#19362f",
				activebackground="#d7b66d",
				relief="flat",
				width=24,
				height=4,
				cursor="hand2",
			)
			button.pack(fill="x")
			ttk.Button(
				discard_panel,
				text="View all cards",
				command=lambda index=pile_index: self._show_pile(f"Discard pile {index + 1}", game.discard_piles[index]),
			).pack(fill="x", pady=(4, 0))
		for column in range(4):
			self.piles_frame.columnconfigure(column, weight=1)

		if not self.setup_complete:
			self.ability_button.pack_forget()
			self.world_ability_label.pack_forget()
			self.hollow_ability_label.pack_forget()
			self.world_slash_button.pack_forget()
			self.limitless_button.pack_forget()
			self.quick_grab_button.pack_forget()
			self.decline_quick_grab_button.pack_forget()
			self.evolve_button.pack_forget()
			player = game.players[self.setup_player]
			if self._needs_handoff(self.setup_player):
				self._show_handoff(player.name)
				return
			self.cards_title.config(text=f"{player.name}: choose 3 face-up cards  |  {len(self.selected_cards)}/3 selected" if self._is_hot_seat() else f"Choose 3 face-up cards  |  {len(self.selected_cards)}/3 selected")
			for index, card in enumerate(player.hand):
				self._card_button(
					self.cards_frame,
					str(card),
					lambda card_index=index: self._toggle_setup_card(card_index),
					selected=index in self.selected_cards,
				).grid(row=index // 6, column=index % 6, padx=5, pady=5)
			self.play_button.config(text="Set face-up cards", command=self._finish_setup, state="normal" if len(self.selected_cards) == 3 else "disabled")
			self.end_button.pack_forget()
			return

		player = game.players[game.current_player]
		source, cards = _current_source(game, player)
		if player.is_bot:
			self.cards_title.config(text="Bots are playing")
			self.play_button.config(state="disabled")
			self.end_button.config(state="disabled")
			return
		if self._needs_handoff(game.current_player):
			self._show_handoff(player.name)
			return
		self.cards_title.config(text=f"{player.name}'s {source.replace('_', ' ')}" if source and self._is_hot_seat() else f"Your {source.replace('_', ' ')}" if source else "No cards available")
		for index, card in enumerate(cards):
			label = f"Card {index + 1}" if source == "face_down" else str(card)
			self._card_button(
				self.cards_frame,
				label,
				lambda card_index=index: self._select_card(card_index),
				selected=index == self.selected_card,
				hidden=source == "face_down",
			).grid(row=index // 6, column=index % 6, padx=5, pady=5)
		pending_effects = bool(
			player.pending_world_slashes
			or player.pending_limitless_effects
			or self._human_quick_grab_target() is not None
		)
		can_play = source is not None and self.selected_card is not None and self.selected_pile is not None and not pending_effects
		self.play_button.config(text="Reveal and play" if source == "face_down" else "Play selected card", command=self._play_selected, state="normal" if can_play else "disabled")
		self.end_button.config(
			state="normal" if self.human_has_played and not pending_effects and not game.enchain_must_keep_playing(game.current_player) else "disabled"
		)
		if source is None:
			self.root.after(0, self._end_human_turn)
		elif source != "face_down" and not _legal_options(game, cards):
			if game.cards_played_this_turn == 0 and game.enchain_return is not None:
				self.notice = "No legal play during Enchain; the interrupted turn resumes."
				self.root.after(0, self._finish_human_turn)
			elif game.cards_played_this_turn == 0:
				self.root.after(0, self._take_piles_and_end)
			else:
				follow_up_notice = "No legal follow-up plays. End your turn to continue."
				if "World Cutting Slash" in self.notice:
					self.notice = f"{self.notice}\n{follow_up_notice}"
				else:
					self.notice = follow_up_notice
				self.status_label.config(text=f"{phase}\n{self.notice}")

	def _show_handoff(self, name):
		self.cards_title.config(text="Pass the device")
		for button in (
			self.ability_button, self.world_ability_label, self.hollow_ability_label, self.world_slash_button,
			self.limitless_button, self.quick_grab_button, self.decline_quick_grab_button, self.evolve_button,
		):
			button.pack_forget()
		self.play_button.config(state="disabled")
		self.end_button.config(state="disabled")
		ttk.Label(self.cards_frame, text=f"Hand the device to {name}. Hands stay hidden until they are ready.", style="Info.TLabel").pack(anchor="w", pady=(0, 10))
		ttk.Button(self.cards_frame, text=f"I'm {name} - show my cards", style="Action.TButton", command=self._confirm_handoff).pack(anchor="w")

	def _show_special_pile(self, title):
		pile = self.game.destroyed_pile if title == "Destroyed pile" else self.game.deleted_pile
		self._show_pile(title, pile)

	def _choose_world_slash_card(self):
		game = self.game
		choices = []
		for player_index, player in enumerate(game.players):
			if player.is_eliminated or player_index != game.current_player and game.player_has_immunity(player_index):
				continue
			for zone, label in (("hand", "hand"), ("face_up", "face-up"), ("face_down", "face-down (random)")):
				count = len(getattr(player, zone))
				if count:
					choices.append((f"{player.name}'s {label} ({count})", zone, player_index, None))
		for pile_index, pile in enumerate(game.discard_piles):
			if pile:
				choices.append((f"Discard pile {pile_index + 1} ({len(pile)})", "discard_pile", None, pile_index))
		if game.destroyed_pile:
			choices.append((f"Destroyed pile ({len(game.destroyed_pile)})", "destroyed_pile", None, None))
		for pile_index, pile in enumerate(game.draw_piles):
			if pile:
				choices.append((f"Draw pile {pile_index + 1} (random, {len(pile)})", "draw_pile", None, pile_index))
		if not choices:
			return None
		options = "\n".join(f"{index + 1}. {choice[0]}" for index, choice in enumerate(choices))
		choice = simpledialog.askinteger(
			"World Cutting Slash",
			f"Choose a card or pile to delete:\n{options}",
			minvalue=1,
			maxvalue=len(choices),
			parent=self.root,
		)
		if choice is None:
			return None
		_, zone, owner_index, pile_index = choices[choice - 1]
		card_index = None
		if zone in ("hand", "face_up", "discard_pile", "destroyed_pile"):
			if zone == "discard_pile":
				cards = game.discard_piles[pile_index]
			elif zone == "destroyed_pile":
				cards = game.destroyed_pile
			else:
				cards = getattr(game.players[owner_index], zone)
			card_list = "\n".join(f"{index + 1}. {card}" for index, card in enumerate(cards))
			card_choice = simpledialog.askinteger(
				"World Cutting Slash",
			f"Choose the card to delete:\n{card_list}",
				minvalue=1,
				maxvalue=len(cards),
				parent=self.root,
			)
			if card_choice is None:
				return None
			card_index = card_choice - 1
		return zone, owner_index, card_index, pile_index

	def _resolve_pending_limitless_effects(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot:
			return
		player = game.players[current]
		while player.pending_limitless_effects and game.winner is None:
			effect = player.pending_limitless_effects[0]
			if effect == "pick_one_face_down" and player.face_down:
				choice = simpledialog.askinteger(
					"Limitless Barrier",
					f"Choose one face-down card to pick up (1-{len(player.face_down)}):",
					minvalue=1,
					maxvalue=len(player.face_down),
					parent=self.root,
				)
				if choice is None:
					self._render()
					return
				cards = game.resolve_limitless_effect(current, face_down_index=choice - 1)
				self.notice = f"Limitless Barrier picked up {cards[0]}."
			elif effect == "replace_hand_from_deleted" and player.hand and game.deleted_pile:
				count = min(len(player.hand), len(game.deleted_pile))
				selected = []
				for _ in range(count):
					options = "\n".join(
						f"{index + 1}. {card}"
						for index, card in enumerate(game.deleted_pile)
						if index not in selected
					)
					available_indices = [index for index in range(len(game.deleted_pile)) if index not in selected]
					choice = simpledialog.askinteger(
						"Perfected Limitless",
						f"Choose a Deleted card for your replacement hand:\n{options}",
						minvalue=1,
						maxvalue=len(available_indices),
						parent=self.root,
					)
					if choice is None:
						self._render()
						return
					selected.append(available_indices[choice - 1])
				cards = game.resolve_limitless_effect(current, deleted_indices=tuple(selected))
				self.notice = f"Perfected Limitless replaced your hand with {len(cards)} Deleted card(s)."
			else:
				cards = game.resolve_limitless_effect(current)
				if effect == "pick_all_face_down":
					self.notice = f"Limitless Barrier picked up {len(cards)} face-down card(s)."
				elif effect == "replace_hand_from_deleted":
					self.notice = "No Deleted cards were available to replace your hand."
				else:
					self.notice = "No face-down cards were available to pick up."
			self._render()

	def _resolve_bot_limitless_effects(self, player_index):
		game = self.game
		player = game.players[player_index]
		while player.pending_limitless_effects and game.winner is None:
			effect = player.pending_limitless_effects[0]
			if effect == "pick_one_face_down":
				index = game.rng.randrange(len(player.face_down)) if player.face_down else None
				game.resolve_limitless_effect(player_index, face_down_index=index)
			elif effect == "pick_all_face_down":
				game.resolve_limitless_effect(player_index)
			else:
				count = min(len(player.hand), len(game.deleted_pile))
				indices = game.rng.sample(range(len(game.deleted_pile)), count) if count else ()
				game.resolve_limitless_effect(player_index, deleted_indices=indices)

	def _resolve_pending_world_slashes(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or game.players[current].pending_world_slashes <= 0:
			return
		while game.players[current].pending_world_slashes and game.winner is None:
			deletion = self._choose_world_slash_card()
			if deletion is None:
				self.notice = "World Cutting Slash remains pending."
				self._render()
				return
			zone, owner_index, card_index, pile_index = deletion
			targets = [
				index for index, player in enumerate(game.players)
				if index != current and not player.is_eliminated and not game.player_has_finished(index) and not game.player_has_immunity(index)
			]
			target_index = None
			if targets:
				target_list = "\n".join(
					f"{choice + 1}. {game.players[index].name} (Cut Meter {game.players[index].cut_meter}/9)"
					for choice, index in enumerate(targets)
				)
				target_choice = simpledialog.askinteger(
					"World Cutting Slash",
					f"Choose another player to increase their Cut Meter:\n{target_list}",
					minvalue=1,
					maxvalue=len(targets),
					parent=self.root,
				)
				if target_choice is None:
					self.notice = "World Cutting Slash remains pending."
					self._render()
					return
				target_index = targets[target_choice - 1]
			try:
				card, hidden, meter = game.resolve_world_cutting_slash(
					current,
					zone,
					target_index,
					card_owner_index=owner_index,
					card_index=card_index,
					pile_index=pile_index,
				)
			except ValueError as error:
				self.notice = str(error)
				self._render()
				return
			if meter is None:
				self.notice = "World Cutting Slash deleted a card; no active opponent remains for Cut Meter."
			else:
				target = game.players[target_index]
				card_label = "a hidden card" if hidden else str(card)
				self.notice = f"World Cutting Slash deleted {card_label}; {target.name}'s Cut Meter is {meter}/9."
				if target.is_eliminated:
					self.notice += f" {target.name} is eliminated and tied for last place."
			self._render()

	def _quick_grab_pending_ace(self):
		self._resolve_quick_grab_choice(True)

	def _decline_quick_grab(self):
		self._resolve_quick_grab_choice(False)

	def _resolve_quick_grab_choice(self, accept):
		viewer = self._human_quick_grab_target()
		if viewer is None:
			return
		try:
			self.game.resolve_quick_grab(viewer, accept)
		except ValueError as error:
			self.notice = str(error)
		else:
			grabber = self._you(viewer)
			self.notice = f"{grabber} took the card into {'your' if grabber == 'You' else 'their'} hand via Quick Grab." if accept else f"{grabber} declined Quick Grab."
		self.game.resolve_bot_quick_grabs()
		self._render()
		if (
			self.game.players[self.game.current_player].is_bot
			and self._human_quick_grab_target() is None
		):
			self.root.after(0, self._run_bot_turns)

	def _show_character_reference(self):
		window = tk.Toplevel(self.root)
		window.title("Characters")
		window.geometry("760x560")
		window.transient(self.root)
		frame = ttk.Frame(window, padding=14)
		frame.pack(fill="both", expand=True)
		text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), padx=12, pady=12)
		scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
		text.configure(yscrollcommand=scrollbar.set, state="normal")
		text.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")
		character_sections = []
		for character_name in CHARACTERS:
			ability_sections = []
			for track in character_ability_tracks(character_name):
				ability_sections.append(f"{track['ability']}\n{track['description']}")
				if "evolution" in track:
					evolution = track["evolution"]
					ability_sections.append(f"Evolution: {evolution['ability']}\n{evolution['description']}")
			character_sections.append(f"{character_name}\n\n" + "\n\n--------------------\n\n".join(ability_sections))
		text.insert("1.0", "\n\n==============================\n\n".join(character_sections))
		text.configure(state="disabled")

	def _show_settings(self):
		window = tk.Toplevel(self.root)
		window.title("Settings")
		window.geometry("440x260")
		window.transient(self.root)
		frame = ttk.Frame(window, padding=22)
		frame.pack(fill="both", expand=True)
		ttk.Label(frame, text="Admin access", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
		ttk.Label(frame, text="Enter the admin password to enable card editing.", style="Info.TLabel").pack(anchor="w", pady=(0, 10))
		password = ttk.Entry(frame, show="*", width=32)
		password.pack(anchor="w", fill="x", pady=(0, 8))
		status = ttk.Label(frame, style="Info.TLabel")
		status.pack(anchor="w", pady=(0, 8))
		edit_button = ttk.Button(
			frame,
			text="Edit all card values",
			command=lambda: (window.destroy(), self._show_card_value_editor()),
			state="normal" if self.admin_unlocked and self.game is not None else "disabled",
		)
		edit_button.pack(anchor="w", pady=(4, 0))
		if self.admin_unlocked:
			status.config(text="Admin access is unlocked for this session.")

		def unlock_admin():
			if password.get() != ADMIN_PASSWORD:
				status.config(text="Incorrect password.")
				return
			self.admin_unlocked = True
			status.config(text="Admin access unlocked for this session.")
			edit_button.config(state="normal" if self.game is not None else "disabled")

		ttk.Button(frame, text="Unlock", command=unlock_admin).pack(anchor="w", pady=(0, 8))
		password.bind("<Return>", lambda _event: unlock_admin())

	def _show_card_value_editor(self):
		if not self.admin_unlocked or self.game is None:
			return
		game = self.game
		window = tk.Toplevel(self.root)
		window.title("Admin card editor")
		window.geometry("900x600")
		window.transient(self.root)
		body = ttk.Frame(window, padding=14)
		body.pack(fill="both", expand=True)
		ttk.Label(body, text="Edit a card's rank and suit", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
		content = ttk.Frame(body)
		content.pack(fill="both", expand=True)
		tree = ttk.Treeview(content, columns=("location", "card"), show="headings", selectmode="browse")
		tree.heading("location", text="Location")
		tree.heading("card", text="Current card")
		tree.column("location", width=300, stretch=True)
		tree.column("card", width=200, stretch=True)
		scrollbar = ttk.Scrollbar(content, orient="vertical", command=tree.yview)
		tree.configure(yscrollcommand=scrollbar.set)
		tree.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="left", fill="y")
		editor = ttk.Frame(content, padding=(18, 0, 0, 0))
		editor.pack(side="left", fill="y")
		selected_label = ttk.Label(editor, text="Select a card", style="Section.TLabel", wraplength=220)
		selected_label.pack(anchor="w", pady=(0, 12))
		ttk.Label(editor, text="Rank").pack(anchor="w")
		rank_var = tk.StringVar()
		rank_box = ttk.Combobox(editor, textvariable=rank_var, values=(*RANKS, "Joker"), state="readonly", width=18)
		rank_box.pack(anchor="w", pady=(2, 10))
		ttk.Label(editor, text="Suit").pack(anchor="w")
		suit_var = tk.StringVar()
		suit_box = ttk.Combobox(editor, textvariable=suit_var, values=SUITS, state="readonly", width=18)
		suit_box.pack(anchor="w", pady=(2, 14))
		status = ttk.Label(editor, style="Info.TLabel", wraplength=220)
		status.pack(anchor="w", pady=(0, 8))
		rows = {}
		selected_item = {"iid": None}

		def add_zone(location, cards, zone, player_index=None, pile_index=None):
			for card_index, card in enumerate(cards):
				iid = f"card-{len(rows)}"
				tree.insert("", "end", iid=iid, values=(location, str(card)))
				rows[iid] = {
					"cards": cards,
					"card_index": card_index,
					"card": card,
					"zone": zone,
					"pile_index": pile_index,
				}

		for player in game.players:
			for zone in ("hand", "face_up", "face_down"):
				add_zone(f"{player.name} / {zone.replace('_', ' ')}", getattr(player, zone), zone)
		for pile_index, pile in enumerate(game.draw_piles):
			add_zone(f"Draw pile {pile_index + 1}", pile, "draw_pile", pile_index=pile_index)
		for pile_index, pile in enumerate(game.discard_piles):
			add_zone(f"Discard pile {pile_index + 1}", pile, "discard_pile", pile_index=pile_index)
		add_zone("Destroyed pile", game.destroyed_pile, "destroyed_pile")
		add_zone("Deleted pile", game.deleted_pile, "deleted_pile")

		def load_selected(_event=None):
			selection = tree.selection()
			if not selection:
				selected_item["iid"] = None
				selected_label.config(text="Select a card")
				return
			iid = selection[0]
			card = rows[iid]["card"]
			selected_item["iid"] = iid
			selected_label.config(text=f"{tree.set(iid, 'location')}\n{card}")
			rank_var.set(card.rank)
			suit_var.set(card.suit if card.suit in SUITS else SUITS[0])
			suit_box.configure(state="disabled" if card.rank == "Joker" else "readonly")

		def save_card():
			iid = selected_item["iid"]
			if iid is None:
				return
			row = rows[iid]
			old_card = row["card"]
			rank = rank_var.get()
			if rank not in (*RANKS, "Joker"):
				status.config(text="Choose a valid rank.")
				return
			suit = "" if rank == "Joker" else suit_var.get() if suit_var.get() in SUITS else old_card.suit or SUITS[0]
			deck_number = 3 if rank == "Joker" else old_card.deck_number
			updated = Card(rank, suit, deck_number)
			row["cards"][row["card_index"]] = updated
			row["card"] = updated
			pile_index = row["pile_index"]
			if row["zone"] == "discard_pile":
				value = 14 if rank == "Joker" else VALUES[rank]
				game.pile_value_history[pile_index][row["card_index"]] = value
				if row["card_index"] == len(game.discard_piles[pile_index]) - 1:
					game.pile_values[pile_index] = value
			game._record(f"Admin changed {tree.set(iid, 'location')} card value to {updated}.")
			tree.set(iid, "card", str(updated))
			selected_label.config(text=f"{tree.set(iid, 'location')}\n{updated}")
			status.config(text=f"Updated to {updated}.")
			self._render()

		tree.bind("<<TreeviewSelect>>", load_selected)
		ttk.Button(editor, text="Apply card change", command=save_card).pack(anchor="w", pady=(4, 0))

	def _show_pile(self, title, cards):
		window = tk.Toplevel(self.root)
		window.title(f"{title} ({len(cards)} cards)")
		window.geometry("380x440")
		window.transient(self.root)
		content = tk.Text(window, wrap="none", font=("Consolas", 11), padx=12, pady=12)
		scrollbar = ttk.Scrollbar(window, orient="vertical", command=content.yview)
		content.configure(yscrollcommand=scrollbar.set, state="normal")
		content.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")
		lines = [f"{index}. {card}" for index, card in enumerate(cards, start=1)]
		if lines:
			lines[-1] += "  (top)"
		else:
			lines.append("Empty")
		content.insert("1.0", "\n".join(lines))
		content.configure(state="disabled")

	def _show_action_log(self):
		window = tk.Toplevel(self.root)
		window.title("Palace action log")
		window.geometry("760x520")
		window.transient(self.root)
		content = tk.Text(window, wrap="word", font=("Consolas", 10), padx=12, pady=12)
		scrollbar = ttk.Scrollbar(window, orient="vertical", command=content.yview)
		content.configure(yscrollcommand=scrollbar.set, state="normal")
		content.pack(side="left", fill="both", expand=True)
		scrollbar.pack(side="right", fill="y")
		try:
			entries = self.game.log_path.read_text(encoding="utf-8")
		except OSError:
			entries = "\n".join(self.game.action_log)
		content.insert("1.0", entries or "No actions have been logged yet.")
		content.see("end")
		content.configure(state="disabled")

	def _toggle_setup_card(self, card_index):
		if card_index in self.selected_cards:
			self.selected_cards.remove(card_index)
		elif len(self.selected_cards) < 3:
			self.selected_cards.add(card_index)
		self._render()

	def _finish_setup(self):
		if len(self.selected_cards) != 3:
			return
		self.game.choose_face_up(self.setup_player, sorted(self.selected_cards))
		self.selected_cards.clear()
		position = self.setup_queue.index(self.setup_player)
		if position + 1 < len(self.setup_queue):
			self.setup_player = self.setup_queue[position + 1]
			self.notice = "Choose three cards to keep face-up for later."
			self._render()
			return
		self.setup_complete = True
		self.notice = "Select a card and a discard pile, then play."
		self._render()
		self._run_bot_turns()

	def _select_card(self, card_index):
		self.selected_card = card_index
		self._render()

	def _select_pile(self, pile_index):
		self.selected_pile = pile_index
		self._render()

	def _use_character_ability(self):
		if self.game is None:
			return
		current = self.game.current_player
		if self.game.players[current].is_bot or self.game.cleave_ability_name(current) is None or self.selected_pile is None:
			return
		replacement_indices = None
		replacement_joker_values = None
		replacement_sources = None
		player = self.game.players[current]
		available_replacements = len(player.hand) + len(player.face_up) + len(player.face_down)
		if (
			self.game.effective_ability(current) == "Spider Net Cleave"
			and len(self.game.discard_piles[self.selected_pile]) == 1
			and available_replacements >= 2
		):
			choices = self._choose_spider_replacements()
			if choices is None:
				return
			replacement_indices, replacement_joker_values, replacement_sources = choices
		try:
			card = self.game.use_cleave(
				current,
				self.selected_pile,
				replacement_indices=replacement_indices,
				replacement_joker_values=replacement_joker_values,
				replacement_sources=replacement_sources,
			)
		except ValueError as error:
			self.notice = str(error)
		else:
			if replacement_indices is not None:
				self.notice = f"Spider Net Cleave destroyed both piles, moved {card} to Destroyed, and replaced both piles with your chosen cards."
			else:
				self.notice = f"Cleave destroyed {card}."
		self._render()
		player = self.game.players[current]
		if player.pending_world_slashes and self.game.winner is None:
			self._resolve_pending_world_slashes()

	def _choose_spider_replacements(self):
		player = self.game.players[self.game.current_player]
		indices = []
		sources = []
		joker_values = []
		for pile_index in range(2):
			while True:
				available_source = next(
					(source for source in ("hand", "face_up", "face_down")
					 if any((source, index) not in zip(sources, indices) for index in range(len(getattr(player, source))))),
					None,
				)
				if available_source is None:
					return None
				available_cards = [
					(index, card)
					for index, card in enumerate(getattr(player, available_source))
					if (available_source, index) not in zip(sources, indices)
				]
				cards = "\n".join(
					f"{option + 1}. {card if available_source != 'face_down' else 'Face-down card'}"
					for option, (_, card) in enumerate(available_cards)
				)
				prompt = f"Choose a card from your {available_source.replace('_', ' ')} for discard pile {pile_index + 1}:\n{cards}"
				choice = simpledialog.askinteger(
					"Spider Net Cleave",
					prompt,
					minvalue=1,
					maxvalue=len(available_cards),
					parent=self.root,
				)
				if choice is None:
					return None
				card_index, card = available_cards[choice - 1]
				break
			indices.append(card_index)
			sources.append(available_source)
			joker_value = None
			if card.rank == "Joker":
				joker_value = simpledialog.askinteger(
					"Joker value",
					f"Choose the replacement Joker's value for discard pile {pile_index + 1} (2-14):",
					minvalue=2,
					maxvalue=14,
					parent=self.root,
				)
				if joker_value is None:
					return None
			joker_values.append(joker_value)
		return tuple(indices), tuple(joker_values), tuple(sources)

	def _use_enchain(self):
		game = self.game
		users = [index for index in self._human_indices() if game.can_use_enchain(index)]
		if not users:
			return
		user = users[0]
		if len(users) > 1:
			viewer = self._viewer()
			if viewer in users:
				user = viewer
			else:
				options = "\n".join(f"{number + 1}. {game.players[index].name}" for number, index in enumerate(users))
				pick = simpledialog.askinteger("Enchain", f"Who is using Enchain?\n{options}", minvalue=1, maxvalue=len(users), parent=self.root)
				if pick is None:
					return
				user = users[pick - 1]
		targets = game.enchain_targets(user)
		options = "\n".join(f"{number + 1}. {game.players[index].name}" for number, index in enumerate(targets))
		choice = simpledialog.askinteger(
			"Enchain",
			f"{game.players[user].name}: choose a player to soul swap with. You must then play 2 cards:\n{options}",
			minvalue=1,
			maxvalue=len(targets),
			parent=self.root,
		)
		if choice is None:
			return
		try:
			game.use_enchain(user, targets[choice - 1])
		except ValueError as error:
			self.notice = str(error)
		else:
			self.notice = f"{self._you(user)} soul swapped with {game.players[targets[choice - 1]].name}. Play 2 cards in a row."
			self.device_holder = user
			self.last_human = user
			self.human_has_played = False
		self.selected_card = None
		self.selected_pile = None
		self._render()

	def _resolve_pending_reveals(self):
		game = self.game
		while game.pending_reveals:
			index = game.pending_reveals[0]
			player = game.players[index]
			if self._is_hot_seat():
				messagebox.showinfo("Reveal", f"Hand the device to {player.name} to choose a card to reveal. Everyone will see it.", parent=self.root)
			options = "\n".join(f"{number + 1}. {card}" for number, card in enumerate(player.hand))
			pick = simpledialog.askinteger(
				"Reveal",
				f"{player.name}: choose a card from your hand to reveal until it is played:\n{options}",
				minvalue=1,
				maxvalue=len(player.hand),
				parent=self.root,
			)
			game.reveal_card(index, (pick - 1) if pick else game.rng.randrange(len(player.hand)))

	def _swap_target_label(self, target):
		owner, zone, _ = target
		if owner >= 0:
			return f"{self.game.players[owner].name}'s {zone.replace('_', ' ')}"
		return "destroyed pile" if zone == "destroyed" else f"discard pile {int(zone[-1]) + 1}"

	def _use_card_swapping(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_use_card_swapping(current):
			return
		player = game.players[current]
		own, theirs = game.card_swap_options(current)
		own_text = "\n".join(f"{n + 1}. {getattr(player, zone)[i]} ({zone.replace('_', ' ')})" for n, (zone, i) in enumerate(own))
		own_pick = simpledialog.askinteger("Card Swapping", f"Choose your card to give away:\n{own_text}", minvalue=1, maxvalue=len(own), parent=self.root)
		if own_pick is None:
			return
		their_text = "\n".join(
			f"{n + 1}. {game.swap_target_card(target)} - {self._swap_target_label(target)}"
			for n, target in enumerate(theirs)
		)
		their_pick = simpledialog.askinteger("Card Swapping", f"Choose a visible card to take:\n{their_text}", minvalue=1, maxvalue=len(theirs), parent=self.root)
		if their_pick is None:
			return
		try:
			game.card_swap(current, *own[own_pick - 1], *theirs[their_pick - 1])
		except ValueError as error:
			self.notice = str(error)
		else:
			self.notice = f"{self._you(current)} swapped a card and everyone else must reveal one."
			self._resolve_pending_reveals()
		self.selected_card = None
		self.selected_pile = None
		self._render()

	def _use_simple_domain(self):
		game = self.game
		viewer = self._viewer()
		if game.can_use_simple_domain(viewer):
			if messagebox.askyesno("Simple Domain", "Activate Simple Domain now? It gives you refinement 3 and can only be used once per game. It isn't offensive and doesn't let others clash.", parent=self.root):
				game.use_simple_domain(viewer)
				self.notice = f"{self._you(viewer)} activated Simple Domain."
		elif game.can_simple_cleanse(viewer):
			effects = game.negative_effects(viewer)
			effect_text = "\n".join(f"{n + 1}. {name}" for n, name in enumerate(effects))
			effect_pick = simpledialog.askinteger("Simple Domain", "Which negative effect do you remove?\n" + effect_text, minvalue=1, maxvalue=len(effects), parent=self.root)
			if effect_pick is None:
				return
			hand = game.players[viewer].hand
			card_text = "\n".join(f"{n + 1}. {card}" for n, card in enumerate(hand))
			card_pick = simpledialog.askinteger("Simple Domain", "Which card from your hand do you discard?\n" + card_text, minvalue=1, maxvalue=len(hand), parent=self.root)
			if card_pick is None:
				return
			try:
				game.simple_cleanse(viewer, effects[effect_pick - 1], card_pick - 1)
			except ValueError as error:
				self.notice = str(error)
			else:
				self.notice = f"{self._you(viewer)} removed {effects[effect_pick - 1]} with Simple Domain."
		self._render()

	def _use_domain(self):
		game = self.game
		viewer = self._viewer()
		actions = []
		for name, unlocked in game.domain_options(viewer):
			actions.append(("open", name, unlocked))
		if game.can_domain_draw(viewer):
			actions.append(("draw", None, True))
		if game.can_joker_domain(viewer):
			for domain in game.domains:
				actions.append(("joker", domain["player"], True))
		if not actions:
			return
		lines = []
		for number, (kind, arg, unlocked) in enumerate(actions):
			if kind == "open":
				verb = "Clash with" if game.domains else "Open"
				lines.append(f"{number + 1}. {verb} {arg}" + ("" if unlocked else " (locked: pay a cost)"))
			elif kind == "draw":
				lines.append(f"{number + 1}. Draw a card for your domain")
			else:
				lines.append(f"{number + 1}. Expend a Joker to weaken {game.domains and game.player_domain(arg)['name']} ({game.players[arg].name})")
		pick = simpledialog.askinteger("Domain", DOMAIN_CLASHING_RULE + "\n\n" + "\n".join(lines), minvalue=1, maxvalue=len(actions), parent=self.root)
		if pick is None:
			return
		kind, arg, unlocked = actions[pick - 1]
		try:
			if kind == "open":
				payment, ability = None, None
				if not unlocked:
					player = game.players[viewer]
					costs = ["refinement"]
					if any(card.rank == "Joker" for card in player.hand):
						costs.append("joker")
					upgraded = [
						track["evolution"]["ability"]
						for track in character_ability_tracks(player.character)
						if "evolution" in track and player.ability_states[track["ability"]]["evolved"]
						and DOMAIN_TAG not in track["evolution"]["ability"]
					]
					if upgraded:
						costs.append("ability")
					text = "\n".join(f"{n + 1}. {cost}" for n, cost in enumerate(costs))
					cost_pick = simpledialog.askinteger("Domain cost", "Pay with (refinement = -1 refinement, joker, ability = exchange an upgrade):\n" + text, minvalue=1, maxvalue=len(costs), parent=self.root)
					if cost_pick is None:
						return
					payment = costs[cost_pick - 1]
					if payment == "ability":
						names = "\n".join(f"{n + 1}. {name}" for n, name in enumerate(upgraded))
						ability_pick = simpledialog.askinteger("Exchange ability", "Which upgraded ability do you give up?\n" + names, minvalue=1, maxvalue=len(upgraded), parent=self.root)
						if ability_pick is None:
							return
						ability = upgraded[ability_pick - 1]
				game.open_domain(viewer, arg, payment, ability)
				self.notice = f"{self._you(viewer)} opened {arg}."
			elif kind == "draw":
				card, result = game.domain_draw(viewer)
				self.notice = f"{self._you(viewer)} drew {card} for the domain: {result}."
			else:
				game.joker_domain(viewer, arg)
				self.notice = f"{self._you(viewer)} used a Joker against a domain."
		except ValueError as error:
			self.notice = str(error)
		self._render()

	def _use_six_eyes(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_use_six_eyes(current):
			return
		options = game.six_eyes_options(current)
		player = game.players[current]
		lines = []
		for number, (kind, index) in enumerate(options):
			if kind == "face_down":
				lines.append(f"{number + 1}. One of your face-down cards (slot {index + 1})")
			else:
				lines.append(f"{number + 1}. {game.players[index].name}'s hand")
		pick = simpledialog.askinteger("Six Eyes", "View one of your face-down cards or see someone's hand:\n" + "\n".join(lines), minvalue=1, maxvalue=len(options), parent=self.root)
		if pick is None:
			return
		try:
			cards = game.use_six_eyes(current, *options[pick - 1])
		except ValueError as error:
			self.notice = str(error)
		else:
			messagebox.showinfo("Six Eyes", "You see: " + ", ".join(map(str, cards)) + "\n(You will remember these cards.)", parent=self.root)
			self.notice = f"{self._you(current)} used Six Eyes."
		self._render()

	def _use_full_hand(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_use_full_hand(current):
			return
		try:
			game.use_full_hand(current)
		except ValueError as error:
			self.notice = str(error)
		else:
			self.notice = f"{self._you(current)} picked up all face-up and face-down cards with Full Hand."
		self.selected_card = None
		self._render()

	def _choose_draw_card(self, player_index, options):
		game = self.game
		lines = [
			f"{number + 1}. {game.draw_piles[pile][-1 - depth]} (draw pile {pile + 1}, card {depth + 1} from the top)"
			for number, (pile, depth) in enumerate(options)
		]
		pick = simpledialog.askinteger("Mastered Six Eyes", "Choose 1 card to draw:\n" + "\n".join(lines), minvalue=1, maxvalue=len(options), parent=self.root)
		return options[pick - 1] if pick else None

	def _use_rescue_draw(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_use_rescue_draw(current):
			return
		destroyed_index = None
		if not any(game.draw_piles):
			options = "\n".join(f"{n + 1}. {card}" for n, card in enumerate(game.destroyed_pile))
			pick = simpledialog.askinteger("Rescue Draw", f"The draw pile is gone. Take 1 card from the destroyed pile:\n{options}", minvalue=1, maxvalue=len(game.destroyed_pile), parent=self.root)
			if pick is None:
				return
			destroyed_index = pick - 1
		elif not messagebox.askyesno("Rescue Draw", "Draw 2 cards from the draw pile? (Usable once every 2 rounds)", parent=self.root):
			return
		try:
			game.use_rescue_draw(current, destroyed_index)
		except ValueError as error:
			self.notice = str(error)
		else:
			self.notice = f"{self._you(current)} used Rescue Draw."
		self._render()

	def _use_god_of_jujutsu(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_choose_god_rule(current):
			return
		rules = [
			rule for rule in GOD_RULES
			if (rule != "Soul Swap" or game.cards_played_this_turn == 0 and game.soul_swap_targets(current))
			and (rule != "Rescue Draw" or game._rescue_ready(current))
			and (rule != "Full Hand" or game.players[current].face_up or game.players[current].face_down)
		]
		options = "\n".join(f"{number + 1}. {rule}" for number, rule in enumerate(rules))
		choice = simpledialog.askinteger(
			"God of Jujutsu",
			f"Choose 1 multi use rule to use this round:\n{options}",
			minvalue=1,
			maxvalue=len(rules),
			parent=self.root,
		)
		if choice is None:
			return
		rule = rules[choice - 1]
		value = None
		target = None
		if rule in ("Quick Grab", "Card Swapping"):
			value = simpledialog.askinteger(
				rule,
				"Which card value?\n(2-10, 11 = Jack, 12 = Queen, 13 = King, 14 = Ace)",
				minvalue=2,
				maxvalue=14,
				parent=self.root,
			)
			if value is None:
				return
		elif rule == "Rescue Draw" and not any(game.draw_piles):
			options = "\n".join(f"{n + 1}. {card}" for n, card in enumerate(game.destroyed_pile))
			pick = simpledialog.askinteger("Rescue Draw", f"The draw pile is gone. Take 1 card from the destroyed pile:\n{options}", minvalue=1, maxvalue=len(game.destroyed_pile), parent=self.root)
			if pick is None:
				return
			value = pick - 1
		elif rule == "Soul Swap":
			targets = game.soul_swap_targets(current)
			names = "\n".join(f"{number + 1}. {game.players[index].name}" for number, index in enumerate(targets))
			pick = simpledialog.askinteger("Soul Swap", f"Choose a player to swap all cards with:\n{names}", minvalue=1, maxvalue=len(targets), parent=self.root)
			if pick is None:
				return
			target = targets[pick - 1]
		try:
			game.use_god_rule(current, rule, value=value, target_index=target)
		except ValueError as error:
			self.notice = str(error)
		else:
			self.notice = f"{self._you(current)} used God of Jujutsu: {rule} is active this round."
			if rule == "Soul Swap":
				self.notice = f"{self._you(current)} soul swapped with {game.players[target].name} using God of Jujutsu."
			elif rule == "Reveal":
				self.notice = f"{self._you(current)} used God of Jujutsu: Reveal."
				self._resolve_pending_reveals()
			elif rule == "Rescue Draw":
				self.notice = f"{self._you(current)} used God of Jujutsu: Rescue Draw."
		self.selected_card = None
		self.selected_pile = None
		self._render()

	def _use_binding_vow(self):
		game = self.game
		current = game.current_player
		if game.players[current].is_bot or not game.can_use_binding_vow(current):
			return
		cards = game.binding_vow_cards(current)
		options = "\n".join(f"{number + 1}. {card}" for number, card in enumerate(cards))
		choice = simpledialog.askinteger(
			"Binding Vow",
			f"This passes your turn. Choose the card that will play as a King:\n{options}",
			minvalue=1,
			maxvalue=len(cards),
			parent=self.root,
		)
		if choice is None:
			return
		card = cards[choice - 1]
		try:
			game.use_binding_vow(current, choice - 1)
		except ValueError as error:
			self.notice = str(error)
			self._render()
			return
		self.notice = f"{self._you(current)} used Binding Vow and passed; {card} will play as a King."
		self.selected_card = None
		self.selected_pile = None
		self.human_has_played = False
		self._render()
		if game.winner is None:
			self.root.after(250, self._run_bot_turns)

	def _evolve_selected_ability(self):
		if self.game is None or self.game.players[self.game.current_player].is_bot or self.game.cards_played_this_turn != 0:
			return
		current = self.game.current_player
		joker_index = next((index for index, card in enumerate(self.game.players[current].hand) if card.rank == "Joker"), None)
		if joker_index is None:
			return
		player = self.game.players[current]
		eligible = [
			track for track in character_ability_tracks(player.character)
			if "evolution" in track
			and not player.ability_states[track["ability"]]["removed"]
			and not player.ability_states[track["ability"]]["evolved"]
		]
		if not eligible:
			return
		selected_track = eligible[0]
		if len(eligible) > 1:
			choices = "\n".join(
				f"{index + 1}. {track['ability']} to {track['evolution']['ability']}"
				for index, track in enumerate(eligible)
			)
			choice = simpledialog.askinteger(
				"Choose an ability to evolve",
				f"This ends your turn. Choose an ability:\n{choices}",
				minvalue=1,
				maxvalue=len(eligible),
				parent=self.root,
			)
			if choice is None:
				return
			selected_track = eligible[choice - 1]
		current = self.game.current_player
		try:
			self.game.evolve_ability(current, joker_index, selected_track["ability"])
		except ValueError as error:
			self.notice = str(error)
			self._render()
			return
		self.notice = f"{self._you(current)} evolved {selected_track['ability']} into {selected_track['evolution']['ability']}; a Joker was deleted and the turn ended."
		self.selected_card = None
		self.selected_pile = None
		self.human_has_played = False
		self._render()
		if self.game.winner is None:
			self.root.after(250, self._run_bot_turns)

	def _play_selected(self):
		game = self.game
		current = game.current_player
		player = game.players[current]
		if player.is_bot:
			return
		you = self._you(current)
		source, cards = _current_source(game, player)
		if source is None or self.selected_card is None or self.selected_pile is None:
			return
		card = cards[self.selected_card]
		if source == "face_down":
			played_card, played = game.play_face_down(current, self.selected_card, self.selected_pile, joker_value=14)
			if played:
				self.notice = f"{you} revealed and played {_played_card_label(played_card, 14)}."
			else:
				self.notice = f"{you} revealed {played_card} and picked up both discard piles."
			if player.pending_world_slashes and game.winner is None:
				self._resolve_pending_world_slashes()
			if player.pending_limitless_effects and game.winner is None:
				self._resolve_pending_limitless_effects()
			if game.pending_quick_grabs and game.winner is None:
				game.resolve_bot_quick_grabs()
			self._finish_human_turn()
			return
		joker_value = None
		if card.rank == "Joker":
			joker_value = simpledialog.askinteger("Joker value", "Choose the Joker's value (2-14):", minvalue=2, maxvalue=14, parent=self.root)
			if joker_value is None:
				return
		first_move = game.cards_played_this_turn == 0
		played_card = game.play(current, source, self.selected_card, self.selected_pile, joker_value)
		self.selected_card = None
		self.selected_pile = None
		if played_card is None:
			self.notice = f"Illegal first play. {you} picked up both discard piles." if first_move else "Illegal follow-up blocked. The piles were left unchanged."
			self._finish_human_turn()
			return
		self.human_has_played = True
		self.notice = f"{you} played {_played_card_label(played_card, joker_value)}."
		if game.winner is not None:
			self._render()
		elif source == "hand" and game.last_drawn_cards:
			self.notice += f" Drew {len(game.last_drawn_cards)} card(s)."
		self._render()
		if player.pending_world_slashes and game.winner is None:
			self._resolve_pending_world_slashes()
		if player.pending_limitless_effects and game.winner is None:
			self._resolve_pending_limitless_effects()
		if game.pending_quick_grabs and game.winner is None:
			game.resolve_bot_quick_grabs()

	def _take_piles_and_end(self):
		current = self.game.current_player
		if self.game.players[current].is_bot:
			return
		self.game.take_discard_piles(current)
		self.notice = f"No legal plays. {self._you(current)} picked up both discard piles."
		self._finish_human_turn()

	def _end_human_turn(self):
		current = self.game.current_player
		player = self.game.players[current]
		if (
			player.is_bot
			or not self.human_has_played
			or player.pending_world_slashes > 0
			or player.pending_limitless_effects
			or self._human_quick_grab_target() is not None
			or self.game.enchain_must_keep_playing(current)
		):
			return
		self._finish_human_turn()

	def _finish_human_turn(self):
		if self.game.winner is not None:
			self._render()
			return
		self.game.end_turn()
		self.human_has_played = self.game.cards_played_this_turn > 0
		self.selected_card = None
		self.selected_pile = None
		self.root.after(250, self._run_bot_turns)

	def _skip_to_results(self):
		if not all(self.game.player_has_finished(index) for index in self._human_indices()):
			return
		self.fast_forward = True
		self.notice = "Fast-forwarding bot turns..."
		self._run_bot_turns()

	def _run_bot_turns(self):
		game = self.game
		if game.winner is not None:
			self.fast_forward = False
			self._render()
			return
		if self._human_quick_grab_target() is not None:
			self.notice = "A card is available for Quick Grab."
			self._render()
			return
		if not game.players[game.current_player].is_bot:
			if game.player_has_finished(game.current_player):
				game.end_turn()
				self.root.after(0 if self.fast_forward else 150, self._run_bot_turns)
				return
			self.human_has_played = game.cards_played_this_turn > 0
			name = game.players[game.current_player].name
			self.notice = f"{name}'s turn. Select a card and discard pile." if self._is_hot_seat() else "Your turn. Select a card and discard pile."
			self._render()
			return
		player_index = game.current_player
		player = game.players[player_index]
		game.refill_player_hand(player_index)
		if game.cards_played_this_turn == 0:
			joker_index = next((index for index, card in enumerate(player.hand) if card.rank == "Joker"), None)
			evolvable = [
				track for track in character_ability_tracks(player.character)
				if "evolution" in track
				and not player.ability_states[track["ability"]]["removed"]
				and not player.ability_states[track["ability"]]["evolved"]
			]
			if joker_index is not None and evolvable:
				game.evolve_ability(player_index, joker_index, evolvable[0]["ability"])
				self.notice = f"{player.name} evolved {evolvable[0]['ability']} into {evolvable[0]['evolution']['ability']} and ended their turn."
				self._render()
				self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)
				return
		source, cards = _current_source(game, player)
		if source is None:
			game.end_turn()
			self.root.after(0 if self.fast_forward else 150, self._run_bot_turns)
			return
		if source == "face_down":
			card_index = game.rng.randrange(len(cards))
			card = cards[card_index]
			joker_value = 14 if card.rank == "Joker" else None
			legal_piles = [
				index for index in range(2)
				if game.can_play(card, index, joker_value=joker_value)
			]
			if legal_piles:
				pile_index = min(
					legal_piles,
					key=lambda index: (game.pile_values[index] if game.discard_piles[index] else 0, len(game.discard_piles[index])),
				)
				card, _ = game.play_face_down(player_index, card_index, pile_index, joker_value=14)
				self.notice = f"{player.name} revealed and played {_played_card_label(card, 14)}."
			else:
				pile_index = min(range(2), key=lambda index: len(game.discard_piles[index]))
				card, _ = game.play_face_down(player_index, card_index, pile_index, joker_value=14)
				self.notice = f"{player.name} revealed {card} and picked up both discard piles."
				if player.pending_world_slashes and game.winner is None:
					game.resolve_bot_world_slashes(player_index)
			if player.pending_world_slashes and game.winner is None:
				game.resolve_bot_world_slashes(player_index)
			if player.pending_limitless_effects and game.winner is None:
				game.resolve_bot_limitless_effects(player_index)
			if game.pending_quick_grabs:
				game.resolve_bot_quick_grabs()
			game.end_turn()
			self._render()
			self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)
			return

		god_rule = game.bot_god_choice(player_index, cards)
		if god_rule is not None:
			game.use_god_rule(player_index, god_rule)
		if game.cards_played_this_turn == 0:
			lapse_notes = game.bot_lapse_actions(player_index)
			if lapse_notes:
				self.notice = f"{player.name} {' and '.join(lapse_notes)}."
				if game.pending_reveals:
					self._resolve_pending_reveals()
				source, cards = _current_source(game, player)
		options = _bot_legal_options(game, cards)
		if not options:
			cleave_pile = game.bot_cleave_choice(player_index, cards)
			if cleave_pile is not None:
				try:
					game.use_cleave(player_index, cleave_pile)
					self.notice = f"{player.name} used Cleave on pile {cleave_pile + 1} to open up a play."
					self._render()
					self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)
					return
				except ValueError:
					pass
			vow_index = game.bot_binding_vow_choice(player_index) if game.cards_played_this_turn == 0 else None
			if vow_index is not None:
				game.use_binding_vow(player_index, vow_index)
				self.notice = f"{player.name} had no legal play and used Binding Vow instead of picking up the piles."
				self._render()
				self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)
				return
			if game.cards_played_this_turn == 0:
				game.take_discard_piles(player_index)
				self.notice = f"{player.name} had no legal play and picked up both piles."
			else:
				self.notice = f"{player.name} has no legal follow-up play."
			game.end_turn()
			self._render()
			self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)
			return

		card_index, pile_index = _bot_choose_play(game, cards, options)
		joker_value = 14 if cards[card_index].rank == "Joker" else None
		card = game.play(player_index, source, card_index, pile_index, joker_value=joker_value)
		if card is None:
			self.notice = f"{player.name} attempted an illegal play."
			game.end_turn()
		else:
			self.notice = f"{player.name} played {_played_card_label(card, joker_value)}."
			if player.pending_world_slashes and game.winner is None:
				game.resolve_bot_world_slashes(player_index)
			if player.pending_limitless_effects and game.winner is None:
				game.resolve_bot_limitless_effects(player_index)
			if game.pending_quick_grabs:
				game.resolve_bot_quick_grabs()
			if game.winner is not None:
				self.fast_forward = False
				self._render()
				return
		self._render()
		self.root.after(0 if self.fast_forward else 300, self._run_bot_turns)


def main():
	root = tk.Tk()
	PalaceApp(root)
	root.mainloop()


if __name__ == "__main__":
	main()
