"use strict";

const SUIT_SYMBOLS = { Clubs: "♣", Diamonds: "♦", Hearts: "♥", Spades: "♠" };
const RANK_SHORT = { Jack: "J", Queen: "Q", King: "K", Ace: "A" };

let bridge = null;
let catalog = null;
let selectedCharacter = null;
let state = null;
let selCard = null;
let selPile = null;
let setupSel = new Set();
let confirmedViewer = null;
let fastForward = false;
let botTimer = null;
let busy = false;
let adminOpen = false;
let playerRows = [];

const $ = (id) => document.getElementById(id);

function el(tag, props = {}, ...children) {
	const node = document.createElement(tag);
	for (const [key, value] of Object.entries(props)) {
		if (key === "class") node.className = value;
		else if (key === "onclick") node.addEventListener("click", value);
		else if (value !== undefined && value !== null) node[key] = value;
	}
	for (const child of children.flat()) {
		node.append(child instanceof Node ? child : document.createTextNode(child));
	}
	return node;
}

// ---------------------------------------------------------------- boot

async function boot() {
	const pyodide = await loadPyodide();
	for (const file of ["palacegames.py", "web_bridge.py"]) {
		let text = window.PALACE_FILES && window.PALACE_FILES[file];
		if (text === undefined) {
			const response = await fetch(file, { cache: "no-store" });
			if (!response.ok) throw new Error(`Could not load ${file}`);
			text = await response.text();
		}
		pyodide.FS.writeFile(file, text);
	}
	pyodide.runPython("import web_bridge");
	bridge = pyodide.pyimport("web_bridge");
	catalog = JSON.parse(bridge.get_catalog());
	selectedCharacter = catalog.characters[0].name;
	$("loading").hidden = true;
	buildSetup();
	$("setup").hidden = false;
	if (location.hash === "#rules") openRules();
}

boot().catch((error) => {
	$("loading-text").textContent = "Could not start: " + error.message;
});

// ---------------------------------------------------------------- setup screen

function showRule(name) {
	showDialog(name, el("p", {}, catalog.rules[name]), [{ label: "Close" }]);
}

// Turns known multi use rule names inside a description into clickable underlined links.
function withRules(text, rules) {
	const container = el("span");
	let pieces = [text];
	for (const rule of rules) {
		pieces = pieces.flatMap((piece) => {
			if (typeof piece !== "string") return [piece];
			const out = [];
			const lower = piece.toLowerCase();
			const needle = rule.toLowerCase();
			let position = 0;
			let found = lower.indexOf(needle, position);
			while (found !== -1) {
				out.push(piece.slice(position, found));
				out.push(el("span", { class: "rule", onclick: () => showRule(rule) }, piece.slice(found, found + rule.length)));
				position = found + rule.length;
				found = lower.indexOf(needle, position);
			}
			out.push(piece.slice(position));
			return out;
		});
	}
	container.append(...pieces.map((piece) => (typeof piece === "string" ? document.createTextNode(piece) : piece)));
	return container;
}

function characterBlock(character, status) {
	const box = el("div", {}, el("h3", {}, character.name));
	for (const track of character.tracks) {
		const evolved = status && status.evolved.includes(track.ability);
		const removed = status && status.removed.includes(track.ability);
		const block = el("div", { class: "track" },
			el("strong", {}, track.ability + (removed ? " (replaced by its evolution)" : "")), el("br"),
			withRules(track.description, track.rules));
		if (track.evolution) {
			block.append(el("br"), el("strong", {}, "Evolution: " + track.evolution.ability + (evolved ? " (unlocked)" : "")), el("br"),
				withRules(track.evolution.description, track.evolution.rules));
		}
		box.append(block);
	}
	return box;
}

function renderCharacterDetails() {
	const character = catalog.characters.find((entry) => entry.name === selectedCharacter);
	const box = $("character-details");
	box.replaceChildren(characterBlock(character));
	box.append(el("p", { class: "hint" }, "Each evolution needs a Joker in hand before you play any cards and ends your turn. Underlined rule names can be clicked to read what they do."));
}

