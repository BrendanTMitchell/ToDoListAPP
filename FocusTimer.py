import json
from datetime import date
from pathlib import Path
from time import perf_counter


LOG_FILE = Path(__file__).with_name("focus_log.json")


def load_sessions():
	try:
		with LOG_FILE.open("r", encoding="utf-8") as log_file:
			return json.load(log_file)
	except FileNotFoundError:
		return []


def save_sessions(sessions):
	with LOG_FILE.open("w", encoding="utf-8") as log_file:
		json.dump(sessions, log_file, indent=2)
		log_file.write("\n")


def print_summary(sessions):
	if not sessions:
		print("No focus sessions logged today.")
		return

	totals = {}
	for session in sessions:
		name = session["name"]
		totals[name] = totals.get(name, 0) + session["minutes"]

	for name, minutes in totals.items():
		print(f"{name}: {round(minutes, 1)} min")

	grand_total = round(sum(totals.values()), 1)
	print(f"Total: {grand_total} min")


def record_session(sessions):
	name = input("Session name: ")
	print("Press Enter when you're done.")
	start_time = perf_counter()
	input()
	minutes = round((perf_counter() - start_time) / 60, 1)
	sessions.append({
		"name": name,
		"date": date.today().isoformat(),
		"minutes": minutes,
	})
	save_sessions(sessions)
	print(f"Session saved: {name} ({minutes} min)")


def main():
	sessions = load_sessions()
	today = date.today().isoformat()

	while True:
		print("\n1. Start a focus session")
		print("2. Show today's summary")
		print("3. Quit")

		choice = input("Choose an option: ")

		if choice == "1":
			record_session(sessions)
		elif choice == "2":
			today_sessions = [
				session for session in sessions if session["date"] == today
			]
			print_summary(today_sessions)
		elif choice == "3":
			break
		else:
			print("Not a valid choice")


if __name__ == "__main__":
	main()
