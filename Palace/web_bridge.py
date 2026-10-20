"""Browser controller for the Palace game (runs in Pyodide; mirrors the Tkinter PalaceApp).

JS calls new_game / get_state / act / bot_step and exchanges JSON strings. Prompts use
the Ask pattern: a handler asks for choices through Answers; when an answer is missing
an Ask is raised, JS shows the question and re-sends the action with the extra answer.
Handlers therefore ask everything before they change the game.
"""

import json

import palacegames as pg
from palacegames import (
	CHARACTERS, DOMAIN_CLASHING_RULE, DOMAIN_TAG, GOD_RULES, MAX_PLAYERS, MULTI_USE_RULES,
	RANDOM_CHARACTER, RANKS, SIMPLE_DOMAIN_REFINEMENT, VALUES, PalaceGame,
	character_ability_tracks, validate_game_settings,
)


class Ask(Exception):
	def __init__(self, title, options):
		super().__init__(title)
		self.title = title
		self.options = list(options)


class Answers:
	def __init__(self, values):
		self.values = list(values or [])
		self.position = 0

	def ask(self, title, options):
		options = list(options)
		if self.position < len(self.values):
			value = self.values[self.position]
			self.position += 1
			if not 0 <= value < len(options):
				raise ValueError("That choice is no longer available")
			return value
		raise Ask(title, options)

	def joker_value(self, title="Joker value"):
		return self.ask(title, [f"{rank}" for rank in RANKS]) + 2


class Session:
	def __init__(self):
		self.game = None
		self.admin = False
		self.reset()

	def reset(self):
		self.game = None
		self.setup_queue = []
		self.setup_player = 0
		self.setup_complete = False
		self.human_has_played = False
		self.last_human = 0
		self.notice = ""
		self.popup = None
		self.auto_end = False
		self.draw_pref = None


S = Session()


def _label(card):
	return str(card)


def _card(card):
	return {"label": str(card), "rank": card.rank, "suit": card.suit}


def _played_label(card, joker_value=None):
	return pg._played_card_label(card, joker_value)


def _humans():
	return [index for index, player in enumerate(S.game.players) if not player.is_bot]


def _hot_seat():
	return len(_humans()) > 1


def _you(index):
	return S.game.players[index].name if _hot_seat() else "You"


def _qg_target():
	game = S.game
	if not game.pending_quick_grabs:
		return None
	return next((i for i in game.pending_quick_grabs[0]["targets"] if not game.players[i].is_bot), None)


def _reveal_target():
	return next((i for i in S.game.pending_reveals if not S.game.players[i].is_bot), None)


def _viewer():
	game = S.game
	grabber = _qg_target()
	if grabber is not None:
		return grabber
	revealer = _reveal_target()
	if revealer is not None:
		return revealer
	if not S.setup_complete:
		return S.setup_player
	if not game.players[game.current_player].is_bot:
		S.last_human = game.current_player
	return S.last_human


def _pending_effects(player):
	return bool(player.pending_world_slashes or player.pending_limitless_effects or _qg_target() is not None)


def _draw_hook(player_index, options):
	game = S.game
	pref, S.draw_pref = S.draw_pref, None
	return pref if pref in options else None


def _needs_draw_choice():
	game = S.game
	current = game.current_player
	player = game.players[current]
	return (
		S.setup_complete and game.winner is None and not player.is_bot
		and game.cards_played_this_turn == 0 and len(player.hand) < 3
		and any(game.draw_piles) and S.draw_pref is None
		and game.effective_ability(current, "Six Eyes") == "Mastered Six Eyes"
		and not game.player_has_finished(current)
	)


def _sync_hand():
	game = S.game
	if S.setup_complete and game.winner is None and not game.player_has_finished(game.current_player):
		if not _needs_draw_choice():
			game.refill_player_hand(game.current_player)


def _finish_turn():
	game = S.game
	S.auto_end = False
	if game.winner is not None:
		return
	game.end_turn()
	S.human_has_played = game.cards_played_this_turn > 0


def _after_play(player_index):
	game = S.game
	if game.pending_quick_grabs and game.winner is None:
		game.resolve_bot_quick_grabs()


def auto_progress():
	"""Turn ends the GUI performs automatically for a human player."""
	game = S.game
	for _ in range(50):
		if game is None or not S.setup_complete or game.winner is not None:
			return
		current = game.current_player
		player = game.players[current]
		if player.is_bot or _needs_draw_choice() or _reveal_target() is not None:
			return
		_sync_hand()
		if S.auto_end and not _pending_effects(player) and not game.enchain_must_keep_playing(current):
			_finish_turn()
			continue
		if _qg_target() is not None or _pending_effects(player):
			return
		source, cards = pg._current_source(game, player)
		if source is None:
			if game.player_has_finished(current) or not S.human_has_played:
				_finish_turn()
				continue
			return
		if source != "face_down" and not pg._legal_options(game, cards):
			if game.cards_played_this_turn == 0 and game.enchain_return is not None:
				S.notice = "No legal play during Enchain. Use an ability or end the turn to resume the interrupted turn."
			elif game.cards_played_this_turn == 0:
				S.notice = f"No legal plays. {_you(current)} can use an ability or pick up the discard piles."
			else:
				S.notice = "No legal follow-up plays. End your turn to continue."
		return


# ---------------------------------------------------------------- setup