function showSheets() {
	if (!state || !state.players) return;
	const body = el("div", { class: "sheets" });
	const seen = new Set();
	state.players.forEach((player) => {
		if (!player.character || seen.has(player.name)) return;
		seen.add(player.name);
		const character = catalog.characters.find((entry) => entry.name === player.character);
		body.append(el("h4", {}, player.name), characterBlock(character, player));
	});
	showDialog("Character sheets", body, [{ label: "Close" }]);
}

$("show-sheets").addEventListener("click", showSheets);

function buildSetup() {
	const list = $("character-list");
	list.replaceChildren(...catalog.characters.map((character) =>
		el("button", {
			class: character.name === selectedCharacter ? "selected" : "",
			onclick: () => {
				selectedCharacter = character.name;
				buildSetup();
			},
		}, character.name)));
	renderCharacterDetails();
	rebuildPlayerRows();
}

function rebuildPlayerRows() {
	const count = Math.max(2, Math.min(catalog.max_players, parseInt($("player-count").value, 10) || 2));
	while (playerRows.length < count) {
		playerRows.push({ type: playerRows.length === 0 ? "Human" : "Bot", character: catalog.random });
	}
	playerRows.length = count;
	const rows = $("player-rows");
	rows.replaceChildren();
	playerRows.forEach((row, index) => {
		const type = el("select", { onchange: (event) => { row.type = event.target.value; } },
			...["Human", "Bot"].map((value) => el("option", { value, selected: value === row.type }, value)));
		const line = el("div", { class: "row-player" }, el("span", {}, `Player ${index + 1}`), type);
		if (index === 0) {
			line.append(el("span", {}, selectedCharacter));
		} else {
			const choices = [catalog.random, ...catalog.characters.map((c) => c.name)];
			line.append(el("select", { onchange: (event) => { row.character = event.target.value; } },
				...choices.map((value) => el("option", { value, selected: value === row.character }, value))));
		}
		rows.append(line);
	});
}

$("player-count").addEventListener("change", rebuildPlayerRows);
$("restore-defaults").addEventListener("click", () => {
	$("player-count").value = catalog.defaults.players;
	$("deck-count").value = catalog.defaults.decks;
	$("joker-count").value = catalog.defaults.jokers;
	playerRows = [];
	rebuildPlayerRows();
});

$("start").addEventListener("click", () => {
	$("setup-error").textContent = "";
	const rows = playerRows.map((row, index) => ({
		type: row.type,
		character: index === 0 ? selectedCharacter : row.character,
	}));
	const result = JSON.parse(bridge.new_game(JSON.stringify({
		players: rows,
		decks: parseInt($("deck-count").value, 10),
		jokers: parseInt($("joker-count").value, 10),
		start_joker: $("start-joker").checked,
	})));
	if (result.error) {
		$("setup-error").textContent = result.error;
		return;
	}
	$("setup").hidden = true;
	$("game").hidden = false;
	confirmedViewer = null;
	fastForward = false;
	selCard = selPile = null;
	setupSel = new Set();
	applyState(result);
});

$("new-game").addEventListener("click", () => {
	if (!confirm("Abandon this game and return to setup?")) return;
	clearTimeout(botTimer);
	botTimer = null;
	state = null;
	$("game").hidden = true;
	$("setup").hidden = false;
});

// ---------------------------------------------------------------- dialogs

function showDialog(title, body, buttons) {
	$("modal-title").textContent = title;
	const bodyBox = $("modal-body");
	bodyBox.replaceChildren(body);
	const buttonBox = $("modal-buttons");
	delete buttonBox.dataset.handoff;
	buttonBox.replaceChildren(...buttons.map((button) =>
		el("button", {
			onclick: () => {
				closeDialog();
				if (button.action) button.action();
			},
		}, button.label)));
	$("modal").hidden = false;
}

