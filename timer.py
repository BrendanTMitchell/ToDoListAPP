import math
import time
import tkinter as tk
from tkinter import ttk


def format_time(seconds):
	minutes, remaining_seconds = divmod(seconds, 60)
	return f"{minutes:02d}:{remaining_seconds:02d}"


def main():
	root = tk.Tk()
	root.title("Study Timer")
	root.resizable(False, False)

	frame = ttk.Frame(root, padding=24)
	frame.grid()

	ttk.Label(frame, text="Study Timer", font=("Segoe UI", 18, "bold")).grid(
		row=0, column=0, columnspan=2, pady=(0, 16)
	)
	ttk.Label(frame, text="Focus time (minutes)").grid(
		row=1, column=0, columnspan=2, sticky="w", pady=(0, 6)
	)

	minutes_entry = ttk.Entry(frame, width=24)
	minutes_entry.grid(row=2, column=0, columnspan=2, sticky="ew")
	minutes_entry.insert(0, "30")

	countdown_text = tk.StringVar(value="00:00")
	ttk.Label(frame, textvariable=countdown_text, font=("Segoe UI", 32, "bold")).grid(
		row=3, column=0, columnspan=2, pady=16
	)

	status_text = tk.StringVar()
	ttk.Label(frame, textvariable=status_text).grid(
		row=4, column=0, columnspan=2, pady=(0, 12)
	)

	start_button = ttk.Button(frame, text="Start")
	start_button.grid(row=5, column=0, columnspan=2, sticky="ew")

	def update_countdown(deadline):
		seconds_left = max(0, math.ceil(deadline - time.monotonic()))
		countdown_text.set(format_time(seconds_left))

		if seconds_left == 0:
			status_text.set("Break time!")
			start_button.state(["!disabled"])
			return

		root.after(200, update_countdown, deadline)

	def start_countdown():
		try:
			minutes = float(minutes_entry.get())
			if not math.isfinite(minutes) or minutes <= 0:
				raise ValueError
			total_seconds = math.ceil(minutes * 60)
		except (ValueError, OverflowError):
			status_text.set("Enter a positive, finite number of minutes.")
			return

		status_text.set("")
		countdown_text.set(format_time(total_seconds))
		start_button.state(["disabled"])
		update_countdown(time.monotonic() + total_seconds)

	start_button.configure(command=start_countdown)
	minutes_entry.focus()
	root.mainloop()


if __name__ == "__main__":
	main()
