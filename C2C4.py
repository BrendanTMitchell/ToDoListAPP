MILES_TO_KILOMETERS = 1.60934


def main():
    miles = float(input("Enter the number of miles: "))
    kilometers = miles * MILES_TO_KILOMETERS
    print(f"{kilometers:.2f} kilometers")


if __name__ == "__main__":
    main()