function closeDialog() {
	$("modal").hidden = true;
}

function showAsk(ask, answers, action) {
	const buttons = ask.options.map((label, index) => ({
		label,
		action: () => send(action, [...answers, index]),
	}));
	buttons.push({ label: "Cancel" });
	showDialog(ask.title, el("p", {}), buttons);
}

$("show-log").addEventListener("click", () => {
	if (state) showDialog("Action log", el("pre", {}, state.log.join("\n")), [{ label: "Close" }]);
});

// ---------------------------------------------------------------- rules page

const RULES_SECTIONS = [
	["Goal", [
		"Get rid of all of your cards before everyone else. Cards are played from your hand first, then your face-up cards, then your face-down cards. Players who run out finish in order; the last player left is last place.",
	]],
	["Setup", [
		"Every player is dealt 3 face-down cards and 6 cards in hand, then keeps 3 of the 6 face-up on the table. The rest of the deck is split into two draw piles. One card from each draw pile starts the two discard piles (a Joker is reshuffled back; a 10 destroys its pile right away).",
		"You choose the number of players (human or bot), the number of 52-card decks and the number of Jokers before the game starts.",
	]],
	["Taking a turn", [
		"There are two discard piles. On your turn you choose one of them and play at least one card on it. Any extra cards you play in the same turn must go on that same pile. Press End turn when you are done.",
		"Your hand is topped up to 3 cards after each play while the draw piles last. Face-up cards can only be played once your hand and both draw piles are empty, and face-down cards after that (you play them blind).",
		"The first card you play must be equal to or higher than the top card of the pile (Jack 11, Queen 12, King 13, Ace 14). An empty pile accepts anything.",
		"After your first card, you can keep stacking on the pile you just played on, as long as each card is the same value as the top card or exactly one higher.",
	]],
	["Special cards", [
		"2: can be played on anything as your first card, and later only on top of an Ace or another 2.",
		"10: as the first card of your turn it can be played on anything. Any 10 destroys the whole pile it is played on, moving it to the destroyed pile.",
		"Joker: wild. You choose its value from 2 to 14 when you play it. A Joker in hand before you play can also be spent to evolve an ability (see characters). Face-down Jokers count as Aces.",
		"Ace: the highest card. Only an Ace, a 2, a 10 or a Joker can go on top of an Ace.",
	]],
	["Picking up", [
		"If you cannot play, or your first card is illegal, you pick up both discard piles and your turn ends. An illegal card after your first play is blocked and ends your turn without picking anything up. A face-down card that turns out to be illegal also makes you pick up both piles.",
	]],
	["Characters, abilities and evolutions", [
		"Each player has a character with abilities. Some abilities can evolve: spend a Joker from your hand before you play any card and your turn ends, but the ability becomes its evolved version. Evolved abilities keep the base ability's behavior unless stated otherwise.",
		"Abilities whose name contains (Domain) are domains and follow Domain Clashing, below.",
	]],
];

function buildRulesPage() {
	const box = $("rules-content");
	box.replaceChildren();
	for (const [title, paragraphs] of RULES_SECTIONS) {
		box.append(el("div", { class: "panel" }, el("h2", {}, title), ...paragraphs.map((text) => el("p", {}, text))));
	}
	const multi = el("div", { class: "panel" },
		el("h2", {}, "Multi-use rules"),
		el("p", {}, "Abilities are built from these reusable rules. Characters can gain them from their abilities, and God of Jujutsu lets its owner use any of them."));
	for (const [name, text] of Object.entries(catalog.rules)) {
		multi.append(el("p", {}, el("strong", {}, name), el("br"), text));
	}
	box.append(multi);
	box.append(el("div", { class: "panel" }, el("h2", {}, "Domain Clashing"), el("pre", { class: "plain" }, catalog.domain_rule)));
}

let viewBeforeRules = "setup";