def get_catalog():
	characters = []
	for name in CHARACTERS:
		tracks = []
		for track in character_ability_tracks(name):
			entry = {"ability": track["ability"], "description": track["description"], "rules": list(track.get("rules", ()))}
			if "evolution" in track:
				evo = track["evolution"]
				entry["evolution"] = {"ability": evo["ability"], "description": evo["description"], "rules": list(evo.get("rules", ()))}
			tracks.append(entry)
		characters.append({"name": name, "tracks": tracks})
	return json.dumps({
		"characters": characters,
		"rules": MULTI_USE_RULES,
		"domain_rule": DOMAIN_CLASHING_RULE,
		"max_players": MAX_PLAYERS,
		"defaults": {"players": pg.DEFAULT_PLAYER_COUNT, "decks": pg.DEFAULT_DECK_COUNT, "jokers": pg.DEFAULT_JOKER_COUNT},
		"random": RANDOM_CHARACTER,
	})


def new_game(settings_json):
	settings = json.loads(settings_json)
	try:
		rows = settings["players"]
		decks = int(settings["decks"])
		jokers = int(settings["jokers"])
		if not 2 <= len(rows) <= MAX_PLAYERS:
			raise ValueError(f"Players must be between 2 and {MAX_PLAYERS}")
		validate_game_settings(len(rows), decks, jokers)
		bot_flags = [row["type"] == "Bot" for row in rows]
		if all(bot_flags):
			raise ValueError("At least one player must be a human")
		characters = [None if row["character"] == RANDOM_CHARACTER else row["character"] for row in rows]
		game = PalaceGame(bot_flags=bot_flags, characters=characters, deck_count=decks, joker_count=jokers, start_with_joker=bool(settings.get("start_joker")))
	except (ValueError, KeyError, TypeError) as error:
		return json.dumps({"error": str(error)})
	S.reset()
	S.game = game
	game.draw_choice_hook = _draw_hook
	humans = []
	for index, player in enumerate(game.players):
		if not player.is_bot:
			humans.append(index)
			continue
		best = sorted(
			range(len(player.hand)),
			key=lambda i: 15 if player.hand[i].rank == "Joker" else VALUES[player.hand[i].rank],
			reverse=True,
		)[:3]
		game.choose_face_up(index, best)
	S.setup_queue = humans
	S.setup_player = humans[0]
	S.last_human = humans[0]
	S.notice = "Choose three cards to keep face-up for later."
	return get_state()


# ---------------------------------------------------------------- state

def _player_tags(index):
	game = S.game
	player = game.players[index]
	tags = []
	if player.character == "Sukuna":
		tags.append(f"Cut Meter {player.cut_meter}/9")
	if game.effective_ability(index, "Limitless Barrier") == "Perfected Limitless":
		tags.append("I-T permanent")
	elif game.player_has_immunity(index):
		tags.append("I-T active")
	if player.is_eliminated:
		tags.append("ELIMINATED")
	elif S.setup_complete and game.player_has_finished(index):
		tags.append("Finished")
	if player.simple_domain_active:
		tags.append(f"Simple Domain (refinement {SIMPLE_DOMAIN_REFINEMENT})")
	domain = game.player_domain(index)
	if domain:
		text = f"{domain['name']}: refinement {domain['refinement']}"
		if game.is_clashing():
			text += " (clashing)"
		if domain.get("rounds_left") is not None:
			text += f", {domain['rounds_left']} round(s) left"
		tags.append(text)
	return tags


def _buttons(viewer):
	game = S.game
	buttons = []
	me = game.players[viewer]
	is_current = game.current_player == viewer

	def add(kind, label, enabled=True, info=False):
		buttons.append({"id": kind, "label": label, "enabled": enabled, "info": info})

	cleave = game.cleave_ability_name(viewer)
	if cleave is not None:
		remaining = game.ability_uses_remaining(viewer, "Cleave")
		add("cleave", f"Use {cleave} ({remaining} left) - pick a discard pile first", is_current and remaining > 0)
	world = game.effective_ability(viewer, "World Cutting Slash")
	if world in ("World Cutting Slash", "Waffle Cutting Slash"):
		add("info", f"{world} active", False, True)
	hollow = game.effective_ability(viewer, "Hollow Purple")
	if hollow in ("Hollow Purple", "Max Purple"):
		add("info", f"{hollow} active", False, True)
	if any(game.can_use_enchain(i) for i in _humans()):
		add("enchain", "Enchain / Rule Workaround (once per game)")
	if is_current and game.can_use_card_swapping(viewer):
		add("card_swap", f"Card Swapping ({'/'.join(sorted(game.swap_ranks(viewer)))}s)")
	if is_current and game.can_use_rescue_draw(viewer):
		add("rescue", "Rescue Draw")
	if is_current and game.can_use_six_eyes(viewer):
		add("six_eyes", "Six Eyes")
	if is_current and game.can_use_full_hand(viewer):
		add("full_hand", "Full Hand")
	if (game.domains and (game.domain_options(viewer) or game.can_domain_draw(viewer) or game.can_joker_domain(viewer))) or (
		is_current and game.domain_options(viewer)
	):
		add("domain", "Domain (clash)" if game.domains else "Domain")
	if game.can_use_simple_domain(viewer):
		add("simple_domain", "Simple Domain (once per game)")
	elif game.can_simple_cleanse(viewer):
		add("simple_domain", "Simple Domain: discard a card to remove an effect")
	if is_current and game.can_choose_god_rule(viewer):
		add("god", "God of Jujutsu (choose a rule for this round)")
	if game.god_rule(viewer):
		rule = game.god_rule(viewer)
		extra = f" ({RANKS[me.god_grab_value - 2]})" if rule in ("Quick Grab", "Card Swapping") else ""
		add("info", f"God of Jujutsu: {rule}{extra} this round", False, True)
	if is_current and game.can_use_binding_vow(viewer):
		add("vow", "Binding Vow (pass turn, one card plays as a King)")
	if game.is_vow_card(viewer, me.vow_card):
		add("info", f"Binding Vow: {me.vow_card} plays as a King", False, True)
	if is_current and me.pending_world_slashes:
		add("resolve_slash", f"Resolve World Cutting Slash ({me.pending_world_slashes})")
	if is_current and me.pending_limitless_effects:
		add("resolve_limitless", f"Resolve Limitless effect ({len(me.pending_limitless_effects)})")
	if game.pending_quick_grabs and viewer in game.pending_quick_grabs[0]["targets"]:
		add("quick_grab", "Quick Grab the card")
		add("decline_quick_grab", "Decline Quick Grab")
	eligible = _evolvable(viewer)
	if is_current and game.cards_played_this_turn == 0 and eligible and any(c.rank == "Joker" for c in me.hand):
		add("evolve", "Evolve ability (ends turn): " + ", ".join(t["evolution"]["ability"] for t in eligible))
	return buttons


def _evolvable(index):
	player = S.game.players[index]
	return [
		track for track in character_ability_tracks(player.character)
		if "evolution" in track
		and not player.ability_states[track["ability"]]["removed"]
		and not player.ability_states[track["ability"]]["evolved"]
	]


def get_state():
	game = S.game
	if game is None:
		return json.dumps({"phase": "none"})
	_sync_hand()
	viewer = _viewer()
	humans = _humans()
	state = {
		"notice": S.notice,
		"popup": S.popup,
		"round": game.round_number,
		"turn": game.turn_number,
		"current": game.current_player,
		"viewer": viewer,
		"hot_seat": _hot_seat(),
		"draw_piles": [len(p) for p in game.draw_piles],
		"discards": [
			{
				"top": _played_label(pile[-1], game.pile_values[i]) if pile else None,
				"count": len(pile),
				"cards": [str(c) for c in pile],
			}
			for i, pile in enumerate(game.discard_piles)
		],
		"destroyed": [str(c) for c in game.destroyed_pile],
		"deleted": [str(c) for c in game.deleted_pile],
		"log": game.action_log[-80:],
	}
	S.popup = None
	players = []
	for index, player in enumerate(game.players):
		seen = [str(c) for c in game.known_cards_of(viewer, index)] if index != viewer else []
		seen_down = [
			{"slot": slot + 1, "label": str(c)} for slot, c in enumerate(player.face_down) if game.is_known(viewer, c)
		] if index == viewer else []
		players.append({
			"name": player.name,
			"character": player.character,
			"bot": player.is_bot,
			"current": index == game.current_player and game.winner is None,
			"hand": len(player.hand),
			"face_down": len(player.face_down),
			"face_up": [_card(c) for c in player.face_up],
			"revealed": [str(c) for c in game.revealed_cards(index)],
			"seen": seen,
			"seen_down": seen_down,
			"evolved": [name for name, s in player.ability_states.items() if s["evolved"]],
			"removed": [name for name, s in player.ability_states.items() if s["removed"]],
			"tags": _player_tags(index),
		})
	state["players"] = players
	if game.winner is not None:
		state["phase"] = "over"
		state["winner"] = game.players[game.winner].name
		state["standings"] = [
			{
				"rank": r["rank"],
				"name": game.players[r["player_index"]].name,
				"status": {"last remaining": "last player standing", "last place (Cut Meter)": "tied last place (Cut Meter)"}.get(r["status"], "finished"),
				"round": r["round"],
				"turn": r["turn"],
			}
			for r in game.finish_order
		]
		return json.dumps(state)
	me = game.players[viewer]
	if not S.setup_complete:
		state["phase"] = "setup"
		state["me"] = {"name": me.name, "hand": [_card(c) for c in me.hand], "face_up": [], "face_down": [], "source": "setup"}
		return json.dumps(state)
	state["phase"] = "play"
	is_current = game.current_player == viewer
	source, cards = pg._current_source(game, me) if is_current else (None, [])
	me_info = {
		"name": me.name,
		"hand": [_card(c) for c in me.hand],
		"face_up": [_card(c) for c in me.face_up],
		"face_down": [{"known": str(c) if game.is_known(viewer, c) else None} for c in me.face_down],
		"source": source,
		"pending": _pending_effects(me) if is_current else False,
		"can_end": is_current and not _pending_effects(me) and not game.enchain_must_keep_playing(viewer)
		and (S.human_has_played or game.cards_played_this_turn > 0 or (game.enchain_return is not None and source != "face_down")),
		"can_pickup": is_current and not _pending_effects(me) and not game.enchain_must_keep_playing(viewer) and not game.pending_reveals,
		"is_current": is_current,
	}
	if _reveal_target() == viewer:
		me_info["mode"] = "reveal"
	state["me"] = me_info
	state["buttons"] = _buttons(viewer)
	state["all_humans_finished"] = all(game.player_has_finished(i) for i in humans)
	state["needs_bot"] = _needs_bot()
	if _needs_draw_choice():
		state["draw_choice"] = [
			{"pile": p, "depth": d, "label": str(game.draw_piles[p][-1 - d])}
			for p in range(2) for d in range(min(3, len(game.draw_piles[p])))
		]
	return json.dumps(state)