function openRules() {
	if (!$("rules-page").hidden) return;
	viewBeforeRules = !$("game").hidden ? "game" : "setup";
	$("setup").hidden = true;
	$("game").hidden = true;
	buildRulesPage();
	$("rules-page").hidden = false;
	window.scrollTo(0, 0);
	if (location.hash !== "#rules") location.hash = "rules";
}

function closeRules() {
	if ($("rules-page").hidden) return;
	$("rules-page").hidden = true;
	$(viewBeforeRules).hidden = false;
	if (location.hash === "#rules") history.replaceState(null, "", location.pathname + location.search);
}

document.querySelectorAll(".open-rules").forEach((button) => button.addEventListener("click", openRules));
$("rules-back").addEventListener("click", closeRules);
window.addEventListener("hashchange", () => {
	if (location.hash === "#rules") openRules();
	else closeRules();
});

// ---------------------------------------------------------------- admin menu

function openAdmin() {
	const status = JSON.parse(bridge.admin_status());
	const password = el("input", { type: "password", placeholder: "Admin password" });
	const message = el("p", {}, status.unlocked ? "Admin access is unlocked for this session." : "Enter the admin password to enable card editing.");
	const editButton = el("button", {
		disabled: !(status.unlocked && status.in_game),
		onclick: () => { closeDialog(); openCardEditor(); },
	}, "Edit all card values");
	const unlock = () => {
		const result = JSON.parse(bridge.admin_unlock(password.value));
		message.textContent = result.unlocked ? "Admin access unlocked for this session." : "Incorrect password.";
		editButton.disabled = !(result.unlocked && result.in_game);
		if (result.unlocked && !result.in_game) message.textContent += " Start a game to edit cards.";
	};
	password.addEventListener("keydown", (event) => { if (event.key === "Enter") unlock(); });
	showDialog("Admin access", el("div", {}, message, password, el("button", { onclick: unlock }, "Unlock"), el("br"), editButton),
		[{ label: "Close" }]);
	password.focus();
}

function openCardEditor() {
	adminOpen = true;
	let selected = null;
	let data = null;
	const list = el("select", { size: 14, class: "admin-list" });
	const rank = el("select");
	const suit = el("select");
	const message = el("p", {});
	const label = el("strong", {}, "Select a card");

	const refill = () => {
		data = JSON.parse(bridge.admin_cards());
		if (data.error) {
			message.textContent = data.error;
			return;
		}
		list.replaceChildren(...data.rows.map((row) => el("option", { value: String(row.id), selected: row.id === selected }, `${row.location}: ${row.card}`)));
		if (!rank.options.length) {
			data.ranks.forEach((value) => rank.append(el("option", { value }, value)));
			data.suits.forEach((value) => suit.append(el("option", { value }, value)));
		}
	};
	list.addEventListener("change", () => {
		selected = parseInt(list.value, 10);
		const row = data.rows[selected];
		label.textContent = `${row.location}: ${row.card}`;
		rank.value = row.rank;
		suit.value = row.suit || data.suits[0];
		suit.disabled = row.rank === "Joker";
	});
	rank.addEventListener("change", () => { suit.disabled = rank.value === "Joker"; });
	const apply = el("button", {
		onclick: () => {
			if (selected === null) return;
			const result = JSON.parse(bridge.admin_set(selected, rank.value, suit.value));
			message.textContent = result.error || result.message;
			applyState(JSON.parse(bridge.get_state()));
			refill();
		},
	}, "Apply card change");
	refill();
	showDialog("Admin card editor", el("div", { class: "admin-editor" },
		list, el("div", {}, label, el("br"), "Rank", el("br"), rank, el("br"), "Suit", el("br"), suit, el("br"), apply, message)),
	[{ label: "Close", action: () => { adminOpen = false; scheduleBot(); } }]);
}

document.querySelectorAll(".open-admin").forEach((button) => button.addEventListener("click", openAdmin));

// ---------------------------------------------------------------- bridge calls

function send(action, answers = []) {
	if (busy) return;
	const result = JSON.parse(bridge.act(JSON.stringify({ ...action, answers })));
	if (result.ask) {
		showAsk(result.ask, answers, action);
		return;
	}
	selCard = null;
	applyState(result);
}

function botTick() {
	botTimer = null;
	if (adminOpen || !state || state.phase !== "play" || !state.needs_bot) return;
	const result = JSON.parse(bridge.bot_step(fastForward ? 40 : 1));
	applyState(result);
}

function scheduleBot() {
	if (adminOpen || botTimer !== null || !state || state.phase !== "play" || !state.needs_bot || needsHandoff()) return;
	botTimer = setTimeout(botTick, fastForward ? 0 : 350);
}

function applyState(next) {
	state = next;
	if (state.phase === "over") fastForward = false;
	render();
	if (state.popup) showDialog("Six Eyes", el("div", {}, el("p", {}, state.popup.text), cardRow(state.popup.cards)), [{ label: "OK" }]);
	scheduleBot();
	autoResolve();
}

// Pending World Cutting Slash / Limitless effects open their prompts automatically.
function autoResolve() {
	if (state.phase !== "play" || needsHandoff() || !$("modal").hidden) return;
	const ids = state.buttons.map((button) => button.id);
	if (ids.includes("resolve_slash")) setTimeout(() => send({ type: "resolve_slash" }), 0);
	else if (ids.includes("resolve_limitless")) setTimeout(() => send({ type: "resolve_limitless" }), 0);
}

function needsHandoff() {
	return Boolean(state && state.hot_seat && state.phase !== "over" && state.viewer !== confirmedViewer);
}

// ---------------------------------------------------------------- rendering

function cardNode(card, options = {}) {
	const red = card.suit === "Hearts" || card.suit === "Diamonds";
	const classes = ["card"];
	if (red) classes.push("red");
	if (card.rank === "Joker") classes.push("joker");
	if (options.selected) classes.push("selected");
	const text = card.rank === "Joker" ? "Joker" : (RANK_SHORT[card.rank] || card.rank) + " " + SUIT_SYMBOLS[card.suit];
	const node = el("button", { class: classes.join(" "), onclick: options.onclick, title: card.label }, text);
	if (options.disabled) node.disabled = true;
	return node;
}

function hiddenNode(index, known, options) {
	const node = el("button", { class: "card hidden" + (options.selected ? " selected" : ""), onclick: options.onclick },
		"Face-down " + (index + 1));
	if (known) node.append(el("small", {}, "Seen: " + known));
	return node;
}

// Turns a card label such as "Ace of Spades" or "Joker as King" back into a card for display.
function labelToCard(label) {
	if (label.startsWith("Joker")) return { rank: "Joker", suit: "", label };
	const [rank, suit] = label.split(" of ");
	return { rank, suit, label };
}

function miniCard(label) {
	const card = labelToCard(label);
	const classes = ["card", "mini"];
	if (card.suit === "Hearts" || card.suit === "Diamonds") classes.push("red");
	if (card.rank === "Joker") classes.push("joker");
	const text = card.rank === "Joker"
		? label.replace("Joker as ", "Joker = ")
		: (RANK_SHORT[card.rank] || card.rank) + " " + SUIT_SYMBOLS[card.suit];
	return el("div", { class: classes.join(" "), title: label }, text);
}

function cardRow(labels, emptyText = "Empty") {
	if (!labels.length) return el("p", {}, emptyText);
	return el("div", { class: "cards mini-row" }, labels.map(miniCard));
}

function render() {
	const st = state;
	if (needsHandoff()) {
		renderHandoff();
		return;
	}
	closeHandoffIfAny();
	const phaseText = st.phase === "setup" ? "Setup"
		: st.phase === "over" ? `${st.winner} finished first.`
		: `Round ${st.round}  |  Turn ${st.turn}  |  ${st.players[st.current].name}`;
	$("status").textContent = phaseText + "\n" + st.notice;
	renderPiles();
	renderPlayers();
	renderHand();
}