def _needs_bot():
	game = S.game
	if game is None or not S.setup_complete or game.winner is not None:
		return False
	if _qg_target() is not None or _reveal_target() is not None:
		return False
	current = game.current_player
	return game.players[current].is_bot or game.player_has_finished(current)


# ---------------------------------------------------------------- actions

def act(action_json):
	action = json.loads(action_json)
	game = S.game
	if game is None:
		return get_state()
	answers = Answers(action.get("answers"))
	handler = HANDLERS.get(action.get("type"))
	if handler is None:
		return get_state()
	try:
		handler(action, answers)
	except Ask as ask:
		return json.dumps({"ask": {"title": ask.title, "options": ask.options}})
	except ValueError as error:
		S.notice = str(error)
	auto_progress()
	return get_state()


def _human_current():
	game = S.game
	if game.winner is not None or not S.setup_complete:
		return None
	player = game.players[game.current_player]
	return None if player.is_bot else game.current_player


def h_setup(action, answers):
	picks = sorted(set(action["cards"]))
	if S.setup_complete or len(picks) != 3:
		return
	game = S.game
	game.choose_face_up(S.setup_player, picks)
	position = S.setup_queue.index(S.setup_player)
	if position + 1 < len(S.setup_queue):
		S.setup_player = S.setup_queue[position + 1]
		S.notice = "Choose three cards to keep face-up for later."
		return
	S.setup_complete = True
	S.notice = "Select a card and a discard pile, then play."


def h_play(action, answers):
	game = S.game
	current = _human_current()
	if current is None or _needs_draw_choice() or game.pending_reveals:
		return
	player = game.players[current]
	source, cards = pg._current_source(game, player)
	card_index, pile_index = action["card"], action["pile"]
	if source is None or not 0 <= card_index < len(cards) or pile_index not in (0, 1) or _pending_effects(player):
		return
	you = _you(current)
	card = cards[card_index]
	if source == "face_down":
		played_card, played = game.play_face_down(current, card_index, pile_index, joker_value=14)
		if played:
			S.notice = f"{you} revealed and played {_played_label(played_card, 14)}."
			S.auto_end = True
		else:
			S.notice = f"{you} revealed {played_card} and picked up both discard piles."
			_after_play(current)
			_finish_turn()
			return
		_after_play(current)
		return
	joker_value = answers.joker_value() if card.rank == "Joker" else None
	first_move = game.cards_played_this_turn == 0
	played_card = game.play(current, source, card_index, pile_index, joker_value)
	if played_card is None:
		S.notice = f"Illegal first play. {you} picked up both discard piles." if first_move else "Illegal follow-up blocked. The piles were left unchanged."
		_finish_turn()
		return
	S.human_has_played = True
	S.notice = f"{you} played {_played_label(played_card, joker_value)}."
	if source == "hand" and game.last_drawn_cards:
		S.notice += f" Drew {len(game.last_drawn_cards)} card(s)."
	_after_play(current)


def h_take_piles(action, answers):
	current = _human_current()
	game = S.game
	if current is None or _pending_effects(game.players[current]) or game.pending_reveals or game.enchain_must_keep_playing(current):
		return
	game.take_discard_piles(current)
	S.notice = f"{_you(current)} picked up both discard piles."
	_finish_turn()


def h_end_turn(action, answers):
	current = _human_current()
	if current is None:
		return
	game = S.game
	player = game.players[current]
	if not S.human_has_played and game.cards_played_this_turn == 0 and game.enchain_return is None:
		return
	if _pending_effects(player) or game.enchain_must_keep_playing(current):
		return
	_finish_turn()


def h_draw_pref(action, answers):
	if not _needs_draw_choice() and S.game.effective_ability(S.game.current_player, "Six Eyes") != "Mastered Six Eyes":
		return
	S.draw_pref = (action["pile"], action["depth"])
	S.notice = "Mastered Six Eyes: chosen card will be drawn."


def h_cleave(action, answers):
	game = S.game
	current = _human_current()
	pile_index = action.get("pile")
	if current is None or pile_index not in (0, 1) or game.cleave_ability_name(current) is None:
		return
	player = game.players[current]
	available = len(player.hand) + len(player.face_up) + len(player.face_down)
	kwargs = {}
	if (
		game.effective_ability(current) == "Spider Net Cleave"
		and len(game.discard_piles[pile_index]) == 1
		and available >= 2
	):
		taken = []
		indices, sources, jokers = [], [], []
		for pile_number in range(2):
			choices = [
				(source, index)
				for source in ("hand", "face_up", "face_down")
				for index in range(len(getattr(player, source)))
				if (source, index) not in taken
			]
			labels = [
				f"{source.replace('_', ' ')}: " + ("Face-down card" if source == "face_down" else str(getattr(player, source)[index]))
				for source, index in choices
			]
			pick = answers.ask(f"Spider Net Cleave: choose a card for discard pile {pile_number + 1}", labels)
			source, index = choices[pick]
			card = getattr(player, source)[index]
			joker = answers.joker_value(f"Joker value for discard pile {pile_number + 1}") if card.rank == "Joker" else None
			taken.append((source, index))
			indices.append(index)
			sources.append(source)
			jokers.append(joker)
		kwargs = {"replacement_indices": tuple(indices), "replacement_joker_values": tuple(jokers), "replacement_sources": tuple(sources)}
	card = game.use_cleave(current, pile_index, **kwargs)
	S.notice = (
		f"Spider Net Cleave destroyed both piles, moved {card} to Destroyed, and replaced both piles with your chosen cards."
		if kwargs else f"Cleave destroyed {card}."
	)