function renderHandoff() {
	const name = state.players[state.viewer].name;
	$("status").textContent = "Pass the device";
	showDialog("Pass the device", el("p", { class: "handoff" }, `Hand the device to ${name}. Hands stay hidden until they are ready.`), [
		{
			label: `I'm ${name} - show my cards`,
			action: () => {
				confirmedViewer = state.viewer;
				applyState(state);
			},
		},
	]);
	$("modal-buttons").dataset.handoff = "1";
}

function closeHandoffIfAny() {
	const buttons = $("modal-buttons");
	if (buttons.dataset.handoff) {
		delete buttons.dataset.handoff;
		closeDialog();
	}
}

function renderPiles() {
	const st = state;
	const box = $("piles");
	box.replaceChildren();
	st.draw_piles.forEach((count, index) => {
		box.append(el("div", { class: "draw" }, `DRAW PILE ${index + 1}`, el("br"), "Cards hidden", el("br"), `${count} cards`));
	});
	[["Destroyed pile", st.destroyed], ["Deleted pile", st.deleted]].forEach(([title, cards]) => {
		box.append(el("div", { class: "pile" }, el("button", {
			onclick: () => showDialog(title, cardRow(cards), [{ label: "Close" }]),
		}, `${title} (${cards.length})`)));
	});
	st.discards.forEach((pile, index) => {
		const canPick = st.phase === "play" && st.me.is_current;
		const node = el("div", { class: "pile discard" + (selPile === index ? " selected" : ""), onclick: () => {
			if (canPick) {
				selPile = index;
				render();
			}
		} },
		`DISCARD ${index + 1}`, pile.top ? miniCard(pile.top) : el("small", {}, "Empty"), el("small", {}, `${pile.count} cards`));
		const viewButton = el("button", { onclick: (event) => {
			event.stopPropagation();
			showDialog(`Discard pile ${index + 1}`, cardRow(pile.cards), [{ label: "Close" }]);
		} }, "View all cards");
		node.append(viewButton);
		box.append(node);
	});
}

function renderPlayers() {
	const box = $("players");
	box.replaceChildren();
	state.players.forEach((player, index) => {
		const lines = [
			el("strong", {}, player.name + (player.character ? ` (${player.character})` : "") + (player.current ? " - current turn" : "")),
			el("br"),
			`Hand: ${player.hand} | Face-down: ${player.face_down}`,
			el("br"),
			"Face-up:",
			player.face_up.length ? el("div", { class: "mini-row" }, player.face_up.map((card) => miniCard(card.label))) : " none",
		];
		if (player.revealed.length) lines.push("Revealed:", el("div", { class: "mini-row" }, player.revealed.map(miniCard)));
		if (player.seen.length) lines.push("Seen cards in their hand/face-down:", el("div", { class: "mini-row" }, player.seen.map(miniCard)));
		if (player.seen_down && player.seen_down.length) {
			lines.push("Your face-down cards you have seen:", el("div", { class: "mini-row" },
				player.seen_down.map((entry) => el("span", { class: "slot" }, el("small", {}, `Slot ${entry.slot}`), miniCard(entry.label)))));
		}
		const node = el("div", { class: "player" + (player.current ? " current" : "") }, ...lines);
		if (player.tags.length) {
			node.append(el("br"), ...player.tags.map((tag) => el("span", { class: "tag" }, tag)));
		}
		box.append(node);
	});
}