def h_enchain(action, answers):
	game = S.game
	users = [i for i in _humans() if game.can_use_enchain(i)]
	if not users:
		return
	viewer = _viewer()
	if viewer in users:
		user = viewer
	elif len(users) == 1:
		user = users[0]
	else:
		user = users[answers.ask("Who is using Enchain?", [game.players[i].name for i in users])]
	targets = game.enchain_targets(user)
	pick = answers.ask(
		f"{game.players[user].name}: choose a player to soul swap with. You must then play 2 cards",
		[game.players[i].name for i in targets],
	)
	game.use_enchain(user, targets[pick])
	S.notice = f"{_you(user)} soul swapped with {game.players[targets[pick]].name}. Play 2 cards in a row."
	S.last_human = user
	S.human_has_played = False


def _swap_label(target):
	owner, zone, _ = target
	if owner >= 0:
		return f"{S.game.players[owner].name}'s {zone.replace('_', ' ')}"
	return "destroyed pile" if zone == "destroyed" else f"discard pile {int(zone[-1]) + 1}"


def h_card_swap(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.can_use_card_swapping(current):
		return
	player = game.players[current]
	own, theirs = game.card_swap_options(current)
	own_pick = answers.ask("Card Swapping: choose your card to give away", [f"{getattr(player, z)[i]} ({z.replace('_', ' ')})" for z, i in own])
	their_pick = answers.ask("Card Swapping: choose a visible card to take", [f"{game.swap_target_card(t)} - {_swap_label(t)}" for t in theirs])
	game.card_swap(current, *own[own_pick], *theirs[their_pick])
	S.notice = f"{_you(current)} swapped a card and everyone else must reveal one."


def h_reveal(action, answers):
	game = S.game
	index = _reveal_target()
	if index is None:
		return
	game.reveal_card(index, action["card"])
	S.notice = f"{game.players[index].name} revealed a card."


def h_six_eyes(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.can_use_six_eyes(current):
		return
	options = game.six_eyes_options(current)
	labels = [
		f"One of your face-down cards (slot {i + 1})" if kind == "face_down" else f"{game.players[i].name}'s hand"
		for kind, i in options
	]
	pick = answers.ask("Six Eyes: view a face-down card or someone's hand", labels)
	cards = game.use_six_eyes(current, *options[pick])
	S.popup = {"text": "You will remember these cards.", "cards": [str(c) for c in cards]}
	S.notice = f"{_you(current)} used Six Eyes."


def h_full_hand(action, answers):
	current = _human_current()
	if current is None or not S.game.can_use_full_hand(current):
		return
	S.game.use_full_hand(current)
	S.notice = f"{_you(current)} picked up all face-up and face-down cards with Full Hand."


def h_rescue(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.can_use_rescue_draw(current):
		return
	destroyed_index = None
	if not any(game.draw_piles):
		destroyed_index = answers.ask("Rescue Draw: the draw pile is gone. Take 1 card from the destroyed pile", [str(c) for c in game.destroyed_pile])
	else:
		if answers.ask("Rescue Draw: draw 2 cards from the draw pile? (once every 2 rounds)", ["Yes, draw 2", "Cancel"]) != 0:
			return
	game.use_rescue_draw(current, destroyed_index)
	S.notice = f"{_you(current)} used Rescue Draw."


def h_god(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.can_choose_god_rule(current):
		return
	player = game.players[current]
	rules = [
		rule for rule in GOD_RULES
		if (rule != "Soul Swap" or game.cards_played_this_turn == 0 and game.soul_swap_targets(current))
		and (rule != "Rescue Draw" or game._rescue_ready(current))
		and (rule != "Full Hand" or player.face_up or player.face_down)
	]
	rule = rules[answers.ask("God of Jujutsu: choose 1 multi use rule to use this round", rules)]
	value = target = None
	if rule in ("Quick Grab", "Card Swapping"):
		value = answers.joker_value(f"{rule}: which card value?")
	elif rule == "Rescue Draw" and not any(game.draw_piles):
		value = answers.ask("Rescue Draw: take 1 card from the destroyed pile", [str(c) for c in game.destroyed_pile])
	elif rule == "Soul Swap":
		targets = game.soul_swap_targets(current)
		target = targets[answers.ask("Soul Swap: choose a player to swap all cards with", [game.players[i].name for i in targets])]
	game.use_god_rule(current, rule, value=value, target_index=target)
	if rule == "Soul Swap":
		S.notice = f"{_you(current)} soul swapped with {game.players[target].name} using God of Jujutsu."
	else:
		S.notice = f"{_you(current)} used God of Jujutsu: {rule} is active this round."


def h_vow(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.can_use_binding_vow(current):
		return
	cards = game.binding_vow_cards(current)
	pick = answers.ask("Binding Vow: this passes your turn. Choose the card that will play as a King", [str(c) for c in cards])
	game.use_binding_vow(current, pick)
	S.notice = f"{_you(current)} used Binding Vow and passed; {cards[pick]} will play as a King."
	S.human_has_played = False


def h_evolve(action, answers):
	game = S.game
	current = _human_current()
	if current is None or game.cards_played_this_turn != 0:
		return
	player = game.players[current]
	joker_index = next((i for i, c in enumerate(player.hand) if c.rank == "Joker"), None)
	eligible = _evolvable(current)
	if joker_index is None or not eligible:
		return
	track = eligible[0]
	if len(eligible) > 1:
		track = eligible[answers.ask("Evolve (ends your turn): choose an ability", [f"{t['ability']} to {t['evolution']['ability']}" for t in eligible])]
	game.evolve_ability(current, joker_index, track["ability"])
	S.notice = f"{_you(current)} evolved {track['ability']} into {track['evolution']['ability']}; a Joker was deleted and the turn ended."
	S.human_has_played = False
	S.auto_end = False


def h_simple_domain(action, answers):
	game = S.game
	viewer = _viewer()
	if game.can_use_simple_domain(viewer):
		if answers.ask("Simple Domain: gives refinement 3, once per game, not offensive and lets no one clash", ["Activate", "Cancel"]) != 0:
			return
		game.use_simple_domain(viewer)
		S.notice = f"{_you(viewer)} activated Simple Domain."
	elif game.can_simple_cleanse(viewer):
		effects = game.negative_effects(viewer)
		effect = effects[answers.ask("Simple Domain: which negative effect do you remove?", effects)]
		hand = game.players[viewer].hand
		card = answers.ask("Simple Domain: which card from your hand do you discard?", [str(c) for c in hand])
		game.simple_cleanse(viewer, effect, card)
		S.notice = f"{_you(viewer)} discarded a card with Simple Domain to remove {effect}."


def h_domain(action, answers):
	game = S.game
	viewer = _viewer()
	actions = [("open", name, unlocked) for name, unlocked in game.domain_options(viewer)]
	if game.can_domain_draw(viewer):
		actions.append(("draw", None, True))
	if game.can_joker_domain(viewer):
		actions.extend(("joker", domain["player"], True) for domain in game.domains)
	if not actions:
		return
	labels = []
	for kind, arg, unlocked in actions:
		if kind == "open":
			labels.append(("Clash with " if game.domains else "Open ") + arg + ("" if unlocked else " (locked: pay a cost)"))
		elif kind == "draw":
			labels.append("Draw a card for your domain")
		else:
			labels.append(f"Expend a Joker to weaken {game.player_domain(arg)['name']} ({game.players[arg].name})")
	kind, arg, unlocked = actions[answers.ask("Domain", labels)]
	if kind == "open":
		payment = ability = None
		if not unlocked:
			player = game.players[viewer]
			costs = ["refinement"]
			if any(c.rank == "Joker" for c in player.hand):
				costs.append("joker")
			upgraded = [
				t["evolution"]["ability"] for t in character_ability_tracks(player.character)
				if "evolution" in t and player.ability_states[t["ability"]]["evolved"] and DOMAIN_TAG not in t["evolution"]["ability"]
			]
			if upgraded:
				costs.append("ability")
			payment = costs[answers.ask("Pay with (refinement = -1 refinement, joker, ability = exchange an upgrade)", costs)]
			if payment == "ability":
				ability = upgraded[answers.ask("Which upgraded ability do you give up?", upgraded)]
		game.open_domain(viewer, arg, payment, ability)
		S.notice = f"{_you(viewer)} opened {arg}."
	elif kind == "draw":
		card, result = game.domain_draw(viewer)
		S.notice = f"{_you(viewer)} drew {card} for the domain: {result}."
	else:
		game.joker_domain(viewer, arg)
		S.notice = f"{_you(viewer)} used a Joker against a domain."


def h_quick_grab(action, answers, accept=True):
	game = S.game
	viewer = _qg_target()
	if viewer is None:
		return
	game.resolve_quick_grab(viewer, accept)
	name = _you(viewer)
	S.notice = f"{name} took the card with Quick Grab." if accept else f"{name} declined Quick Grab."
	game.resolve_bot_quick_grabs()


def h_decline_quick_grab(action, answers):
	h_quick_grab(action, answers, False)


def h_resolve_slash(action, answers):
	game = S.game
	current = _human_current()
	if current is None or game.players[current].pending_world_slashes <= 0:
		return
	choices = []
	for index, player in enumerate(game.players):
		if player.is_eliminated or index != current and game.player_has_immunity(index):
			continue
		for zone, label in (("hand", "hand"), ("face_up", "face-up"), ("face_down", "face-down (random)")):
			count = len(getattr(player, zone))
			if count:
				choices.append((f"{player.name}'s {label} ({count})", zone, index, None))
	for pile_index, pile in enumerate(game.discard_piles):
		if pile:
			choices.append((f"Discard pile {pile_index + 1} ({len(pile)})", "discard_pile", None, pile_index))
	if game.destroyed_pile:
		choices.append((f"Destroyed pile ({len(game.destroyed_pile)})", "destroyed_pile", None, None))
	for pile_index, pile in enumerate(game.draw_piles):
		if pile:
			choices.append((f"Draw pile {pile_index + 1} (random, {len(pile)})", "draw_pile", None, pile_index))
	_, zone, owner, pile_index = choices[answers.ask("World Cutting Slash: choose a card or pile to delete", [c[0] for c in choices])]
	card_index = None
	if zone in ("hand", "face_up", "discard_pile", "destroyed_pile"):
		if zone == "discard_pile":
			cards = game.discard_piles[pile_index]
		elif zone == "destroyed_pile":
			cards = game.destroyed_pile
		else:
			cards = getattr(game.players[owner], zone)
		card_index = answers.ask("World Cutting Slash: choose the card to delete", [str(c) for c in cards])
	targets = [
		i for i, p in enumerate(game.players)
		if i != current and not p.is_eliminated and not game.player_has_finished(i) and not game.player_has_immunity(i)
	]
	target = None
	if targets:
		target = targets[answers.ask(
			"World Cutting Slash: choose a player to increase their Cut Meter",
			[f"{game.players[i].name} (Cut Meter {game.players[i].cut_meter}/9)" for i in targets],
		)]
	card, hidden, meter = game.resolve_world_cutting_slash(
		current, zone, target, card_owner_index=owner, card_index=card_index, pile_index=pile_index,
	)
	if meter is None:
		S.notice = "World Cutting Slash deleted a card; no active opponent remains for Cut Meter."
	else:
		victim = game.players[target]
		S.notice = f"World Cutting Slash deleted {'a hidden card' if hidden else card}; {victim.name}'s Cut Meter is {meter}/9."
		if victim.is_eliminated:
			S.notice += f" {victim.name} is eliminated and tied for last place."


def h_resolve_limitless(action, answers):
	game = S.game
	current = _human_current()
	if current is None or not game.players[current].pending_limitless_effects:
		return
	player = game.players[current]
	effect = player.pending_limitless_effects[0]
	if effect == "pick_one_face_down" and player.face_down:
		pick = answers.ask("Limitless Barrier: choose one face-down card to pick up", [f"Face-down card {i + 1}" for i in range(len(player.face_down))])
		cards = game.resolve_limitless_effect(current, face_down_index=pick)
		S.notice = f"Limitless Barrier picked up {cards[0]}."
	elif effect == "replace_hand_from_deleted" and player.hand and game.deleted_pile:
		selected = []
		for _ in range(min(len(player.hand), len(game.deleted_pile))):
			available = [i for i in range(len(game.deleted_pile)) if i not in selected]
			pick = answers.ask("Perfected Limitless: choose a Deleted card for your replacement hand", [str(game.deleted_pile[i]) for i in available])
			selected.append(available[pick])
		cards = game.resolve_limitless_effect(current, deleted_indices=tuple(selected))
		S.notice = f"Perfected Limitless replaced your hand with {len(cards)} Deleted card(s)."
	else:
		cards = game.resolve_limitless_effect(current)
		S.notice = f"Limitless Barrier resolved ({len(cards)} card(s))."


def h_skip(action, answers):
	return


HANDLERS = {
	"setup": h_setup, "play": h_play, "take_piles": h_take_piles, "end_turn": h_end_turn,
	"draw_pref": h_draw_pref, "cleave": h_cleave, "enchain": h_enchain, "card_swap": h_card_swap,
	"reveal": h_reveal, "six_eyes": h_six_eyes, "full_hand": h_full_hand, "rescue": h_rescue,
	"god": h_god, "vow": h_vow, "evolve": h_evolve, "simple_domain": h_simple_domain,
	"domain": h_domain, "quick_grab": h_quick_grab, "decline_quick_grab": h_decline_quick_grab,
	"resolve_slash": h_resolve_slash, "resolve_limitless": h_resolve_limitless, "skip": h_skip,
}


# ---------------------------------------------------------------- admin

def admin_status():
	return json.dumps({"unlocked": S.admin, "in_game": S.game is not None})


def admin_unlock(password):
	if password == pg.ADMIN_PASSWORD:
		S.admin = True
	return admin_status()


def _admin_zones():
	game = S.game
	zones = []
	for player in game.players:
		for zone in ("hand", "face_up", "face_down"):
			zones.append((f"{player.name} / {zone.replace('_', ' ')}", getattr(player, zone), "player", None))
	for index, pile in enumerate(game.draw_piles):
		zones.append((f"Draw pile {index + 1}", pile, "draw_pile", index))
	for index, pile in enumerate(game.discard_piles):
		zones.append((f"Discard pile {index + 1}", pile, "discard_pile", index))
	zones.append(("Destroyed pile", game.destroyed_pile, "destroyed_pile", None))
	zones.append(("Deleted pile", game.deleted_pile, "deleted_pile", None))
	return zones


def admin_cards():
	if not S.admin or S.game is None:
		return json.dumps({"error": "Admin access is locked or no game is running."})
	rows = []
	for location, cards, _zone, _pile in _admin_zones():
		for card in cards:
			rows.append({"id": len(rows), "location": location, "card": str(card), "rank": card.rank, "suit": card.suit})
	return json.dumps({"rows": rows, "ranks": list(RANKS) + ["Joker"], "suits": list(pg.SUITS)})


def admin_set(row_id, rank, suit):
	if not S.admin or S.game is None:
		return json.dumps({"error": "Admin access is locked or no game is running."})
	if rank not in (*RANKS, "Joker"):
		return json.dumps({"error": "Choose a valid rank."})
	position = 0
	for location, cards, zone, pile_index in _admin_zones():
		if row_id < position + len(cards):
			card_index = row_id - position
			old = cards[card_index]
			new_suit = "" if rank == "Joker" else suit if suit in pg.SUITS else old.suit or pg.SUITS[0]
			updated = pg.Card(rank, new_suit, 3 if rank == "Joker" else old.deck_number)
			cards[card_index] = updated
			if zone == "discard_pile":
				value = 14 if rank == "Joker" else VALUES[rank]
				S.game.pile_value_history[pile_index][card_index] = value
				if card_index == len(cards) - 1:
					S.game.pile_values[pile_index] = value
			S.game._record(f"Admin changed {location} card value to {updated}.")
			return json.dumps({"message": f"Updated to {updated}."})
		position += len(cards)
	return json.dumps({"error": "That card no longer exists."})


# ---------------------------------------------------------------- bots

def _bot_step():
	game = S.game
	if game is None or not S.setup_complete or game.winner is not None:
		return False
	if _qg_target() is not None or _reveal_target() is not None:
		return False
	current = game.current_player
	player = game.players[current]
	if not player.is_bot:
		if game.player_has_finished(current):
			game.end_turn()
			return True
		S.human_has_played = game.cards_played_this_turn > 0
		return False
	game.refill_player_hand(current)
	if game.cards_played_this_turn == 0:
		joker_index = next((i for i, c in enumerate(player.hand) if c.rank == "Joker"), None)
		evolvable = _evolvable(current)
		if joker_index is not None and evolvable:
			game.evolve_ability(current, joker_index, evolvable[0]["ability"])
			S.notice = f"{player.name} evolved {evolvable[0]['ability']} into {evolvable[0]['evolution']['ability']} and ended their turn."
			return True
	source, cards = pg._current_source(game, player)
	if source is None:
		game.end_turn()
		return True
	if source == "face_down":
		card_index = game.rng.randrange(len(cards))
		card = cards[card_index]
		joker_value = 14 if card.rank == "Joker" else None
		legal = [i for i in range(2) if game.can_play(card, i, joker_value=joker_value)]
		if legal:
			pile_index = min(legal, key=lambda i: (game.pile_values[i] if game.discard_piles[i] else 0, len(game.discard_piles[i])))
			card, _ = game.play_face_down(current, card_index, pile_index, joker_value=14)
			S.notice = f"{player.name} revealed and played {_played_label(card, 14)}."
		else:
			pile_index = min(range(2), key=lambda i: len(game.discard_piles[i]))
			card, _ = game.play_face_down(current, card_index, pile_index, joker_value=14)
			S.notice = f"{player.name} revealed {card} and picked up both discard piles."
		_bot_resolve(current)
		if _qg_target() is None:
			game.end_turn()
		return True
	god_rule = game.bot_god_choice(current, cards)
	if god_rule is not None:
		game.use_god_rule(current, god_rule)
	if game.cards_played_this_turn == 0:
		notes = game.bot_lapse_actions(current)
		if notes:
			S.notice = f"{player.name} {' and '.join(notes)}."
			if _reveal_target() is not None:
				return True
			source, cards = pg._current_source(game, player)
	options = pg._bot_legal_options(game, cards)
	if not options:
		pile = game.bot_cleave_choice(current, cards)
		if pile is not None:
			try:
				game.use_cleave(current, pile)
				S.notice = f"{player.name} used Cleave on pile {pile + 1} to open up a play."
				return True
			except ValueError:
				pass
		vow = game.bot_binding_vow_choice(current) if game.cards_played_this_turn == 0 else None
		if vow is not None:
			game.use_binding_vow(current, vow)
			S.notice = f"{player.name} had no legal play and used Binding Vow instead of picking up the piles."
			return True
		if game.cards_played_this_turn == 0:
			game.take_discard_piles(current)
			S.notice = f"{player.name} had no legal play and picked up both piles."
		else:
			S.notice = f"{player.name} has no legal follow-up play."
		game.end_turn()
		return True
	card_index, pile_index = pg._bot_choose_play(game, cards, options)
	joker_value = 14 if cards[card_index].rank == "Joker" else None
	card = game.play(current, source, card_index, pile_index, joker_value=joker_value)
	if card is None:
		S.notice = f"{player.name} attempted an illegal play."
		game.end_turn()
	else:
		S.notice = f"{player.name} played {_played_label(card, joker_value)}."
		_bot_resolve(current)
	return True


def _bot_resolve(current):
	game = S.game
	player = game.players[current]
	if player.pending_world_slashes and game.winner is None:
		game.resolve_bot_world_slashes(current)
	if player.pending_limitless_effects and game.winner is None:
		game.resolve_bot_limitless_effects(current)
	if game.pending_quick_grabs:
		game.resolve_bot_quick_grabs()


def bot_step(count=1):
	"""Run up to `count` bot actions; stops early when a human must act."""
	for _ in range(int(count)):
		try:
			if not _bot_step():
				break
		except ValueError as error:
			S.notice = str(error)
			break
		auto_progress()
	return get_state()