function renderHand() {
	const st = state;
	const cards = $("cards");
	const actions = $("actions");
	const draw = $("draw-choice");
	cards.replaceChildren();
	actions.replaceChildren();
	draw.replaceChildren();

	if (st.phase === "over") {
		$("hand-title").textContent = "Final standings";
		const table = el("table", { class: "standings" });
		st.standings.forEach((row) => {
			table.append(el("tr", {},
				el("td", {}, `${row.rank}.`), el("td", {}, row.name),
				el("td", {}, row.status), el("td", {}, `Round ${row.round}, Turn ${row.turn}`)));
		});
		cards.append(table);
		return;
	}

	if (st.phase === "setup") {
		$("hand-title").textContent = `${st.me.name}: choose 3 face-up cards | ${setupSel.size}/3 selected`;
		st.me.hand.forEach((card, index) => {
			cards.append(cardNode(card, {
				selected: setupSel.has(index),
				onclick: () => {
					if (setupSel.has(index)) setupSel.delete(index);
					else if (setupSel.size < 3) setupSel.add(index);
					render();
				},
			}));
		});
		actions.append(el("button", {
			class: "primary",
			disabled: setupSel.size !== 3,
			onclick: () => {
				const picks = [...setupSel];
				setupSel = new Set();
				send({ type: "setup", cards: picks });
			},
		}, "Set face-up cards"));
		return;
	}

	const me = st.me;
	if (me.mode === "reveal") {
		$("hand-title").textContent = `${me.name}: choose a card from your hand to reveal until it is played`;
		me.hand.forEach((card, index) => cards.append(cardNode(card, { onclick: () => send({ type: "reveal", card: index }) })));
		return;
	}

	const source = me.source;
	if (!me.is_current) {
		$("hand-title").textContent = st.players[st.current].bot ? "Bots are playing" : `Waiting for ${st.players[st.current].name}`;
	} else {
		$("hand-title").textContent = source ? `${st.hot_seat ? me.name + "'s" : "Your"} ${source.replace("_", " ")}` : "No cards available";
	}
	if (me.is_current && source) {
		const list = source === "hand" ? me.hand : source === "face_up" ? me.face_up : me.face_down;
		list.forEach((card, index) => {
			const options = { selected: selCard === index, onclick: () => { selCard = index; render(); } };
			cards.append(source === "face_down" ? hiddenNode(index, card.known, options) : cardNode(card, options));
		});
	}

	if (st.draw_choice) {
		draw.append(el("div", {}, "Mastered Six Eyes: choose 1 of the top 3 cards of each draw pile to draw."));
		st.draw_choice.forEach((choice) => {
			draw.append(el("button", {
				onclick: () => send({ type: "draw_pref", pile: choice.pile, depth: choice.depth }),
			}, `${choice.label} (pile ${choice.pile + 1}, #${choice.depth + 1})`));
		});
	}

	if (st.all_humans_finished) {
		actions.append(el("button", { class: "primary", onclick: () => { fastForward = true; applyState(state); } }, "Skip to results"));
		return;
	}
	if (me.is_current) {
		const canPlay = source && selCard !== null && selPile !== null && !me.pending && !st.draw_choice;
		actions.append(
			el("button", {
				class: "primary",
				disabled: !canPlay,
				onclick: () => send({ type: "play", card: selCard, pile: selPile }),
			}, source === "face_down" ? "Reveal and play" : "Play selected card"),
			el("button", { disabled: !me.can_end, onclick: () => send({ type: "end_turn" }) }, "End turn"),
			el("button", {
				disabled: !me.can_pickup,
				onclick: () => { if (confirm("Pick up both discard piles? This ends your turn.")) send({ type: "take_piles" }); },
			}, "Pick up discard piles"),
		);
	}
	st.buttons.forEach((button) => {
		if (button.info) {
			actions.append(el("span", { class: "info" }, button.label));
			return;
		}
		const extra = button.id === "cleave" ? { pile: selPile } : {};
		const enabled = button.enabled && (button.id !== "cleave" || (selPile !== null && st.discards[selPile].count > 0));
		actions.append(el("button", { disabled: !enabled, onclick: () => send({ type: button.id, ...extra }) }, button.label));
	});
}
